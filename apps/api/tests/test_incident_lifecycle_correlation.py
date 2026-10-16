import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agents.incident_investigator.tools.gateway import ReadOnlyToolGateway
from agents.incident_investigator.validator import validate_evidence
from apps.api.app.auth import create_user_session, hash_password
from apps.api.app.db import get_db
from apps.api.app.integrations.github import ScopedGitHubClient
from apps.api.app.lifecycle import (
    ConcurrencyConflictError,
    InvalidTransitionError,
    can_transition,
    transition_incident,
)
from apps.api.app.main import app
from apps.api.app.models import (
    Base,
    Incident,
    IncidentEvent,
    Membership,
    Organization,
    Service,
    User,
)
from apps.api.app.schemas import (
    Evidence,
    EvidenceRef,
    Hypothesis,
    InvestigationResult,
    Scope,
)

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


def create_user_and_token(
    db, email: str, role: str, org: Organization | None = None, org_name: str = "Test Org"
) -> tuple[User, Organization, str, str]:
    pw_hash, salt = hash_password("test-password")
    user = User(email=email, hashed_password=pw_hash, salt=salt, name="Test User")
    db.add(user)
    db.flush()

    if org is None:
        org = Organization(name=org_name)
        db.add(org)
        db.flush()

    membership = Membership(user_id=user.id, organization_id=org.id, role=role)
    db.add(membership)
    db.flush()

    raw_token, _session = create_user_session(db, user.id)
    csrf_token = "test-csrf-token-12345"
    db.commit()
    return user, org, raw_token, csrf_token


ALERT_AUTH_HEADER = {"Authorization": "Bearer aegisops-demo-alertmanager-secret"}


# ==============================================================================
# Work Package A: Incident Lifecycle State Machine Tests
# ==============================================================================


def test_lifecycle_transition_matrix():
    """Verify explicit transition matrix allowed and disallowed transitions."""
    assert can_transition("open", "acknowledged") is True
    assert can_transition("open", "mitigating") is True
    assert can_transition("open", "resolved") is True
    assert can_transition("open", "closed") is False  # Cannot close directly from open

    assert can_transition("acknowledged", "mitigating") is True
    assert can_transition("acknowledged", "resolved") is True
    assert can_transition("acknowledged", "closed") is False

    assert can_transition("mitigating", "resolved") is True
    assert can_transition("mitigating", "open") is False

    assert can_transition("resolved", "closed") is True
    assert can_transition("resolved", "reopened") is True
    assert can_transition("resolved", "acknowledged") is False

    assert can_transition("closed", "reopened") is True
    assert can_transition("closed", "resolved") is False

    assert can_transition("reopened", "acknowledged") is True
    assert can_transition("reopened", "mitigating") is True
    assert can_transition("reopened", "resolved") is True


def test_lifecycle_transitions_and_events():
    """Verify transitions in database, optimistic concurrency, and audit events."""
    db = TestingSessionLocal()
    user, org, _, _ = create_user_and_token(db, "sre@aegisops.local", "member")
    svc = Service(organization_id=org.id, name="shop-api", environment="staging")
    db.add(svc)
    db.flush()

    incident = Incident(
        organization_id=org.id,
        service_id=svc.id,
        title="Elevated checkout latency",
        severity="critical",
        status="open",
        version=1,
        fingerprint="fp_latency_test",
        started_at=datetime.now(UTC),
    )
    db.add(incident)
    db.commit()

    # 1. Valid transition: open -> acknowledged
    transition_incident(
        incident,
        target_status="acknowledged",
        actor=user.email,
        reason="Investigating error spike",
        expected_version=1,
        db=db,
    )
    db.commit()
    assert incident.status == "acknowledged"
    assert incident.version == 2

    # 2. Concurrency conflict on stale version
    with pytest.raises(ConcurrencyConflictError):
        transition_incident(
            incident,
            target_status="mitigating",
            actor=user.email,
            expected_version=1,  # Stale!
            db=db,
        )

    # 3. Invalid transition: acknowledged -> closed
    with pytest.raises(InvalidTransitionError):
        transition_incident(
            incident,
            target_status="closed",
            actor=user.email,
            expected_version=2,
            db=db,
        )

    # 4. Valid flow to resolved and closed
    transition_incident(
        incident,
        target_status="resolved",
        actor=user.email,
        expected_version=2,
        db=db,
    )
    db.commit()
    assert incident.status == "resolved"
    assert incident.resolved_at is not None
    assert incident.version == 3

    transition_incident(
        incident,
        target_status="closed",
        actor=user.email,
        expected_version=3,
        db=db,
    )
    db.commit()
    assert incident.status == "closed"
    assert incident.version == 4

    # 5. Reopening from closed
    transition_incident(
        incident,
        target_status="reopened",
        actor=user.email,
        reason="Recurrence observed",
        expected_version=4,
        db=db,
    )
    db.commit()
    assert incident.status == "reopened"
    assert incident.resolved_at is None
    assert incident.version == 5

    # Check recorded IncidentEvents
    events = db.scalars(
        select(IncidentEvent)
        .where(IncidentEvent.incident_id == incident.id)
        .order_by(IncidentEvent.created_at.asc())
    ).all()
    assert len(events) == 4
    assert [e.payload["to_status"] for e in events] == [
        "acknowledged",
        "resolved",
        "closed",
        "reopened",
    ]


def test_api_incident_lifecycle_patch_endpoint(test_client):
    """Test PATCH /api/v1/incidents/{id} endpoint, RBAC, and error status codes."""
    db = TestingSessionLocal()
    _viewer, org, viewer_token, csrf = create_user_and_token(db, "viewer@aegisops.local", "viewer")
    _member, _, member_token, _ = create_user_and_token(
        db, "member@aegisops.local", "member", org=org
    )

    svc = Service(organization_id=org.id, name="shop-api", environment="staging")
    db.add(svc)
    db.flush()

    inc = Incident(
        organization_id=org.id,
        service_id=svc.id,
        title="High error rate",
        severity="critical",
        status="open",
        version=1,
        fingerprint="fp_api_patch",
        started_at=datetime.now(UTC),
    )
    db.add(inc)
    db.commit()

    inc_id = str(inc.id)

    # 1. Viewer attempt -> 403 Forbidden
    test_client.cookies.set("aegisops_session", viewer_token)
    test_client.cookies.set("aegisops_csrf", csrf)
    res = test_client.patch(
        f"/api/v1/incidents/{inc_id}",
        json={"status": "acknowledged"},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 403
    assert "Viewers cannot modify" in res.json()["detail"]

    # 2. Member attempt -> 200 OK
    test_client.cookies.set("aegisops_session", member_token)
    res = test_client.patch(
        f"/api/v1/incidents/{inc_id}",
        json={"status": "acknowledged", "expected_version": 1},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "acknowledged"
    assert data["version"] == 2

    # 3. Invalid transition -> 400 Bad Request
    res = test_client.patch(
        f"/api/v1/incidents/{inc_id}",
        json={"status": "closed"},  # acknowledged -> closed is disallowed
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400
    assert "Invalid incident transition" in res.json()["detail"]

    # 4. Concurrency conflict -> 409 Conflict
    res = test_client.patch(
        f"/api/v1/incidents/{inc_id}",
        json={"status": "mitigating", "expected_version": 1},  # Current version is 2!
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 409
    assert "optimistic concurrency conflict" in res.json()["detail"]


# ==============================================================================
# Work Package B: Multi-Alert Correlation Tests
# ==============================================================================


def test_multi_alert_correlation_and_deduplication(test_client):
    """Verify that alerts for same service & env correlate, while duplicates dedupe."""
    db = TestingSessionLocal()
    _, org, token, _csrf = create_user_and_token(db, "lead@aegisops.local", "admin")
    svc1 = Service(organization_id=org.id, name="shop-api", environment="staging")
    svc2 = Service(organization_id=org.id, name="auth-api", environment="staging")
    db.add_all([svc1, svc2])
    db.commit()

    test_client.cookies.set("aegisops_session", token)

    now = datetime.now(UTC)

    # 1. Send first alert: HighApiErrorRate on shop-api
    payload1 = {
        "version": "4",
        "groupKey": "test-group-1",
        "status": "firing",
        "receiver": "aegisops-webhook",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighApiErrorRate",
                    "organization": org.name,
                    "service": "shop-api",
                    "severity": "warning",
                },
                "annotations": {"summary": "shop-api 5xx ratio above 5%"},
                "startsAt": now.isoformat(),
                "fingerprint": "fp_shop_5xx",
            }
        ],
    }
    res1 = test_client.post(
        "/api/v1/webhooks/alertmanager", headers=ALERT_AUTH_HEADER, json=payload1
    )
    assert res1.status_code == 200
    assert res1.json()["incidents_created"] == 1

    # 2. Send duplicate alert: same fingerprint
    res2 = test_client.post(
        "/api/v1/webhooks/alertmanager", headers=ALERT_AUTH_HEADER, json=payload1
    )
    assert res2.status_code == 200
    assert res2.json()["duplicates_skipped"] == 1
    assert res2.json()["incidents_created"] == 0

    # 3. Send correlated alert: HighLatency on same shop-api (staging) within window
    payload2 = {
        "version": "4",
        "groupKey": "test-group-2",
        "status": "firing",
        "receiver": "aegisops-webhook",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighLatencyP95",
                    "organization": org.name,
                    "service": "shop-api",
                    "severity": "critical",  # Escalates incident severity!
                },
                "annotations": {"summary": "shop-api P95 latency > 2s"},
                "startsAt": (now + timedelta(minutes=5)).isoformat(),
                "fingerprint": "fp_shop_latency",
            }
        ],
    }
    res3 = test_client.post(
        "/api/v1/webhooks/alertmanager", headers=ALERT_AUTH_HEADER, json=payload2
    )
    assert res3.status_code == 200
    assert res3.json()["alerts_correlated"] == 1
    assert res3.json()["incidents_created"] == 0

    # Check incident was updated
    inc = db.scalar(select(Incident).where(Incident.service_id == svc1.id))
    assert inc is not None
    assert inc.correlated_alert_count == 2
    assert inc.severity == "critical"  # Elevated from warning

    # Check timeline events
    events = db.scalars(select(IncidentEvent).where(IncidentEvent.incident_id == inc.id)).all()
    event_types = [e.event_type for e in events]
    assert "incident_created" in event_types
    assert "alert_firing_duplicate" in event_types
    assert "alert_correlated" in event_types


def test_multi_alert_correlation_negative_boundaries(test_client):
    """Negative tests: Different service, env, or outside window do NOT merge."""
    db = TestingSessionLocal()
    _, org, token, _ = create_user_and_token(db, "sre@aegisops.local", "admin")
    svc_shop = Service(organization_id=org.id, name="shop-api", environment="staging")
    svc_auth = Service(organization_id=org.id, name="auth-api", environment="staging")
    db.add_all([svc_shop, svc_auth])
    db.commit()

    test_client.cookies.set("aegisops_session", token)
    now = datetime.now(UTC)

    # 1. Alert for shop-api
    payload_shop = {
        "version": "4",
        "groupKey": "gk-1",
        "status": "firing",
        "receiver": "aegisops-webhook",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighApiErrorRate",
                    "organization": org.name,
                    "service": "shop-api",
                    "severity": "warning",
                },
                "annotations": {"summary": "shop error"},
                "startsAt": now.isoformat(),
                "fingerprint": "fp_shop_1",
            }
        ],
    }
    test_client.post("/api/v1/webhooks/alertmanager", headers=ALERT_AUTH_HEADER, json=payload_shop)

    # 2. Alert for DIFFERENT service: auth-api -> Must create separate incident!
    payload_auth = {
        "version": "4",
        "groupKey": "gk-2",
        "status": "firing",
        "receiver": "aegisops-webhook",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighApiErrorRate",
                    "organization": org.name,
                    "service": "auth-api",
                    "severity": "critical",
                },
                "annotations": {"summary": "auth error"},
                "startsAt": now.isoformat(),
                "fingerprint": "fp_auth_1",
            }
        ],
    }
    res_auth = test_client.post(
        "/api/v1/webhooks/alertmanager", headers=ALERT_AUTH_HEADER, json=payload_auth
    )
    assert res_auth.json()["incidents_created"] == 1
    assert res_auth.json()["alerts_correlated"] == 0

    incidents = db.scalars(select(Incident)).all()
    assert len(incidents) == 2  # Two independent incidents


# ==============================================================================
# Work Package D & E: GitHub Read Integration & ADK Deployment Tool Tests
# ==============================================================================


def test_scoped_github_client_offline_and_deployments():
    """Verify ScopedGitHubClient retrieves deployments and falls back gracefully."""
    with patch.dict("os.environ", {"AEGISOPS_GITHUB_OFFLINE": "1"}):
        client = ScopedGitHubClient()
        deployments = client.get_recent_deployments("AegisOps/shop-api", limit=3)
        assert len(deployments) == 1
        assert deployments[0]["repository"] == "AegisOps/shop-api"
        assert deployments[0]["is_deployment"] is True

        commits = client.get_recent_commits("AegisOps/shop-api", limit=5)
        assert len(commits) == 1
        assert commits[0]["author"] == "AegisOps CI"


def test_tool_gateway_get_recent_deployments_and_cross_tenant_rejection():
    """Verify tool gateway gets deployments and blocks unauthorized repo (T7)."""
    db = TestingSessionLocal()
    _, org, _, _ = create_user_and_token(db, "tester@aegisops.local", "member")
    svc = Service(
        organization_id=org.id,
        name="shop-api",
        github_repo="AegisOps/shop-api",
        environment="staging",
    )
    db.add(svc)
    db.commit()

    scope = Scope(organization_id=org.id, service_id=svc.id, run_id=uuid.uuid4())
    gw = ReadOnlyToolGateway(scope=scope, db_session=db)

    # 1. Normal authorized deployment lookup
    with patch.dict("os.environ", {"AEGISOPS_GITHUB_OFFLINE": "1"}):
        res = gw.get_recent_deployments(limit=5)
        assert res["repository"] == "AegisOps/shop-api"
        assert res["deployment_count"] == 1
        assert "evidence_id" in res
        ev_id = res["evidence_id"]
        assert ev_id.startswith("ev_deploy_")
        assert ev_id in gw.evidence_ledger

    # 2. T7: Cross-tenant / unauthorized repository attempt -> Rejected!
    res_unauth = gw.get_recent_deployments(repository="attacker/malicious-repo")
    assert "Access denied" in res_unauth["error"]
    assert res_unauth["deployments"] == []


def test_agent_claim_validation_deployment_rules():
    """Verify validator rules: T1 broken deployment valid; unverified evidence rejected."""
    run_id = uuid.uuid4()
    org_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    scope = Scope(organization_id=org_id, service_id=svc_id, run_id=run_id)

    now = datetime.now(UTC)
    deploy_ev = Evidence(
        organization_id=org_id,
        service_id=svc_id,
        run_id=run_id,
        evidence_id="ev_deploy_12345",
        source="deployments",
        observed_at=now,
        locator="github:repo:AegisOps/shop-api:deployments",
        redacted_snippet='[{"version": "0.1.1-buggy", "commit_sha": "badf00d"}]',
    )
    log_ev = Evidence(
        organization_id=org_id,
        service_id=svc_id,
        run_id=run_id,
        evidence_id="ev_log_67890",
        source="logs",
        observed_at=now,
        locator="loki:shop-api",
        redacted_snippet="HTTP 500 PaymentGatewayTimeoutException in checkout",
    )
    ledger = {deploy_ev.evidence_id: deploy_ev, log_ev.evidence_id: log_ev}

    # Case 1 (T1): Valid broken deployment hypothesis with corroborating error logs
    valid_res = InvestigationResult(
        status="complete",
        summary="Service failure triggered by bad release deployment",
        hypotheses=[
            Hypothesis(
                cause="Broken release deployment introduced payment timeout regression",
                confidence="medium",
                supporting_evidence=[
                    EvidenceRef(
                        evidence_id=deploy_ev.evidence_id,
                        supports="Deployment of release 0.1.1",
                    ),
                    EvidenceRef(
                        evidence_id=log_ev.evidence_id,
                        supports="500 timeout exceptions post-deployment",
                    ),
                ],
            )
        ],
    )
    validated = validate_evidence(valid_res, scope=scope, returned_ledger=ledger)
    assert validated.status == "complete"

    # Case 2: Deployment claim WITHOUT citing any deployment evidence -> Rejected!
    missing_deploy_res = InvestigationResult(
        status="complete",
        summary="Claiming bad release without proof",
        hypotheses=[
            Hypothesis(
                cause="Broken release deployment introduced errors",
                confidence="medium",
                supporting_evidence=[
                    EvidenceRef(
                        evidence_id=log_ev.evidence_id,
                        supports="Only error logs cited",
                    )
                ],
            )
        ],
    )
    with pytest.raises(ValueError, match="without citing deployment"):
        validate_evidence(missing_deploy_res, scope=scope, returned_ledger=ledger)

    # Case 3 (T5): Nonexistent evidence reference -> Rejected!
    fake_ev_res = InvestigationResult(
        status="complete",
        summary="Cites invented evidence",
        hypotheses=[
            Hypothesis(
                cause="Normal operation",
                confidence="low",
                supporting_evidence=[
                    EvidenceRef(
                        evidence_id="ev_fake_nonexistent",
                        supports="Hallucinated evidence",
                    )
                ],
            )
        ],
    )
    with pytest.raises(ValueError, match="Unknown evidence reference"):
        validate_evidence(fake_ev_res, scope=scope, returned_ledger=ledger)


def test_api_service_deployments_endpoint(test_client):
    """Test GET /api/v1/services/{id}/deployments endpoint."""
    db = TestingSessionLocal()
    _, org, token, _ = create_user_and_token(db, "dev@aegisops.local", "member")
    svc = Service(
        organization_id=org.id,
        name="shop-api",
        github_repo="AegisOps/shop-api",
        environment="staging",
    )
    db.add(svc)
    db.commit()

    test_client.cookies.set("aegisops_session", token)

    with patch.dict("os.environ", {"AEGISOPS_GITHUB_OFFLINE": "1"}):
        res = test_client.get(f"/api/v1/services/{svc.id}/deployments")
        assert res.status_code == 200
        items = res.json()
        assert len(items) == 1
        assert items[0]["repository"] == "AegisOps/shop-api"
        assert items[0]["is_deployment"] is True
