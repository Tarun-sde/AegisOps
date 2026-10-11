import hashlib
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agents.incident_investigator.investigator import execute_investigation
from apps.api.app.auth import create_user_session
from apps.api.app.db import get_db
from apps.api.app.main import app
from apps.api.app.models import (
    Base,
    EvidenceItem,
    Incident,
    InvestigationRun,
    Membership,
    Organization,
    Service,
    ToolExecution,
    User,
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
    with TestingSessionLocal() as db:
        org = Organization(name="AegisOps Demo")
        db.add(org)
        db.flush()
        user = User(
            email="demo@aegisops.local",
            hashed_password="hash",
            salt="salt",
            name="Demo User",
            is_active=True,
        )
        db.add(user)
        db.flush()
        membership = Membership(
            user_id=user.id,
            organization_id=org.id,
            role="owner",
        )
        db.add(membership)
        svc = Service(organization_id=org.id, name="shop-api")
        db.add(svc)
        raw_token, _ = create_user_session(db, user.id)
        client.cookies.set("aegisops_session", raw_token)
        db.commit()

    yield

    client.cookies.clear()
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app)


def create_test_incident(db) -> Incident:
    svc = db.query(Service).filter(Service.name == "shop-api").first()
    inc = Incident(
        organization_id=svc.organization_id,
        service_id=svc.id,
        fingerprint=f"fp-{uuid.uuid4().hex[:8]}",
        title="High error rate in shop-api",
        severity="critical",
        status="firing",
        started_at=datetime.now(UTC),
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc


def test_start_investigation_endpoint():
    with TestingSessionLocal() as db:
        inc = create_test_incident(db)
        incident_id = str(inc.id)

    with patch("apps.worker.tasks.run_investigation_task.delay") as mock_delay:
        resp = client.post(f"/api/v1/incidents/{incident_id}/investigations")
        assert resp.status_code == 201
        data = resp.json()
        assert data["incident_id"] == incident_id
        assert data["status"] == "QUEUED"
        assert "id" in data
        mock_delay.assert_called_once_with(data["id"])


def test_start_investigation_not_found():
    random_id = str(uuid.uuid4())
    resp = client.post(f"/api/v1/incidents/{random_id}/investigations")
    assert resp.status_code == 404


def test_get_investigation_details_and_cancellation():
    with TestingSessionLocal() as db:
        inc = create_test_incident(db)
        run = InvestigationRun(
            incident_id=inc.id,
            organization_id=inc.organization_id,
            service_id=inc.service_id,
            status="QUEUED",
            model="gemini-3.5-flash",
            prompt_version="phase2-v1",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = str(run.id)

    # 1. Fetch details
    resp = client.get(f"/api/v1/investigations/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == run_id
    assert data["status"] == "QUEUED"

    # 2. Cancel
    cancel_resp = client.post(f"/api/v1/investigations/{run_id}/cancel")
    assert cancel_resp.status_code == 200
    cancel_data = cancel_resp.json()
    assert cancel_data["status"] == "CANCELLED"

    # 3. Confirm cancelled status persisted
    get_resp = client.get(f"/api/v1/investigations/{run_id}")
    assert get_resp.json()["status"] == "CANCELLED"


def test_get_investigation_events_and_evidence():
    with TestingSessionLocal() as db:
        inc = create_test_incident(db)
        run = InvestigationRun(
            incident_id=inc.id,
            organization_id=inc.organization_id,
            service_id=inc.service_id,
            status="COMPLETE",
            model="gemini-3.5-flash",
            prompt_version="phase2-v1",
        )
        db.add(run)
        db.flush()

        tool_exec = ToolExecution(
            run_id=run.id,
            tool_name="query_service_metrics",
            arguments={"metric_name": "http_5xx_error_rate"},
            status="success",
            latency_ms=12.5,
        )
        db.add(tool_exec)

        ev_item = EvidenceItem(
            evidence_id="ev_metric_12345678",
            run_id=run.id,
            organization_id=inc.organization_id,
            service_id=inc.service_id,
            source="metrics",
            observed_at=datetime.now(UTC),
            locator="prometheus:http_5xx_error_rate",
            redacted_snippet="5xx error rate: 0.15",
            content_hash="abc123hash",
            query_metadata={"metric": "http_5xx_error_rate"},
        )
        db.add(ev_item)
        db.commit()
        run_id = str(run.id)
        evidence_id = ev_item.evidence_id

    # Get events
    events_resp = client.get(f"/api/v1/investigations/{run_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()
    assert len(events) == 1
    assert events[0]["tool_name"] == "query_service_metrics"

    # Get evidence list
    ev_list_resp = client.get(f"/api/v1/investigations/{run_id}/evidence")
    assert ev_list_resp.status_code == 200
    ev_list = ev_list_resp.json()
    assert ev_list["total"] == 1
    assert ev_list["items"][0]["evidence_id"] == evidence_id

    # Get single evidence item
    ev_item_resp = client.get(f"/api/v1/evidence/{evidence_id}")
    assert ev_item_resp.status_code == 200
    assert ev_item_resp.json()["evidence_id"] == evidence_id


@pytest.mark.parametrize(
    "telemetry_http,expected",
    [("supported", "COMPLETE"), ("empty", "INCONCLUSIVE"), ("unavailable", "INCONCLUSIVE")],
    indirect=["telemetry_http"],
)
def test_execute_investigation_lifecycle_offline(telemetry_http, expected):
    with TestingSessionLocal() as db:
        inc = create_test_incident(db)
        run = InvestigationRun(
            incident_id=inc.id,
            organization_id=inc.organization_id,
            service_id=inc.service_id,
            status="QUEUED",
            model="gemini-3.5-flash",
            prompt_version="phase2-v1",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

        # Execute investigation with offline deterministic agent
        finished_run = execute_investigation(
            run_id,
            db,
            use_live_model=False,
            scenario="supported",
        )

        assert finished_run.status == expected
        assert finished_run.summary is not None
        assert finished_run.tool_call_count == 3
        assert finished_run.execution_mode == "offline"
        assert finished_run.provider == "offline"
        assert telemetry_http.call_count == 2
        evidence = db.query(EvidenceItem).filter_by(run_id=run_id).all()
        executions = db.query(ToolExecution).filter_by(run_id=run_id).all()
        assert len(executions) == 3
        for item in evidence:
            assert item.organization_id == inc.organization_id
            assert item.service_id == inc.service_id
            assert item.content_hash == hashlib.sha256(item.redacted_snippet.encode()).hexdigest()
        if expected == "COMPLETE":
            assert len(finished_run.hypotheses) == 1
            hypothesis = finished_run.hypotheses[0]
            assert hypothesis.confidence == "high"
            assert "payment processing gateway timeout" in hypothesis.cause
            assert {item.source for item in evidence} == {"alert", "metrics", "logs"}
            assert all(item.status == "success" for item in executions)
            cited_ids = {ref["evidence_id"] for ref in hypothesis.supporting_evidence}
            assert cited_ids <= {item.evidence_id for item in evidence}
            assert {item.source for item in evidence if item.evidence_id in cited_ids} == {
                "metrics",
                "logs",
            }
            metric = next(item for item in evidence if item.source == "metrics")
            assert metric.locator == "promql:http_5xx_error_rate"
            assert metric.query_metadata["window_minutes"] == 15
            log = next(item for item in evidence if item.source == "logs")
            assert "CHECKOUT_GATEWAY_TIMEOUT" in log.redacted_snippet
            assert "APPLICATION_EXCEPTION" in log.redacted_snippet
        else:
            assert finished_run.hypotheses == []
            assert finished_run.missing_evidence
            if any(item.status == "error" for item in executions):
                assert {item.source for item in evidence} == {"alert"}
                assert {item.error_category for item in executions if item.status == "error"} == {
                    "PROMETHEUS_UNAVAILABLE",
                    "LOKI_UNAVAILABLE",
                }

        # Verify idempotency: re-running does not re-investigate
        rerun = execute_investigation(run_id, db)
        assert rerun.status == expected
        assert telemetry_http.call_count == 2
        assert db.query(EvidenceItem).filter_by(run_id=run_id).count() == len(evidence)
        assert db.query(ToolExecution).filter_by(run_id=run_id).count() == 3
