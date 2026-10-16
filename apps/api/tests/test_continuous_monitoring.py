from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.app.models import (
    Base,
    Incident,
    IncidentEvent,
    Organization,
    Service,
)
from apps.worker.tasks import probe_monitored_services_task

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    with patch("apps.worker.tasks.SessionLocal", TestingSessionLocal):
        yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def mock_public_dns():
    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
        yield mock_dns


def test_continuous_monitoring_lifecycle_and_recovery():
    with TestingSessionLocal() as db:
        org = Organization(name="Monitoring Org")
        db.add(org)
        db.flush()

        svc = Service(
            organization_id=org.id,
            name="IronLog-Worker-Target",
            environment="production",
            healthcheck_url="https://ironlog.example.com/api/health",
            is_monitored=True,
            monitoring_interval_seconds=10,
            failure_threshold=3,
            monitoring_status="unknown",
            last_verified_at=datetime.now(UTC) - timedelta(seconds=20),
        )
        db.add(svc)
        db.commit()
        svc_id = svc.id
        org_id = org.id

    # --- Probe 1: Cold start / Transient failure (Failure 1) ---
    with patch("apps.api.app.auth.get_ssrf_safe_opener") as mock_opener:
        mock_opener.return_value.open.side_effect = Exception("Cold start timeout")
        res1 = probe_monitored_services_task()
        assert res1["probed_services"] == 1

    with TestingSessionLocal() as db:
        svc = db.get(Service, svc_id)
        assert svc.monitoring_status == "degraded"
        assert svc.consecutive_failures == 1
        # Cold start must NOT create an incident yet
        incidents = db.scalars(select(Incident).where(Incident.service_id == svc_id)).all()
        assert len(incidents) == 0

    # --- Probe 2: Second transient failure (Failure 2) ---
    with TestingSessionLocal() as db:
        svc = db.get(Service, svc_id)
        svc.last_verified_at = datetime.now(UTC) - timedelta(seconds=20)
        db.commit()

    with patch("apps.api.app.auth.get_ssrf_safe_opener") as mock_opener:
        mock_opener.return_value.open.side_effect = Exception("Cold start still starting")
        res2 = probe_monitored_services_task()
        assert res2["probed_services"] == 1

    with TestingSessionLocal() as db:
        svc = db.get(Service, svc_id)
        assert svc.monitoring_status == "degraded"
        assert svc.consecutive_failures == 2
        incidents = db.scalars(select(Incident).where(Incident.service_id == svc_id)).all()
        assert len(incidents) == 0

    # --- Probe 3: Sustained Outage (Failure 3 >= threshold 3) ---
    with TestingSessionLocal() as db:
        svc = db.get(Service, svc_id)
        svc.last_verified_at = datetime.now(UTC) - timedelta(seconds=20)
        db.commit()

    with patch("apps.api.app.auth.get_ssrf_safe_opener") as mock_opener:
        mock_opener.return_value.open.side_effect = Exception("503 Service Unavailable")
        res3 = probe_monitored_services_task()
        assert res3["probed_services"] == 1

    with TestingSessionLocal() as db:
        svc = db.get(Service, svc_id)
        assert svc.monitoring_status == "down"
        assert svc.consecutive_failures == 3

        # Qualifying outage creates an incident!
        incidents = db.scalars(select(Incident).where(Incident.service_id == svc_id)).all()
        assert len(incidents) == 1
        incident = incidents[0]
        assert incident.status == "open"
        assert incident.severity == "critical"
        assert incident.organization_id == org_id
        assert "Service Outage" in incident.title

        events = db.scalars(
            select(IncidentEvent).where(IncidentEvent.incident_id == incident.id)
        ).all()
        assert len(events) == 1
        assert events[0].event_type == "created"
        assert events[0].actor == "system:healthcheck_monitor"

    # --- Probe 4: Deduplication check (Failure 4) ---
    with TestingSessionLocal() as db:
        svc = db.get(Service, svc_id)
        svc.last_verified_at = datetime.now(UTC) - timedelta(seconds=20)
        db.commit()

    with patch("apps.api.app.auth.get_ssrf_safe_opener") as mock_opener:
        mock_opener.return_value.open.side_effect = Exception("Still down")
        res4 = probe_monitored_services_task()
        assert res4["probed_services"] == 1

    with TestingSessionLocal() as db:
        svc = db.get(Service, svc_id)
        assert svc.monitoring_status == "down"
        assert svc.consecutive_failures == 4
        # Deduplication: No duplicate incident created
        incidents = db.scalars(select(Incident).where(Incident.service_id == svc_id)).all()
        assert len(incidents) == 1

    # --- Probe 5: Service Recovery (Success 200) ---
    with TestingSessionLocal() as db:
        svc = db.get(Service, svc_id)
        svc.last_verified_at = datetime.now(UTC) - timedelta(seconds=20)
        db.commit()

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("apps.api.app.auth.get_ssrf_safe_opener") as mock_opener:
        mock_opener.return_value.open.return_value = mock_resp
        res5 = probe_monitored_services_task()
        assert res5["probed_services"] == 1

    with TestingSessionLocal() as db:
        svc = db.get(Service, svc_id)
        assert svc.monitoring_status == "reachable"
        assert svc.consecutive_failures == 0
        assert svc.consecutive_successes == 1

        # Outage incident must be automatically resolved
        incidents = db.scalars(select(Incident).where(Incident.service_id == svc_id)).all()
        assert len(incidents) == 1
        incident = incidents[0]
        assert incident.status == "resolved"
        assert incident.resolved_at is not None

        events = db.scalars(
            select(IncidentEvent)
            .where(IncidentEvent.incident_id == incident.id)
            .order_by(IncidentEvent.occurred_at.asc())
        ).all()
        assert len(events) == 2
        assert events[1].event_type == "resolved"
        assert "Service recovered" in events[1].payload["message"]


def test_continuous_monitoring_skips_unexpired_intervals():
    with TestingSessionLocal() as db:
        org = Organization(name="Interval Org")
        db.add(org)
        db.flush()

        # Probed only 5 seconds ago with 60 second interval -> should be skipped
        svc = Service(
            organization_id=org.id,
            name="Unexpired-Service",
            environment="production",
            healthcheck_url="https://ironlog.example.com/api/health",
            is_monitored=True,
            monitoring_interval_seconds=60,
            last_verified_at=datetime.now(UTC) - timedelta(seconds=5),
        )
        db.add(svc)
        db.commit()

    res = probe_monitored_services_task()
    assert res["probed_services"] == 0


def test_lifecycle_failure_acknowledgement_continued_failure_recovery():
    """Reproduced audit scenario (Priority 1.5):

    - Three failures create an outage incident.
    - User acknowledges it.
    - Another failed probe occurs -> must NOT create a duplicate incident.
    - Service recovers -> resolves the acknowledged incident cleanly.
    """
    with TestingSessionLocal() as db:
        org = Organization(name="Ack Org")
        db.add(org)
        db.flush()

        svc = Service(
            organization_id=org.id,
            name="Ack-Service-Target",
            environment="production",
            healthcheck_url="https://ack.example.com/health",
            is_monitored=True,
            monitoring_interval_seconds=10,
            failure_threshold=3,
            monitoring_status="unknown",
            last_verified_at=datetime.now(UTC) - timedelta(seconds=20),
        )
        db.add(svc)
        db.commit()
        svc_id = svc.id

    # 1. Trigger 3 failures -> creates outage incident
    mock_fail = MagicMock()
    mock_fail.status = 503
    mock_fail.__enter__.return_value = mock_fail
    mock_fail.__exit__.return_value = False

    for _ in range(3):
        with TestingSessionLocal() as db:
            s = db.get(Service, svc_id)
            s.last_verified_at = datetime.now(UTC) - timedelta(seconds=20)
            db.commit()

        with patch("apps.api.app.auth.get_ssrf_safe_opener") as mock_opener:
            mock_opener.return_value.open.side_effect = Exception("HTTP 503 Outage")
            probe_monitored_services_task()

    with TestingSessionLocal() as db:
        svc = db.get(Service, svc_id)
        assert svc.monitoring_status == "down"
        assert svc.consecutive_failures == 3

        incidents = db.scalars(select(Incident).where(Incident.service_id == svc_id)).all()
        assert len(incidents) == 1
        inc = incidents[0]
        assert inc.status == "open"
        inc_id = inc.id

        # 2. User acknowledges the incident
        inc.status = "acknowledged"
        inc.updated_at = datetime.now(UTC)
        db.commit()

    # 3. Continued probe failure while incident is acknowledged
    with TestingSessionLocal() as db:
        s = db.get(Service, svc_id)
        s.last_verified_at = datetime.now(UTC) - timedelta(seconds=20)
        db.commit()

    with patch("apps.api.app.auth.get_ssrf_safe_opener") as mock_opener:
        mock_opener.return_value.open.side_effect = Exception("HTTP 503 Outage Continues")
        res = probe_monitored_services_task()
        assert res["probed_services"] == 1

    with TestingSessionLocal() as db:
        svc = db.get(Service, svc_id)
        assert svc.monitoring_status == "down"
        assert svc.consecutive_failures == 4

        # DEDUPLICATION: Must NOT create a second incident while acknowledged!
        incidents = db.scalars(select(Incident).where(Incident.service_id == svc_id)).all()
        assert len(incidents) == 1, f"Expected 1 incident, found {len(incidents)}"
        assert incidents[0].id == inc_id
        assert incidents[0].status == "acknowledged"

    # 4. Service recovers (HTTP 200) -> must resolve the acknowledged incident!
    with TestingSessionLocal() as db:
        s = db.get(Service, svc_id)
        s.last_verified_at = datetime.now(UTC) - timedelta(seconds=20)
        db.commit()

    mock_ok = MagicMock()
    mock_ok.status = 200
    mock_ok.__enter__.return_value = mock_ok
    mock_ok.__exit__.return_value = False

    with patch("apps.api.app.auth.get_ssrf_safe_opener") as mock_opener:
        mock_opener.return_value.open.return_value = mock_ok
        res_rec = probe_monitored_services_task()
        assert res_rec["probed_services"] == 1

    with TestingSessionLocal() as db:
        svc = db.get(Service, svc_id)
        assert svc.monitoring_status == "reachable"
        assert svc.consecutive_failures == 0
        assert svc.consecutive_successes == 1

        # The acknowledged incident must now be resolved
        incidents = db.scalars(select(Incident).where(Incident.service_id == svc_id)).all()
        assert len(incidents) == 1
        resolved_inc = incidents[0]
        assert resolved_inc.id == inc_id
        assert resolved_inc.status == "resolved"
        assert resolved_inc.resolved_at is not None
