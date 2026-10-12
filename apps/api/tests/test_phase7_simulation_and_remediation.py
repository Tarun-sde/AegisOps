"""Tests for Phase 7: Incident Simulation Lab, Controlled Remediation, and Auditable Recovery.

Validates:
- Workstream A/B: S01-S06 failure scenarios catalog and life cycle
- Workstream C: Fault controller, start, reset, lazy expiry, concurrency conflicts
- Workstream D/E/F: Remediation execution engine, RBAC, two-phase claiming, idempotency
- Workstream G: Google ADK create_remediation_proposal tool
- Workstream H: Recovery verification & service.recovery_observed events
- Workstream K: Multi-tenant boundary, production rejection, tampered payload defense
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agents.incident_investigator.tools.gateway import ReadOnlyToolGateway
from apps.api.app.actions.catalog import (
    validate_proposal_parameters,
)
from apps.api.app.auth import hash_password
from apps.api.app.db import get_db
from apps.api.app.main import app
from apps.api.app.models import (
    ActionExecution,
    ActionProposal,
    Base,
    Incident,
    Membership,
    Organization,
    OutboxEvent,
    ProposalApproval,
    Service,
    SimulationRun,
    User,
)
from apps.api.app.simulation.scenarios import SCENARIO_CATALOG
from apps.api.app.simulation.service import SimulationService

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def test_client():
    return TestClient(app)


def create_user_and_tenant(
    db, email: str, role: str = "admin", org_name: str = "Test Org"
) -> tuple[User, Organization, str]:
    pwd_hash, salt = hash_password("password123")
    user = User(
        email=email,
        name=email.split("@")[0].title(),
        hashed_password=pwd_hash,
        salt=salt,
        is_active=True,
    )
    org = Organization(name=org_name)
    db.add_all([user, org])
    db.flush()

    membership = Membership(
        user_id=user.id,
        organization_id=org.id,
        role=role,
    )
    db.add(membership)
    db.commit()
    db.refresh(user)
    db.refresh(org)
    return user, org, "password123"


def login_client(client: TestClient, email: str, password: str = "password123") -> dict[str, str]:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"x-csrf-token": res.cookies["aegisops_csrf"]}


def create_target_service(
    db, org_id: uuid.UUID, name: str = "shop-api", env: str = "staging"
) -> Service:
    svc = Service(
        name=name,
        organization_id=org_id,
        environment=env,
        status="active",
    )
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


# ---------------------------------------------------------------------------
# SCENARIO CATALOG & DEFINITIONS (Workstream A & B)
# ---------------------------------------------------------------------------


def test_scenario_catalog_integrity():
    """Validates that all six scenarios S01-S06 are defined with required attributes."""
    expected_ids = {
        "S01_CHECKOUT_500",
        "S02_SLOW_DB_QUERIES",
        "S03_DB_POOL_EXHAUSTION",
        "S04_BROKEN_RELEASE",
        "S05_SERVICE_UNAVAILABLE",
        "S06_SLOW_DOWNSTREAM",
    }
    assert set(SCENARIO_CATALOG.keys()) == expected_ids

    for sc_id, sc in SCENARIO_CATALOG.items():
        assert sc.scenario_id == sc_id
        assert sc.allowed_environment == "staging"
        assert sc.maximum_duration_seconds > 0
        assert sc.risk_level in ("LOW", "MEDIUM", "HIGH")
        has_restart = "restart_demo_service" in sc.permitted_actions
        has_rollback = "rollback_demo_release" in sc.permitted_actions
        assert has_restart or has_rollback


def test_get_scenarios_api(test_client):
    """GET /api/v1/simulation/scenarios returns catalog items."""
    db = TestingSessionLocal()
    create_user_and_tenant(db, "admin@test.com", "admin")
    headers = login_client(test_client, "admin@test.com")

    res = test_client.get("/api/v1/simulation/scenarios", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 6
    scenario_ids = [item["scenario_id"] for item in data]
    assert "S01_CHECKOUT_500" in scenario_ids
    assert "S04_BROKEN_RELEASE" in scenario_ids


# ---------------------------------------------------------------------------
# SIMULATION LIFECYCLE: START, CONFLICT, RESET, LAZY EXPIRY (Workstream C)
# ---------------------------------------------------------------------------


@patch.object(SimulationService, "_call_shop_api")
def test_simulation_start_and_reset_flow(mock_call_shop_api, test_client):
    """Verifies starting scenario S01 and manually resetting it."""
    mock_call_shop_api.return_value = {"status": "ok", "scenario": "S01_CHECKOUT_500"}

    db = TestingSessionLocal()
    _, org, _ = create_user_and_tenant(db, "admin@test.com", "admin")
    svc = create_target_service(db, org.id, "shop-api", "staging")
    headers = login_client(test_client, "admin@test.com")

    # 1. Start S01
    start_payload = {
        "service_id": str(svc.id),
        "environment": "staging",
    }
    res = test_client.post(
        "/api/v1/simulation/scenarios/S01_CHECKOUT_500/start",
        json=start_payload,
        headers=headers,
    )
    assert res.status_code == 201, res.text
    run_data = res.json()
    run_id = run_data["id"]
    assert run_data["scenario_id"] == "S01_CHECKOUT_500"
    assert run_data["status"] == "ACTIVE"
    assert run_data["cleanup_status"] == "PENDING"

    # Verify outbox event and simulation events
    events_res = test_client.get(f"/api/v1/simulation/runs/{run_id}/events", headers=headers)
    assert events_res.status_code == 200
    event_types = [e["event_type"] for e in events_res.json()]
    assert "simulation.started" in event_types
    assert "simulation.fault_activated" in event_types

    # 2. Reset the simulation
    mock_call_shop_api.return_value = {"status": "ok", "reset": True}
    reset_res = test_client.post(
        f"/api/v1/simulation/runs/{run_id}/reset",
        json={"reason": "Operator completed experiment"},
        headers=headers,
    )
    assert reset_res.status_code == 200, reset_res.text
    reset_data = reset_res.json()
    assert reset_data["status"] == "COMPLETED"
    assert reset_data["cleanup_status"] == "CLEANED"
    assert reset_data["ended_at"] is not None


@patch.object(SimulationService, "_call_shop_api")
def test_simulation_concurrency_conflict(mock_call_shop_api, test_client):
    """Starting scenario on a service that already has an ACTIVE scenario fails with 409."""
    mock_call_shop_api.return_value = {"status": "ok"}
    db = TestingSessionLocal()
    _, org, _ = create_user_and_tenant(db, "admin@test.com", "admin")
    svc = create_target_service(db, org.id, "shop-api", "staging")
    headers = login_client(test_client, "admin@test.com")

    # Start first scenario S01
    res1 = test_client.post(
        "/api/v1/simulation/scenarios/S01_CHECKOUT_500/start",
        json={"service_id": str(svc.id)},
        headers=headers,
    )
    assert res1.status_code == 201

    # Attempt to start S02 on the same service concurrently
    res2 = test_client.post(
        "/api/v1/simulation/scenarios/S02_SLOW_DB_QUERIES/start",
        json={"service_id": str(svc.id)},
        headers=headers,
    )
    assert res2.status_code == 409
    assert "already ACTIVE" in res2.json()["detail"]


@patch.object(SimulationService, "_call_shop_api")
def test_simulation_lazy_expiry_and_watchdog(mock_call_shop_api, test_client):
    """Verifies that expired simulations are safely cleaned up on query and watchdog."""
    mock_call_shop_api.return_value = {"status": "ok"}
    db = TestingSessionLocal()
    user, org, _ = create_user_and_tenant(db, "admin@test.com", "admin")
    svc = create_target_service(db, org.id, "shop-api", "staging")
    headers = login_client(test_client, "admin@test.com")

    # Create an expired run directly in DB
    past_time = datetime.now(UTC) - timedelta(minutes=10)
    expired_run = SimulationRun(
        organization_id=org.id,
        scenario_id="S03_DB_POOL_EXHAUSTION",
        service_id=svc.id,
        environment="staging",
        status="ACTIVE",
        started_by_id=user.id,
        started_at=past_time,
        expires_at=past_time + timedelta(seconds=60),
        expected_cause="CONNECTION_POOL_SATURATION",
        cleanup_status="PENDING",
    )
    db.add(expired_run)
    db.commit()
    db.refresh(expired_run)

    # Calling GET /api/v1/simulation/runs/{run_id} triggers lazy expiry
    res = test_client.get(f"/api/v1/simulation/runs/{expired_run.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "EXPIRED"
    assert data["ended_at"] is not None

    # Trigger watchdog reconciliation
    watchdog_res = test_client.post("/api/v1/simulation/watchdog/reconcile", headers=headers)
    assert watchdog_res.status_code == 200
    assert "cleaned_expired_runs" in watchdog_res.json()


# ---------------------------------------------------------------------------
# RECOVERY VERIFICATION (Workstream H)
# ---------------------------------------------------------------------------


@patch("urllib.request.urlopen")
def test_simulation_recovery_verification(mock_urlopen, test_client):
    """POST /api/v1/simulation/runs/{id}/verify-recovery checks genuine health and records event."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"status": "ok", "fault_active": False}).encode(
        "utf-8"
    )
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    db = TestingSessionLocal()
    user, org, _ = create_user_and_tenant(db, "admin@test.com", "admin")
    svc = create_target_service(db, org.id, "shop-api", "staging")
    headers = login_client(test_client, "admin@test.com")

    sim_run = SimulationRun(
        organization_id=org.id,
        scenario_id="S01_CHECKOUT_500",
        service_id=svc.id,
        environment="staging",
        status="ACTIVE",
        started_by_id=user.id,
        started_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        expected_cause="PAYMENT_GATEWAY_TIMEOUT",
        cleanup_status="PENDING",
    )
    db.add(sim_run)
    db.commit()

    res = test_client.post(
        f"/api/v1/simulation/runs/{sim_run.id}/verify-recovery",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["recovered"] is True
    assert data["health"]["fault_active"] is False


# ---------------------------------------------------------------------------
# RBAC & MULTI-TENANT ISOLATION (Workstream K)
# ---------------------------------------------------------------------------


def test_simulation_rbac_viewer_denied(test_client):
    """Role viewer is forbidden from starting or resetting simulations."""
    db = TestingSessionLocal()
    _, org, _ = create_user_and_tenant(db, "viewer@test.com", "viewer")
    svc = create_target_service(db, org.id, "shop-api", "staging")
    headers = login_client(test_client, "viewer@test.com")

    res = test_client.post(
        "/api/v1/simulation/scenarios/S01_CHECKOUT_500/start",
        json={"service_id": str(svc.id)},
        headers=headers,
    )
    assert res.status_code == 403


def test_simulation_tenant_isolation(test_client):
    """Alien tenant in Organization B cannot access simulation runs from Organization A."""
    db = TestingSessionLocal()
    user_a, org_a, _ = create_user_and_tenant(db, "admin_a@test.com", "admin", "Org A")
    _, org_b, _ = create_user_and_tenant(db, "admin_b@test.com", "admin", "Org B")
    svc_a = create_target_service(db, org_a.id, "shop-api", "staging")

    sim_run_a = SimulationRun(
        organization_id=org_a.id,
        scenario_id="S01_CHECKOUT_500",
        service_id=svc_a.id,
        environment="staging",
        status="ACTIVE",
        started_by_id=user_a.id,
        started_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        expected_cause="PAYMENT_GATEWAY_TIMEOUT",
        cleanup_status="PENDING",
    )
    db.add(sim_run_a)
    db.commit()

    headers_b = login_client(test_client, "admin_b@test.com")

    # Org B trying to view Org A's simulation run
    res = test_client.get(f"/api/v1/simulation/runs/{sim_run_a.id}", headers=headers_b)
    assert res.status_code == 404

    # Org B trying to reset Org A's simulation run
    res_reset = test_client.post(
        f"/api/v1/simulation/runs/{sim_run_a.id}/reset",
        json={"reason": "Attacker trying to reset"},
        headers=headers_b,
    )
    assert res_reset.status_code == 404


# ---------------------------------------------------------------------------
# CONTROLLED REMEDIATION EXECUTION (Workstreams D, E, F)
# ---------------------------------------------------------------------------


def create_proposal_and_approve(
    db, org_id: uuid.UUID, svc_id: uuid.UUID, user_id: uuid.UUID, env: str = "staging"
) -> tuple[ActionProposal, ProposalApproval]:
    params = {"service_name": "shop-api", "reason": "Demonstration restart"}
    canonical_params, p_hash = validate_proposal_parameters("restart_demo_service", params)

    proposal = ActionProposal(
        organization_id=org_id,
        service_id=svc_id,
        environment=env,
        action_catalog_id="restart_demo_service",
        immutable_parameters=canonical_params,
        parameters_hash=p_hash,
        reason="Demonstration recovery",
        expected_outcome="Shop API restarted cleanly",
        known_risks="Brief temporary unavailability",
        status="PROPOSED",
        idempotency_key=f"prop:{uuid.uuid4()}",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    db.add(proposal)
    db.flush()

    approval = ProposalApproval(
        proposal_id=proposal.id,
        organization_id=org_id,
        approver_id=user_id,
        decision="APPROVED",
        comment="Verified safe staging remediation",
        parameters_hash=p_hash,
    )
    proposal.status = "APPROVED"
    db.add(approval)
    db.commit()
    db.refresh(proposal)
    db.refresh(approval)
    return proposal, approval


@patch("apps.api.app.actions.executor.RemediationExecutor._verify_health")
@patch("apps.api.app.actions.executor.RemediationExecutor._call_service")
def test_remediation_execution_happy_path(mock_call_service, mock_verify_health, test_client):
    """Approved staging proposal is claimed and executed; records ActionExecution and outbox."""
    mock_call_service.return_value = {"status": "ok", "action": "restart_demo_service"}
    mock_verify_health.return_value = {"status": "ok", "fault_active": False}

    db = TestingSessionLocal()
    user, org, _ = create_user_and_tenant(db, "admin@test.com", "admin")
    svc = create_target_service(db, org.id, "shop-api", "staging")
    proposal, _ = create_proposal_and_approve(db, org.id, svc.id, user.id, "staging")

    headers = login_client(test_client, "admin@test.com")

    # Execute proposal
    res = test_client.post(f"/api/v1/actions/proposals/{proposal.id}/execute", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "SUCCEEDED"
    assert data["action_catalog_id"] == "restart_demo_service"
    assert data["parameters_hash"] == proposal.parameters_hash
    assert data["error_message"] is None

    # Verify execution record in DB
    db_exec = db.query(ActionExecution).filter_by(proposal_id=proposal.id).first()
    assert db_exec is not None
    assert db_exec.status == "SUCCEEDED"

    # Verify proposal status transitioned to SUCCEEDED
    db.refresh(proposal)
    assert proposal.status == "SUCCEEDED"

    # Verify outbox event emitted
    outbox = db.query(OutboxEvent).filter_by(event_type="action.execution_succeeded").first()
    assert outbox is not None


def test_remediation_production_target_rejection(test_client):
    """Rule 1 & Rule 6: Execution against production environment is strictly rejected."""
    db = TestingSessionLocal()
    user, org, _ = create_user_and_tenant(db, "admin@test.com", "admin")
    svc_prod = create_target_service(db, org.id, "shop-api", "production")

    params = {"service_name": "shop-api", "reason": "Targeting prod attempt"}
    canonical_params, p_hash = validate_proposal_parameters("restart_demo_service", params)
    proposal = ActionProposal(
        organization_id=org.id,
        service_id=svc_prod.id,
        environment="production",
        action_catalog_id="restart_demo_service",
        immutable_parameters=canonical_params,
        parameters_hash=p_hash,
        reason="Malicious attempt to target production",
        expected_outcome="Fail closed",
        known_risks="Brief temporary unavailability",
        status="APPROVED",
        idempotency_key=f"prop:{uuid.uuid4()}",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    db.add(proposal)
    db.flush()
    approval = ProposalApproval(
        proposal_id=proposal.id,
        organization_id=org.id,
        approver_id=user.id,
        decision="APPROVED",
        comment="Should still be rejected by deterministic backend",
        parameters_hash=p_hash,
    )
    db.add(approval)
    db.commit()

    headers = login_client(test_client, "admin@test.com")
    res = test_client.post(f"/api/v1/actions/proposals/{proposal.id}/execute", headers=headers)
    assert res.status_code == 400
    assert "production" in res.json()["detail"].lower()


def test_remediation_unapproved_proposal_rejection(test_client):
    """Proposals in PROPOSED state cannot be executed without prior human approval."""
    db = TestingSessionLocal()
    _, org, _ = create_user_and_tenant(db, "admin@test.com", "admin")
    svc = create_target_service(db, org.id, "shop-api", "staging")

    params = {"service_name": "shop-api", "reason": "Unapproved execution attempt"}
    canonical_params, p_hash = validate_proposal_parameters("restart_demo_service", params)
    proposal = ActionProposal(
        organization_id=org.id,
        service_id=svc.id,
        environment="staging",
        action_catalog_id="restart_demo_service",
        immutable_parameters=canonical_params,
        parameters_hash=p_hash,
        reason="Unapproved execution attempt",
        expected_outcome="Denied",
        known_risks="Brief temporary unavailability",
        status="PROPOSED",  # Not APPROVED
        idempotency_key=f"prop:{uuid.uuid4()}",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    db.add(proposal)
    db.commit()

    headers = login_client(test_client, "admin@test.com")
    res = test_client.post(f"/api/v1/actions/proposals/{proposal.id}/execute", headers=headers)
    assert res.status_code == 409
    assert "requires APPROVED to execute" in res.json()["detail"]


def test_remediation_tampered_parameter_hash_rejection(test_client):
    """Tampering with proposal immutable parameters fails execution integrity validation."""
    db = TestingSessionLocal()
    user, org, _ = create_user_and_tenant(db, "admin@test.com", "admin")
    svc = create_target_service(db, org.id, "shop-api", "staging")
    proposal, approval = create_proposal_and_approve(db, org.id, svc.id, user.id, "staging")

    # Malicious direct modification of parameters in DB
    proposal.immutable_parameters = {"service_name": "malicious-injected-service"}
    db.commit()

    headers = login_client(test_client, "admin@test.com")
    res = test_client.post(f"/api/v1/actions/proposals/{proposal.id}/execute", headers=headers)
    assert res.status_code == 400
    assert "tampering detected" in res.json()["detail"].lower()


@patch("apps.api.app.actions.executor.RemediationExecutor._verify_health")
@patch("apps.api.app.actions.executor.RemediationExecutor._call_service")
def test_remediation_duplicate_execution_idempotency(
    mock_call_service, mock_verify_health, test_client
):
    """Duplicate execution requests return existing execution without running duplicate effects."""
    mock_call_service.return_value = {"status": "ok", "action": "restart_demo_service"}
    mock_verify_health.return_value = {"status": "ok", "fault_active": False}

    db = TestingSessionLocal()
    user, org, _ = create_user_and_tenant(db, "admin@test.com", "admin")
    svc = create_target_service(db, org.id, "shop-api", "staging")
    proposal, _ = create_proposal_and_approve(db, org.id, svc.id, user.id, "staging")

    headers = login_client(test_client, "admin@test.com")

    # First call
    res1 = test_client.post(f"/api/v1/actions/proposals/{proposal.id}/execute", headers=headers)
    assert res1.status_code == 200
    exec_id_1 = res1.json()["id"]

    # Second call (replay / duplicate)
    res2 = test_client.post(f"/api/v1/actions/proposals/{proposal.id}/execute", headers=headers)
    assert res2.status_code == 200
    exec_id_2 = res2.json()["id"]

    # Same execution ID returned; side effect called only once
    assert exec_id_1 == exec_id_2
    assert mock_call_service.call_count == 1


# ---------------------------------------------------------------------------
# GOOGLE ADK INTEGRATION (Workstream G)
# ---------------------------------------------------------------------------


def test_adk_agent_proposal_creation_tool():
    """create_remediation_proposal creates proposal in PROPOSED state with zero execution."""
    db = TestingSessionLocal()
    user, org, _ = create_user_and_tenant(db, "admin@test.com", "admin")
    svc = create_target_service(db, org.id, "shop-api", "staging")

    incident = Incident(
        organization_id=org.id,
        service_id=svc.id,
        title="High error rate on shop-api",
        severity="SEV-2",
        status="open",
        environment="staging",
        fingerprint="fp-test-adk",
        started_at=datetime.now(UTC),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    from apps.api.app.schemas import Scope

    scope = Scope(
        organization_id=org.id,
        service_id=svc.id,
        run_id=uuid.uuid4(),
    )

    gateway = ReadOnlyToolGateway(
        scope=scope,
        db_session=db,
        incident=incident,
    )

    # Agent calls create_remediation_proposal
    res = gateway.create_remediation_proposal(
        action_catalog_id="restart_demo_service",
        parameters={"service_name": "shop-api", "reason": "Checkout 500 error cascade detected"},
        reason="Checkout 500 error cascade detected",
        expected_outcome="Restore healthy container process",
    )

    assert res["status"] == "PROPOSED"
    proposal_id = uuid.UUID(res["proposal_id"])

    # Verify database state
    db_proposal = db.query(ActionProposal).filter_by(id=proposal_id).first()
    assert db_proposal is not None
    assert db_proposal.status == "PROPOSED"
    assert db_proposal.environment == "staging"

    # Crucial security verification: ZERO ActionExecution records exist!
    assert db.query(ActionExecution).filter_by(proposal_id=proposal_id).count() == 0
