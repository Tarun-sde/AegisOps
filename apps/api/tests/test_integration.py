import concurrent.futures
import os
import threading
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api.app.actions.service import ProposalService, compute_parameters_hash
from apps.api.app.auth import TenantContext
from apps.api.app.db import SessionLocal
from apps.api.app.main import app
from apps.api.app.models import (
    ActionExecution,
    ActionProposal,
    Organization,
    OutboxEvent,
    ProposalApproval,
    Service,
    SimulationEvent,
    SimulationRun,
    User,
)
from apps.api.app.outbox.dispatcher import dispatch_outbox_batch
from apps.worker.tasks import reconcile_simulation_expiry_task

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("AEGISOPS_INTEGRATION") != "1", reason="Use isolated Compose verify service"
    ),
]


def test_migration_round_trip_and_database_constraints():
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "aegisops_phase0_verify",
        ), "Migration round-trip requires the dedicated verification database"
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        org_id = uuid4()
        service_id = uuid4()
        with connection.transaction(force_rollback=True):
            connection.execute(
                "INSERT INTO organizations (id,name) VALUES (%s,%s)", (org_id, "Synthetic test")
            )
            connection.execute(
                "INSERT INTO services (id,organization_id,name) VALUES (%s,%s,%s)",
                (service_id, org_id, "shop-api"),
            )
            assert connection.execute(
                "SELECT organization_id FROM services WHERE id=%s", (service_id,)
            ).fetchone() == (org_id,)
            with pytest.raises(psycopg.errors.ForeignKeyViolation), connection.transaction():
                connection.execute(
                    "INSERT INTO services (id,organization_id,name) VALUES (%s,%s,%s)",
                    (uuid4(), uuid4(), "alien"),
                )
            with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
                connection.execute(
                    "INSERT INTO services (id,organization_id,name) VALUES (%s,%s,%s)",
                    (uuid4(), org_id, "shop-api"),
                )

            # Phase 1: Test incidents and unique constraint for open status
            inc1_id = uuid4()
            connection.execute(
                """
                INSERT INTO incidents (
                    id, organization_id, service_id, title,
                    severity, status, fingerprint, started_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    inc1_id,
                    org_id,
                    service_id,
                    "High error rate",
                    "critical",
                    "open",
                    "fp-1",
                    datetime.now(UTC),
                ),
            )

            # Second open incident with same fingerprint must violate partial unique index
            with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
                connection.execute(
                    """
                    INSERT INTO incidents (
                        id, organization_id, service_id, title,
                    severity, status, fingerprint, started_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        uuid4(),
                        org_id,
                        service_id,
                        "Duplicate alert",
                        "critical",
                        "open",
                        "fp-1",
                        datetime.now(UTC),
                    ),
                )
            # Transition first incident to acknowledged
            connection.execute(
                "UPDATE incidents SET status='acknowledged' WHERE id=%s",
                (inc1_id,),
            )
            # Acknowledged incident with same fingerprint must also reject duplicate
            # incident via uq_active_incident_fingerprint
            with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
                connection.execute(
                    """
                    INSERT INTO incidents (
                        id, organization_id, service_id, title,
                        severity, status, fingerprint, started_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        uuid4(),
                        org_id,
                        service_id,
                        "Duplicate while acknowledged",
                        "critical",
                        "open",
                        "fp-1",
                        datetime.now(UTC),
                    ),
                )

            # Incident events foreign key constraint
            event_id = uuid4()
            connection.execute(
                """
                INSERT INTO incident_events (
                    id, incident_id, event_type, actor, occurred_at, payload
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    event_id,
                    inc1_id,
                    "incident_created",
                    "alertmanager",
                    datetime.now(UTC),
                    '{"test": true}',
                ),
            )

            with pytest.raises(psycopg.errors.ForeignKeyViolation), connection.transaction():
                connection.execute(
                    """
                    INSERT INTO incident_events (
                        id, incident_id, event_type, actor, occurred_at, payload
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (uuid4(), uuid4(), "incident_created", "alertmanager", datetime.now(UTC), "{}"),
                )

        assert (
            connection.execute("SELECT id FROM organizations WHERE id=%s", (org_id,)).fetchone()
            is None
        )
        assert connection.execute(
            "SELECT default_version FROM pg_available_extensions WHERE name='vector'"
        ).fetchone() == ("0.8.7",)
    # This command is for a dedicated disposable verification project, never an operator database.
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_real_dependency_readiness():
    with TestClient(app) as client:
        response = client.get("/readyz")
        assert response.status_code == 200, response.text
        assert response.json()["checks"] == {"postgres": "ok", "redis": "ok"}


def test_postgres_concurrency_remediation_proposal_claim():
    """Two concurrent workers attempting to claim the same remediation proposal.
    Exactly one must succeed; the other must fail or no-op, and the unique
    constraint on action_executions(proposal_id) must hold.
    """
    db = SessionLocal()
    try:
        org_id = uuid4()
        user_id = uuid4()
        service_id = uuid4()
        proposal_id = uuid4()

        org = Organization(id=org_id, name="Concurrency Claim Org")
        user = User(
            id=user_id,
            email=f"admin-{user_id}@concurrency.test",
            hashed_password="hash",
            salt="salt",
            name="Admin Tester",
        )
        service = Service(
            id=service_id,
            organization_id=org_id,
            name="shop-api",
            environment="staging",
        )
        params = {"service_name": "shop-api", "grace_period_seconds": 10}
        p_hash = compute_parameters_hash(params)

        proposal = ActionProposal(
            id=proposal_id,
            organization_id=org_id,
            service_id=service_id,
            action_catalog_id="restart_demo_service",
            environment="staging",
            immutable_parameters=params,
            parameters_hash=p_hash,
            reason="Test concurrency claim",
            expected_outcome="Service restarted",
            known_risks="Momentary drop in traffic during restart",
            status="APPROVED",
            idempotency_key=f"prop-concurrency-{proposal_id}",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        approval = ProposalApproval(
            proposal_id=proposal_id,
            organization_id=org_id,
            approver_id=user_id,
            decision="APPROVED",
            parameters_hash=p_hash,
            comment="Approved for concurrency test",
        )
        db.add_all([org, user, service, proposal, approval])
        db.commit()
    finally:
        db.close()

    barrier = threading.Barrier(2)

    def worker_claim(worker_index: int):
        thread_db = SessionLocal()
        try:
            thread_org = thread_db.get(Organization, org_id)
            thread_user = thread_db.get(User, user_id)
            ctx = TenantContext(user=thread_user, organization=thread_org, role="admin")
            svc = ProposalService(thread_db, ctx)

            barrier.wait(timeout=10)
            exec_record = svc.execute_proposal(
                proposal_id=proposal_id,
                idempotency_key=f"worker-{worker_index}-{proposal_id}",
            )
            return {
                "success": True,
                "execution_id": str(exec_record.id),
                "status": exec_record.status,
            }
        except Exception as exc:
            return {"success": False, "error": type(exc).__name__, "message": str(exc)}
        finally:
            thread_db.close()

    with (
        patch("apps.api.app.actions.executor.RemediationExecutor._call_service") as mock_exec,
        patch("apps.api.app.actions.executor.RemediationExecutor._verify_health") as mock_health,
    ):
        mock_exec.return_value = {"status": "ok", "action": "restart_demo_service"}
        mock_health.return_value = {"status": "ok", "fault_active": False}

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker_claim, 1)
            f2 = executor.submit(worker_claim, 2)
            r1 = f1.result()
            r2 = f2.result()

    verify_db = SessionLocal()
    try:
        executions = verify_db.scalars(
            select(ActionExecution).where(ActionExecution.proposal_id == proposal_id)
        ).all()
        # Exactly one execution record exists in DB; unique constraint held
        assert len(executions) == 1, f"Expected exactly 1 execution record, got {len(executions)}"
        assert executions[0].status == "SUCCEEDED"

        successes = [r for r in [r1, r2] if r["success"]]
        assert len(successes) >= 1
        # If both returned an execution object, it must be the exact same one (idempotency)
        if len(successes) == 2:
            assert r1["execution_id"] == r2["execution_id"]
    finally:
        verify_db.close()


def test_postgres_concurrency_simulation_expiry_reconciliation():
    """Two concurrent workers running reconcile_simulation_expiry_task on the same expired run.
    The run must transition to EXPIRED exactly once, with no duplicate timeline events.
    """
    db = SessionLocal()
    try:
        org_id = uuid4()
        user_id = uuid4()
        service_id = uuid4()
        run_id = uuid4()

        org = Organization(id=org_id, name="Expiry Concurrency Org")
        user = User(
            id=user_id,
            email=f"expiry-{user_id}@concurrency.test",
            hashed_password="hash",
            salt="salt",
            name="Expiry Tester",
        )
        service = Service(
            id=service_id,
            organization_id=org_id,
            name="shop-api",
            environment="staging",
        )
        sim_run = SimulationRun(
            id=run_id,
            organization_id=org_id,
            service_id=service_id,
            scenario_id="S01_CHECKOUT_500",
            status="ACTIVE",
            environment="staging",
            cleanup_status="PENDING",
            expected_cause="PAYMENT_GATEWAY_TIMEOUT",
            expires_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        event = SimulationEvent(
            run_id=run_id,
            organization_id=org_id,
            event_type="simulation.started",
            actor="test",
            payload={"scenario": "S01_CHECKOUT_500"},
        )
        db.add_all([org, user, service, sim_run, event])
        db.commit()
    finally:
        db.close()

    barrier = threading.Barrier(2)

    def worker_reconcile():
        barrier.wait(timeout=10)
        return reconcile_simulation_expiry_task()

    with patch("apps.api.app.simulation.service.SimulationService._call_shop_api") as mock_shop:
        mock_shop.return_value = {"status": "ok", "fault_active": False}

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker_reconcile)
            f2 = executor.submit(worker_reconcile)
            res1 = f1.result()
            res2 = f2.result()

    verify_db = SessionLocal()
    try:
        updated_run = verify_db.get(SimulationRun, run_id)
        assert updated_run is not None
        assert updated_run.status == "EXPIRED"
        assert updated_run.cleanup_status == "CLEANED"

        events = verify_db.scalars(
            select(SimulationEvent).where(
                SimulationEvent.run_id == run_id,
                SimulationEvent.event_type == "simulation.expired",
            )
        ).all()
        # Exactly one expiry event, no duplicate timeline events
        assert len(events) == 1, f"Expected exactly 1 expiry timeline event, got {len(events)}"

        total_cleaned = res1.get("cleaned_expired_runs", 0) + res2.get("cleaned_expired_runs", 0)
        assert total_cleaned == 1, (
            f"Expected total 1 cleaned run across workers, got {total_cleaned}"
        )
    finally:
        verify_db.close()


def test_postgres_concurrency_outbox_batch_dispatch():
    """Two concurrent outbox dispatchers claiming the same outbox_events row.
    Each event must be delivered at most once per lease.
    """
    db = SessionLocal()
    try:
        # Clean up / deliver any pre-existing outbox events from earlier test lifecycle events
        db.query(OutboxEvent).filter(OutboxEvent.status.in_(["PENDING", "RETRY_SCHEDULED"])).update(
            {"status": "DELIVERED"}
        )
        db.commit()

        org_id = uuid4()
        org = Organization(id=org_id, name="Outbox Concurrency Org")
        ev_id = uuid4()
        outbox_ev = OutboxEvent(
            id=ev_id,
            organization_id=org_id,
            aggregate_type="incident",
            aggregate_id=str(uuid4()),
            event_type="incident.created",
            payload={"test": "concurrency"},
            idempotency_key=f"outbox-concurrency-{ev_id}",
            status="PENDING",
            next_attempt_at=datetime.now(UTC) - timedelta(seconds=10),
            attempt_count=0,
            max_attempts=5,
        )
        db.add_all([org, outbox_ev])
        db.commit()
    finally:
        db.close()

    barrier = threading.Barrier(2)

    def worker_dispatch():
        thread_db = SessionLocal()
        try:
            barrier.wait(timeout=10)
            return dispatch_outbox_batch(
                thread_db,
                batch_size=10,
                destination_url="http://127.0.0.1:8000/mock-sink",
                lease_seconds=60,
            )
        finally:
            thread_db.close()

    with patch("apps.api.app.outbox.dispatcher.urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = b'{"status": "ok"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker_dispatch)
            f2 = executor.submit(worker_dispatch)
            r1 = f1.result()
            r2 = f2.result()

    verify_db = SessionLocal()
    try:
        ev = verify_db.get(OutboxEvent, ev_id)
        assert ev is not None
        assert ev.status == "DELIVERED"
        assert ev.attempt_count == 1

        total_claimed = r1.get("claimed", 0) + r2.get("claimed", 0)
        total_delivered = r1.get("delivered", 0) + r2.get("delivered", 0)
        assert total_claimed == 1, f"Expected 1 total claimed event, got {total_claimed}"
        assert total_delivered == 1, f"Expected 1 total delivered event, got {total_delivered}"
    finally:
        verify_db.close()
