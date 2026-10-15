import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.app.auth import create_user_session
from apps.api.app.main import app, get_db
from apps.api.app.models import Base, Membership, Organization, Service, User

# Isolated in-memory SQLite for fast, self-contained unit tests
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    # Seed Demo Org, Service, User, and Session for authenticated test client
    with TestingSessionLocal() as db:
        org = Organization(name="AegisOps Demo")
        db.add(org)
        db.flush()
        svc = Service(organization_id=org.id, name="shop-api")
        db.add(svc)
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
        raw_token, _ = create_user_session(db, user.id)
        client.cookies.set("aegisops_session", raw_token)

    app.dependency_overrides[get_db] = override_get_db
    yield

    client.cookies.clear()
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)

AUTH_HEADER = {"Authorization": "Bearer aegisops-demo-alertmanager-secret"}


def sample_webhook_payload(status: str = "firing", fingerprint: str = "fp-test-123"):
    return {
        "version": "4",
        "groupKey": f"group-{fingerprint}",
        "status": status,
        "receiver": "aegisops-webhook",
        "alerts": [
            {
                "status": status,
                "labels": {
                    "alertname": "HighApiErrorRate",
                    "service": "shop-api",
                    "severity": "critical",
                    "environment": "demo",
                },
                "annotations": {
                    "summary": "High 5xx error rate on shop-api route /checkout",
                    "description": "5xx ratio > 20% on /checkout",
                },
                "startsAt": datetime.now(UTC).isoformat(),
                "endsAt": (datetime.now(UTC).isoformat() if status == "resolved" else None),
                "fingerprint": fingerprint,
            }
        ],
    }


def test_webhook_auth_rejection():
    # 1. Missing header
    res1 = client.post("/api/v1/webhooks/alertmanager", json=sample_webhook_payload())
    assert res1.status_code == 401

    # 2. Invalid bearer token
    res2 = client.post(
        "/api/v1/webhooks/alertmanager",
        headers={"Authorization": "Bearer wrong-token"},
        json=sample_webhook_payload(),
    )
    assert res2.status_code == 401


def test_webhook_payload_validation():
    # Malformed payload (missing required alerts)
    res = client.post(
        "/api/v1/webhooks/alertmanager",
        headers=AUTH_HEADER,
        json={"version": "4", "groupKey": "test"},
    )
    assert res.status_code == 422


def test_webhook_incident_creation_and_deduplication():
    # Step 1: Initial firing webhook delivery
    payload = sample_webhook_payload("firing", "fp-checkout-101")
    res1 = client.post("/api/v1/webhooks/alertmanager", headers=AUTH_HEADER, json=payload)
    assert res1.status_code == 200
    assert res1.json()["incidents_created"] == 1
    assert res1.json()["duplicates_skipped"] == 0

    # Verify incident exists via API
    list_res = client.get("/api/v1/incidents")
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] == 1
    incident = data["items"][0]
    assert incident["status"] == "open"
    assert incident["fingerprint"] == "fp-checkout-101"
    assert incident["severity"] == "critical"

    # Step 2: Duplicate delivery (same fingerprint, still firing)
    res2 = client.post("/api/v1/webhooks/alertmanager", headers=AUTH_HEADER, json=payload)
    assert res2.status_code == 200
    assert res2.json()["incidents_created"] == 0
    assert res2.json()["duplicates_skipped"] == 1

    # Confirm still exactly 1 incident in database
    list_res2 = client.get("/api/v1/incidents")
    assert list_res2.json()["total"] == 1

    # Check incident timeline events
    events_res = client.get(f"/api/v1/incidents/{incident['id']}/events")
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) == 2
    assert events[0]["event_type"] == "incident_created"
    assert events[1]["event_type"] == "alert_firing_duplicate"

    # Step 3: Resolved webhook delivery
    resolved_payload = sample_webhook_payload("resolved", "fp-checkout-101")
    res3 = client.post("/api/v1/webhooks/alertmanager", headers=AUTH_HEADER, json=resolved_payload)
    assert res3.status_code == 200
    assert res3.json()["incidents_resolved"] == 1

    # Confirm incident is now resolved
    detail_res = client.get(f"/api/v1/incidents/{incident['id']}")
    assert detail_res.status_code == 200
    assert detail_res.json()["status"] == "resolved"
    assert detail_res.json()["resolved_at"] is not None

    # Step 4: Duplicate resolved delivery is idempotent
    res4 = client.post("/api/v1/webhooks/alertmanager", headers=AUTH_HEADER, json=resolved_payload)
    assert res4.status_code == 200
    assert res4.json()["incidents_resolved"] == 0

    # Step 5: Recurrence creates a new incident episode
    recurrence_payload = sample_webhook_payload("firing", "fp-checkout-101")
    res5 = client.post(
        "/api/v1/webhooks/alertmanager", headers=AUTH_HEADER, json=recurrence_payload
    )
    assert res5.status_code == 200
    assert res5.json()["incidents_created"] == 1

    list_res3 = client.get("/api/v1/incidents")
    assert list_res3.json()["total"] == 2


def test_incident_query_filters_and_404():
    # 404 on unknown incident
    res = client.get(f"/api/v1/incidents/{uuid.uuid4()}")
    assert res.status_code == 404

    res_events = client.get(f"/api/v1/incidents/{uuid.uuid4()}/events")
    assert res_events.status_code == 404


def test_application_incidents_filter_before_pagination_and_inventory_counts():
    """DEC-385: unrelated recent incidents must not hide older application records."""
    from datetime import timedelta

    from sqlalchemy import select

    from apps.api.app.models import Incident

    with TestingSessionLocal() as db:
        service = db.scalar(select(Service))
        org_id, service_id = service.organization_id, service.id
        other = Service(organization_id=org_id, name="another-app")
        foreign_org = Organization(name="Foreign workspace")
        db.add_all([other, foreign_org])
        db.flush()
        foreign = Service(organization_id=foreign_org.id, name="foreign-app")
        db.add(foreign)
        db.flush()
        foreign_id = foreign.id
        now = datetime.now(UTC)
        for index in range(25):
            db.add(
                Incident(
                    organization_id=org_id,
                    service_id=other.id,
                    title=f"Unrelated {index}",
                    severity="warning",
                    status="open",
                    fingerprint=f"other-{index}",
                    started_at=now,
                )
            )
        for index, lifecycle in enumerate(
            ["open", "acknowledged", "mitigating", "reopened", "resolved", "closed"]
        ):
            db.add(
                Incident(
                    organization_id=org_id,
                    service_id=service_id,
                    title=f"Selected {index}",
                    severity="critical",
                    status=lifecycle,
                    fingerprint=f"selected-{index}",
                    started_at=now - timedelta(days=index + 1),
                )
            )
        db.add(
            Incident(
                organization_id=foreign_org.id,
                service_id=foreign_id,
                title="Foreign private incident",
                severity="critical",
                status="open",
                fingerprint="foreign",
                started_at=now,
            )
        )
        db.commit()
    response = client.get(f"/api/v1/incidents?service_id={service_id}&size=2&page=2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 6
    assert [i["title"] for i in payload["items"]] == ["Selected 2", "Selected 3"]
    assert all(i["service_id"] == str(service_id) for i in payload["items"])
    filtered = client.get(
        f"/api/v1/incidents?service_id={service_id}&status=resolved&severity=critical"
    ).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["title"] == "Selected 4"
    services = client.get("/api/v1/services").json()
    selected = next(s for s in services if s["id"] == str(service_id))
    assert selected["active_incident_count"] == 4
    assert selected["last_incident_at"] is not None
    assert len(services) == 2
    assert client.get(f"/api/v1/incidents?service_id={foreign_id}").status_code == 404
    assert client.get(f"/api/v1/incidents?service_id={uuid.uuid4()}").status_code == 404
    assert client.get("/api/v1/incidents?service_id=not-a-uuid").status_code == 422
    client.cookies.clear()
    assert client.get(f"/api/v1/incidents?service_id={service_id}").status_code == 401
    assert client.get("/api/v1/services").status_code == 401
