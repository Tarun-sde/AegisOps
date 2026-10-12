from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.app.actions.catalog import (
    compute_parameters_hash,
    execute_action,
    validate_proposal_parameters,
)
from apps.api.app.auth import hash_password
from apps.api.app.db import get_db
from apps.api.app.main import app
from apps.api.app.models import (
    ActionProposal,
    Base,
    Membership,
    Organization,
    OutboxEvent,
    Service,
    User,
)
from apps.api.app.outbox.dispatcher import (
    calculate_backoff_delay,
    dispatch_outbox_batch,
)
from apps.api.app.outbox.service import create_outbox_event
from apps.api.app.outbox.signer import (
    sign_event_envelope,
    verify_event_signature,
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
    return {
        "csrf_token": res.cookies["aegisops_csrf"],
        "session": res.cookies["aegisops_session"],
    }


def make_signed_headers(
    payload: bytes, event_id: str, timestamp_str: str, secret: str | None = None
) -> dict[str, str]:
    sig = sign_event_envelope(payload, event_id, timestamp_str, secret=secret)
    return {
        "X-AegisOps-Signature": sig,
        "X-AegisOps-Timestamp": timestamp_str,
        "X-AegisOps-Event-ID": event_id,
        "X-AegisOps-Key-ID": "v1",
    }


# =========================================================================
# 1. UNIT TESTS: Signer, Canonical Hashing, Catalog & Invariants
# =========================================================================


def test_hmac_signing_and_verification_success():
    secret = "test-webhook-secret-32-chars-long!"
    payload = b'{"event_type":"incident.created","id":"123"}'
    event_id = str(uuid.uuid4())
    now_iso = datetime.now(UTC).isoformat()

    headers = make_signed_headers(payload, event_id, now_iso, secret=secret)
    assert "X-AegisOps-Signature" in headers
    assert headers["X-AegisOps-Event-ID"] == event_id
    assert headers["X-AegisOps-Timestamp"] == now_iso

    is_valid, reason = verify_event_signature(
        payload_bytes=payload,
        event_id=event_id,
        timestamp_str=now_iso,
        signature=headers["X-AegisOps-Signature"],
        secret=secret,
    )
    assert is_valid is True
    assert reason is None


def test_hmac_verification_invalid_signature():
    secret = "test-webhook-secret-32-chars-long!"
    payload = b'{"event_type":"incident.created"}'
    event_id = str(uuid.uuid4())
    now_iso = datetime.now(UTC).isoformat()

    headers = make_signed_headers(payload, event_id, now_iso, secret=secret)

    # Tampered payload
    is_valid, reason = verify_event_signature(
        payload_bytes=b'{"event_type":"incident.created","tampered":true}',
        event_id=event_id,
        timestamp_str=now_iso,
        signature=headers["X-AegisOps-Signature"],
        secret=secret,
    )
    assert is_valid is False
    assert reason == "Signature mismatch"


def test_hmac_verification_clock_skew_and_stale_timestamp():
    secret = "test-webhook-secret-32-chars-long!"
    payload = b'{"event_type":"incident.created"}'
    event_id = str(uuid.uuid4())
    stale_iso = (datetime.now(UTC) - timedelta(seconds=400)).isoformat()

    headers = make_signed_headers(payload, event_id, stale_iso, secret=secret)

    is_valid, reason = verify_event_signature(
        payload_bytes=payload,
        event_id=event_id,
        timestamp_str=stale_iso,
        signature=headers["X-AegisOps-Signature"],
        secret=secret,
        max_skew_seconds=300,
    )
    assert is_valid is False
    assert reason is not None
    assert "Timestamp skew" in reason


def test_canonical_parameter_hashing_order_independent():
    dict1 = {"b": 2, "a": 1, "nested": {"z": 9, "y": 8}}
    dict2 = {"a": 1, "nested": {"y": 8, "z": 9}, "b": 2}

    hash1 = compute_parameters_hash(dict1)
    hash2 = compute_parameters_hash(dict2)
    assert hash1 == hash2
    assert len(hash1) == 64

    # Different value produces different hash
    dict3 = {"a": 2, "b": 2, "nested": {"y": 8, "z": 9}}
    assert compute_parameters_hash(dict3) != hash1


def test_action_catalog_parameter_validation():
    # Valid restart params
    valid_restart = {
        "service_name": "shop-api",
        "reason": "OOM recovery",
        "grace_period_seconds": 30,
    }
    clean, param_hash = validate_proposal_parameters("restart_demo_service", valid_restart)
    assert clean["service_name"] == "shop-api"
    assert clean["grace_period_seconds"] == 30
    assert len(param_hash) == 64

    # Invalid catalog ID
    with pytest.raises(ValueError, match="is not permitted"):
        validate_proposal_parameters("unknown_action", {})

    # Invalid parameter type
    with pytest.raises(ValueError, match="Invalid parameters"):
        validate_proposal_parameters(
            "restart_demo_service",
            {"service_name": "shop-api", "reason": "ok", "grace_period_seconds": "not-an-int"},
        )


def test_zero_execution_invariant():
    """In Phase 6, executing actions is strictly prohibited (DEC-312)."""
    with pytest.raises(NotImplementedError, match="disabled in Phase 6"):
        execute_action("restart_demo_service", {})


def test_backoff_delay_exponential_growth():
    delay1 = calculate_backoff_delay(1, base_seconds=2.0, jitter=False)
    delay2 = calculate_backoff_delay(2, base_seconds=2.0, jitter=False)
    delay3 = calculate_backoff_delay(3, base_seconds=2.0, jitter=False)

    assert delay1 == 2.0
    assert delay2 == 4.0
    assert delay3 == 8.0

    delay_max = calculate_backoff_delay(20, base_seconds=2.0, max_seconds=100.0, jitter=False)
    assert delay_max == 100.0


# =========================================================================
# 2. TRANSACTIONAL OUTBOX & DISPATCHER TESTS
# =========================================================================


def test_create_outbox_event_bounds():
    with TestingSessionLocal() as db:
        _, org, _ = create_user_and_tenant(db, "outbox_user@example.com")
        event = create_outbox_event(
            db,
            organization_id=org.id,
            aggregate_type="incident",
            aggregate_id=str(uuid.uuid4()),
            event_type="incident.created",
            payload={"incident_id": "123", "service_name": "shop-api"},
        )
        db.commit()
        assert event.status == "PENDING"
        assert event.attempt_count == 0

        # Oversized payload rejected
        with pytest.raises(ValueError, match="exceeds maximum size limit"):
            create_outbox_event(
                db,
                organization_id=org.id,
                aggregate_type="incident",
                aggregate_id=str(uuid.uuid4()),
                event_type="incident.created",
                payload={"huge": "x" * 70000},
            )


def test_outbox_dispatch_success_to_demo_sink(test_client):
    with TestingSessionLocal() as db:
        _, org, _ = create_user_and_tenant(db, "sink_user@example.com")
        event = create_outbox_event(
            db,
            organization_id=org.id,
            aggregate_type="incident",
            aggregate_id=str(uuid.uuid4()),
            event_type="incident.created",
            payload={"title": "High latency on shop-api", "service_name": "shop-api"},
        )
        db.commit()
        event_id = event.id

    # Mock urllib request to return 200 OK
    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"status":"accepted"}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp), TestingSessionLocal() as db:
        result = dispatch_outbox_batch(db, batch_size=10)
        assert result["delivered"] == 1

        updated = db.get(OutboxEvent, event_id)
        assert updated is not None
        assert updated.status == "DELIVERED"
        assert updated.delivered_at is not None
        assert updated.attempt_count == 1


def test_outbox_dispatch_transient_failure_retries():
    import io
    import urllib.error

    with TestingSessionLocal() as db:
        _, org, _ = create_user_and_tenant(db, "retry_user@example.com")
        event = create_outbox_event(
            db,
            organization_id=org.id,
            aggregate_type="incident",
            aggregate_id=str(uuid.uuid4()),
            event_type="incident.created",
            payload={"title": "Error spike"},
        )
        db.commit()
        event_id = event.id

    # Mock HTTP 503 error
    http_error = urllib.error.HTTPError(
        url="http://dummy",
        code=503,
        msg="Service Unavailable",
        hdrs={},
        fp=io.BytesIO(b"Service Unavailable"),
    )

    with patch("urllib.request.urlopen", side_effect=http_error), TestingSessionLocal() as db:
        result = dispatch_outbox_batch(db, batch_size=10)
        assert result["retry_scheduled"] == 1

        updated = db.get(OutboxEvent, event_id)
        assert updated is not None
        assert updated.status == "RETRY_SCHEDULED"
        assert updated.attempt_count == 1
        next_attempt = (
            updated.next_attempt_at.replace(tzinfo=UTC)
            if updated.next_attempt_at.tzinfo is None
            else updated.next_attempt_at
        )
        assert next_attempt > datetime.now(UTC)


def test_outbox_dispatch_max_retries_dead_letters():
    import io
    import urllib.error

    with TestingSessionLocal() as db:
        _, org, _ = create_user_and_tenant(db, "dlq_user@example.com")
        event = create_outbox_event(
            db,
            organization_id=org.id,
            aggregate_type="incident",
            aggregate_id=str(uuid.uuid4()),
            event_type="incident.created",
            payload={"title": "Fatal event"},
        )
        event.attempt_count = 4
        event.max_attempts = 5
        db.commit()
        event_id = event.id

    http_error = urllib.error.HTTPError(
        url="http://dummy",
        code=500,
        msg="Internal Server Error",
        hdrs={},
        fp=io.BytesIO(b"Internal Server Error"),
    )

    with patch("urllib.request.urlopen", side_effect=http_error), TestingSessionLocal() as db:
        result = dispatch_outbox_batch(db, batch_size=10)
        assert result["dead_lettered"] == 1

        updated = db.get(OutboxEvent, event_id)
        assert updated is not None
        assert updated.status == "DEAD_LETTERED"
        assert updated.attempt_count == 5


# =========================================================================
# 3. DEMO SINK & RECEIVER IDEMPOTENCY TESTS (DEC-304, DEC-315)
# =========================================================================


def test_demo_sink_requires_valid_hmac(test_client):
    body = json.dumps({"event_id": "e-1", "data": {}}).encode("utf-8")

    # Missing headers -> 401
    res = test_client.post("/api/v1/automations/demo-sink", content=body)
    assert res.status_code == 401
    assert "Missing required signature headers" in res.json()["detail"]

    # Invalid signature -> 401
    headers = {
        "X-AegisOps-Signature": "invalid-sig",
        "X-AegisOps-Timestamp": datetime.now(UTC).isoformat(),
        "X-AegisOps-Event-ID": "e-1",
    }
    res = test_client.post("/api/v1/automations/demo-sink", content=body, headers=headers)
    assert res.status_code == 401


def test_demo_sink_idempotency_deduplication(test_client):
    """MANDATORY EXIT GATE: Repeated delivery does not create duplicate logical demo tickets."""
    event_id = str(uuid.uuid4())
    body_data = {
        "event_id": event_id,
        "event_type": "incident.created",
        "idempotency_key": f"idem-{event_id}",
        "data": {"title": "Test incident alert"},
    }
    body_bytes = json.dumps(body_data).encode("utf-8")
    now_iso = datetime.now(UTC).isoformat()
    headers = make_signed_headers(body_bytes, event_id, now_iso)

    # 1. First delivery -> accepted
    res1 = test_client.post("/api/v1/automations/demo-sink", content=body_bytes, headers=headers)
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert data1["status"] == "accepted"
    assert data1["ticket_id"] is not None

    # 2. Second delivery with identical event -> duplicate_ignored
    res2 = test_client.post("/api/v1/automations/demo-sink", content=body_bytes, headers=headers)
    assert res2.status_code == 200, res2.text
    data2 = res2.json()
    assert data2["status"] == "duplicate_ignored"
    assert data2["ticket_id"] is None
    assert "duplicate delivery ignored" in data2["message"].lower()


# =========================================================================
# 4. REMEDIATION PROPOSAL LIFECYCLE & SECURITY TESTS (DEC-308 - DEC-312)
# =========================================================================


def test_proposal_creation_and_retrieval(test_client):
    with TestingSessionLocal() as db:
        _, org, _ = create_user_and_tenant(db, "admin1@example.com", role="admin")
        service = Service(organization_id=org.id, name="shop-api")
        db.add(service)
        db.commit()
        service_id = str(service.id)

    auth = login_client(test_client, "admin1@example.com")
    csrf = auth["csrf_token"]

    payload = {
        "service_id": service_id,
        "environment": "staging",
        "action_catalog_id": "restart_demo_service",
        "immutable_parameters": {
            "service_name": "shop-api",
            "reason": "Memory leak detected in staging",
            "grace_period_seconds": 20,
        },
        "reason": "Memory leak detected in shop-api staging",
        "expected_outcome": "Process restarts cleanly and frees memory",
        "known_risks": "Brief 2-second connection drop on staging",
        "expires_in_seconds": 600,
    }

    res = test_client.post(
        "/api/v1/actions/proposals",
        json=payload,
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["status"] == "PROPOSED"
    assert data["action_catalog_id"] == "restart_demo_service"
    assert len(data["parameters_hash"]) == 64
    proposal_id = data["id"]

    # Retrieve proposal detail
    detail_res = test_client.get(f"/api/v1/actions/proposals/{proposal_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == proposal_id

    # List proposals
    list_res = test_client.get("/api/v1/actions/proposals")
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1


def test_proposal_approval_by_authorized_admin(test_client):
    """MANDATORY EXIT GATE: Authorized user can approve proposal with exact parameter hash."""
    with TestingSessionLocal() as db:
        _, org, _ = create_user_and_tenant(db, "approver@example.com", role="admin")
        service = Service(organization_id=org.id, name="shop-api")
        db.add(service)
        db.commit()
        service_id = str(service.id)

    auth = login_client(test_client, "approver@example.com")
    csrf = auth["csrf_token"]

    create_res = test_client.post(
        "/api/v1/actions/proposals",
        json={
            "service_id": service_id,
            "environment": "staging",
            "action_catalog_id": "rollback_demo_release",
            "immutable_parameters": {
                "service_name": "shop-api",
                "target_version": "v1.2.0",
                "reason": "Elevated 500 error rate",
            },
            "reason": "Elevated 500 error rate after v1.3.0 release",
            "expected_outcome": "Restores error rate to baseline",
            "known_risks": "Reverts new checkout features",
        },
        headers={"x-csrf-token": csrf},
    )
    assert create_res.status_code == 201
    prop = create_res.json()
    proposal_id = prop["id"]
    param_hash = prop["parameters_hash"]

    # Approve with exact hash
    approve_res = test_client.post(
        f"/api/v1/actions/proposals/{proposal_id}/approve",
        json={"expected_parameters_hash": param_hash, "comment": "Verified against staging alerts"},
        headers={"x-csrf-token": csrf},
    )
    assert approve_res.status_code == 200, approve_res.text
    approved_data = approve_res.json()
    assert approved_data["status"] == "APPROVED"
    assert approved_data["approval"] is not None
    assert approved_data["approval"]["decision"] == "APPROVED"

    # Verify atomic outbox event was generated for approval
    with TestingSessionLocal() as db:
        outbox_event = (
            db.query(OutboxEvent)
            .filter(
                OutboxEvent.aggregate_id == proposal_id,
                OutboxEvent.event_type == "proposal.approved",
            )
            .first()
        )
        assert outbox_event is not None


def test_proposal_approval_rejected_for_unauthorized_role(test_client):
    """MANDATORY EXIT GATE: Unauthorized user cannot approve proposal."""
    with TestingSessionLocal() as db:
        _admin_user, org, _ = create_user_and_tenant(db, "org_admin@example.com", role="admin")
        service = Service(organization_id=org.id, name="shop-api")
        db.add(service)

        # Create viewer user in the same org
        pwd_hash, salt = hash_password("password123")
        viewer = User(
            email="viewer@example.com",
            name="Viewer",
            hashed_password=pwd_hash,
            salt=salt,
            is_active=True,
        )
        db.add(viewer)
        db.flush()
        db.add(Membership(user_id=viewer.id, organization_id=org.id, role="viewer"))
        db.commit()
        service_id = str(service.id)

    # Create proposal as admin
    admin_auth = login_client(test_client, "org_admin@example.com")
    create_res = test_client.post(
        "/api/v1/actions/proposals",
        json={
            "service_id": service_id,
            "environment": "staging",
            "action_catalog_id": "restart_demo_service",
            "immutable_parameters": {
                "service_name": "shop-api",
                "reason": "Restart staging",
                "grace_period_seconds": 10,
            },
            "reason": "Restart staging",
            "expected_outcome": "Fresh process running",
            "known_risks": "Minimal connection blip",
        },
        headers={"x-csrf-token": admin_auth["csrf_token"]},
    )
    prop = create_res.json()
    proposal_id = prop["id"]
    param_hash = prop["parameters_hash"]

    # Attempt to approve as viewer -> 403 Forbidden
    viewer_auth = login_client(test_client, "viewer@example.com")
    res = test_client.post(
        f"/api/v1/actions/proposals/{proposal_id}/approve",
        json={"expected_parameters_hash": param_hash, "comment": "Sneaky approval"},
        headers={"x-csrf-token": viewer_auth["csrf_token"]},
    )
    assert res.status_code == 403
    assert "requires admin or owner" in res.json()["detail"]


def test_proposal_hash_mismatch_rejected(test_client):
    """MANDATORY EXIT GATE: Modified parameters cannot be approved under an old hash."""
    with TestingSessionLocal() as db:
        _, org, _ = create_user_and_tenant(db, "hash_admin@example.com", role="admin")
        service = Service(organization_id=org.id, name="shop-api")
        db.add(service)
        db.commit()
        service_id = str(service.id)

    auth = login_client(test_client, "hash_admin@example.com")
    create_res = test_client.post(
        "/api/v1/actions/proposals",
        json={
            "service_id": service_id,
            "environment": "staging",
            "action_catalog_id": "restart_demo_service",
            "immutable_parameters": {
                "service_name": "shop-api",
                "reason": "Routine restart",
                "grace_period_seconds": 10,
            },
            "reason": "Routine restart",
            "expected_outcome": "Fresh memory footprint",
            "known_risks": "Minimal connection blip",
        },
        headers={"x-csrf-token": auth["csrf_token"]},
    )
    proposal_id = create_res.json()["id"]

    # Submit wrong hash
    tampered_hash = hashlib.sha256(b"tampered").hexdigest()
    approve_res = test_client.post(
        f"/api/v1/actions/proposals/{proposal_id}/approve",
        json={"expected_parameters_hash": tampered_hash},
        headers={"x-csrf-token": auth["csrf_token"]},
    )
    assert approve_res.status_code == 400
    assert "does not match proposal's canonical hash" in approve_res.json()["detail"]


def test_proposal_lazy_expiry(test_client):
    """MANDATORY EXIT GATE: Expired proposals cannot be approved."""
    with TestingSessionLocal() as db:
        _, org, _ = create_user_and_tenant(db, "expiry_admin@example.com", role="admin")
        service = Service(organization_id=org.id, name="shop-api")
        db.add(service)
        db.commit()
        service_id = str(service.id)

    auth = login_client(test_client, "expiry_admin@example.com")
    create_res = test_client.post(
        "/api/v1/actions/proposals",
        json={
            "service_id": service_id,
            "environment": "staging",
            "action_catalog_id": "restart_demo_service",
            "immutable_parameters": {
                "service_name": "shop-api",
                "reason": "Test expiry",
                "grace_period_seconds": 10,
            },
            "reason": "Test expiry lifecycle",
            "expected_outcome": "Expected test outcome",
            "known_risks": "Minimal risk assessment",
            "expires_in_seconds": 60,
        },
        headers={"x-csrf-token": auth["csrf_token"]},
    )
    proposal_id = create_res.json()["id"]
    param_hash = create_res.json()["parameters_hash"]

    # Manually backdate expires_at in DB
    with TestingSessionLocal() as db:
        prop = db.get(ActionProposal, uuid.UUID(proposal_id))
        prop.expires_at = datetime.now(UTC) - timedelta(seconds=10)
        db.commit()

    # Reading proposal transitions to EXPIRED
    detail_res = test_client.get(f"/api/v1/actions/proposals/{proposal_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["status"] == "EXPIRED"

    # Approving expired proposal fails with 400
    approve_res = test_client.post(
        f"/api/v1/actions/proposals/{proposal_id}/approve",
        json={"expected_parameters_hash": param_hash},
        headers={"x-csrf-token": auth["csrf_token"]},
    )
    assert approve_res.status_code in (400, 409)
    assert "expired" in approve_res.json()["detail"].lower()


def test_cross_tenant_proposal_isolation(test_client):
    """Tenant B cannot read or approve Tenant A's proposal."""
    with TestingSessionLocal() as db:
        _, org_a, _ = create_user_and_tenant(
            db, "tenant_a@example.com", role="admin", org_name="Tenant A"
        )
        _, _org_b, _ = create_user_and_tenant(
            db, "tenant_b@example.com", role="admin", org_name="Tenant B"
        )

        svc_a = Service(organization_id=org_a.id, name="svc-a")
        db.add(svc_a)
        db.commit()
        svc_a_id = str(svc_a.id)

    auth_a = login_client(test_client, "tenant_a@example.com")
    create_res = test_client.post(
        "/api/v1/actions/proposals",
        json={
            "service_id": svc_a_id,
            "environment": "staging",
            "action_catalog_id": "restart_demo_service",
            "immutable_parameters": {
                "service_name": "svc-a",
                "reason": "Tenant A isolated task",
                "grace_period_seconds": 10,
            },
            "reason": "Tenant A isolated task",
            "expected_outcome": "Outcome",
            "known_risks": "Risks",
        },
        headers={"x-csrf-token": auth_a["csrf_token"]},
    )
    proposal_id = create_res.json()["id"]
    param_hash = create_res.json()["parameters_hash"]

    # Login as Tenant B
    auth_b = login_client(test_client, "tenant_b@example.com")

    # Read Tenant A proposal -> 404 Not Found
    res_get = test_client.get(f"/api/v1/actions/proposals/{proposal_id}")
    assert res_get.status_code == 404

    # Approve Tenant A proposal -> 404 Not Found
    res_approve = test_client.post(
        f"/api/v1/actions/proposals/{proposal_id}/approve",
        json={"expected_parameters_hash": param_hash},
        headers={"x-csrf-token": auth_b["csrf_token"]},
    )
    assert res_approve.status_code == 404


def test_rejection_lifecycle(test_client):
    with TestingSessionLocal() as db:
        _, org, _ = create_user_and_tenant(db, "reject_admin@example.com", role="admin")
        service = Service(organization_id=org.id, name="shop-api")
        db.add(service)
        db.commit()
        service_id = str(service.id)

    auth = login_client(test_client, "reject_admin@example.com")
    create_res = test_client.post(
        "/api/v1/actions/proposals",
        json={
            "service_id": service_id,
            "environment": "staging",
            "action_catalog_id": "restart_demo_service",
            "immutable_parameters": {
                "service_name": "shop-api",
                "reason": "Needs rejection",
                "grace_period_seconds": 10,
            },
            "reason": "Needs rejection",
            "expected_outcome": "Outcome",
            "known_risks": "Risks",
        },
        headers={"x-csrf-token": auth["csrf_token"]},
    )
    proposal_id = create_res.json()["id"]

    reject_res = test_client.post(
        f"/api/v1/actions/proposals/{proposal_id}/reject",
        json={"comment": "Root cause was DB deadlock, restart unnecessary"},
        headers={"x-csrf-token": auth["csrf_token"]},
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "REJECTED"
    assert reject_res.json()["approval"]["decision"] == "REJECTED"
    assert "DB deadlock" in reject_res.json()["approval"]["comment"]
