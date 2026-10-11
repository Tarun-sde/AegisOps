from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agents.incident_investigator.tools.gateway import ReadOnlyToolGateway
from apps.api.app.auth import (
    create_user_session,
    hash_password,
    validate_connector_url,
    verify_password,
)
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
    User,
)
from apps.api.app.schemas import Scope, SpanRead, TraceSummaryRead

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


def test_password_hashing_and_verification():
    raw = "Sup3rSecureP@ss!"
    pwd_hash, salt = hash_password(raw)
    assert pwd_hash != raw
    assert len(salt) > 0
    assert verify_password(raw, pwd_hash, salt) is True
    assert verify_password("wrong-password", pwd_hash, salt) is False


def test_auth_register_and_login_lifecycle(test_client):
    # 1. Register new user
    reg_res = test_client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "password123", "name": "Alice Developer"},
    )
    assert reg_res.status_code == 201, reg_res.text
    data = reg_res.json()
    assert data["user"]["email"] == "alice@example.com"
    assert data["role"] == "owner"
    assert "csrf_token" in data
    assert "aegisops_session" in reg_res.cookies
    assert "aegisops_csrf" in reg_res.cookies

    # 2. Duplicate registration fails
    dup_res = test_client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert dup_res.status_code == 409

    # 3. /api/v1/me with active session
    me_res = test_client.get("/api/v1/me")
    assert me_res.status_code == 200
    assert me_res.json()["user"]["email"] == "alice@example.com"

    # 4. Logout revokes session
    csrf_token = reg_res.cookies["aegisops_csrf"]
    logout_res = test_client.post(
        "/api/v1/auth/logout",
        headers={"x-csrf-token": csrf_token},
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "logged_out"

    # 5. Subsequent /api/v1/me is unauthorized
    unauth_res = test_client.get("/api/v1/me")
    assert unauth_res.status_code == 401

    # 6. Login again
    login_res = test_client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert login_res.status_code == 200
    assert login_res.json()["user"]["email"] == "alice@example.com"
    assert "aegisops_session" in login_res.cookies


def test_login_invalid_credentials_and_deactivated_account(test_client):
    with TestingSessionLocal() as db:
        pwd_hash, salt = hash_password("secretpass")
        user = User(
            email="bob@example.com",
            hashed_password=pwd_hash,
            salt=salt,
            name="Bob",
            is_active=False,
        )
        db.add(user)
        db.commit()

    # Wrong password
    bad_res = test_client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "wrongpassword"},
    )
    assert bad_res.status_code == 401

    # Deactivated account
    deact_res = test_client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "secretpass"},
    )
    assert deact_res.status_code == 401
    assert "deactivated" in deact_res.json()["detail"]


def test_expired_session_rejected(test_client):
    with TestingSessionLocal() as db:
        pwd_hash, salt = hash_password("pass")
        user = User(
            email="expired@example.com",
            hashed_password=pwd_hash,
            salt=salt,
            name="Exp",
            is_active=True,
        )
        db.add(user)
        db.flush()
        org = Organization(name="Org Exp")
        db.add(org)
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=org.id, role="member"))
        raw_token, session = create_user_session(db, user.id)
        # Manually expire session
        session.expires_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()

    test_client.cookies.set("aegisops_session", raw_token)
    res = test_client.get("/api/v1/me")
    assert res.status_code == 401


def test_csrf_protection_on_mutating_requests(test_client):
    # Register user to get session and csrf
    reg_res = test_client.post(
        "/api/v1/auth/register",
        json={"email": "csrf_test@example.com", "password": "password123"},
    )
    assert reg_res.status_code == 201
    csrf_token = reg_res.cookies["aegisops_csrf"]

    # Mutating POST without x-csrf-token header -> 403 CSRF validation failed
    svc_no_csrf = test_client.post(
        "/api/v1/services",
        json={"name": "test-svc", "environment": "staging"},
    )
    assert svc_no_csrf.status_code == 403
    assert "CSRF" in svc_no_csrf.json()["detail"]

    # Mutating POST with mismatched x-csrf-token header -> 403
    svc_bad_csrf = test_client.post(
        "/api/v1/services",
        json={"name": "test-svc", "environment": "staging"},
        headers={"x-csrf-token": "bad-token"},
    )
    assert svc_bad_csrf.status_code == 403

    # Mutating POST with matching header -> 201 Created
    svc_ok = test_client.post(
        "/api/v1/services",
        json={"name": "test-svc", "environment": "staging"},
        headers={"x-csrf-token": csrf_token},
    )
    assert svc_ok.status_code == 201
    assert svc_ok.json()["name"] == "test-svc"


def test_cross_tenant_isolation(test_client):
    with TestingSessionLocal() as db:
        # Org A
        pwd_hash, salt = hash_password("pass")
        user_a = User(email="user_a@tenant.a", hashed_password=pwd_hash, salt=salt, name="User A")
        db.add(user_a)
        db.flush()
        org_a = Organization(name="Tenant Alpha")
        db.add(org_a)
        db.flush()
        db.add(Membership(user_id=user_a.id, organization_id=org_a.id, role="owner"))
        sv_a = Service(organization_id=org_a.id, name="service-a")
        db.add(sv_a)
        db.flush()
        inc_a = Incident(
            organization_id=org_a.id,
            service_id=sv_a.id,
            title="Incident A",
            status="open",
            severity="critical",
            fingerprint="fp-a",
            started_at=datetime.now(UTC),
        )
        db.add(inc_a)

        # Org B
        user_b = User(email="user_b@tenant.b", hashed_password=pwd_hash, salt=salt, name="User B")
        db.add(user_b)
        db.flush()
        org_b = Organization(name="Tenant Beta")
        db.add(org_b)
        db.flush()
        db.add(Membership(user_id=user_b.id, organization_id=org_b.id, role="owner"))
        sv_b = Service(organization_id=org_b.id, name="service-b")
        db.add(sv_b)
        db.flush()
        inc_b = Incident(
            organization_id=org_b.id,
            service_id=sv_b.id,
            title="Incident B",
            status="open",
            severity="critical",
            fingerprint="fp-b",
            started_at=datetime.now(UTC),
        )
        db.add(inc_b)

        raw_token_a, _ = create_user_session(db, user_a.id)
        org_b_id = org_b.id
        sv_b_id = sv_b.id
        inc_b_id = inc_b.id
        db.commit()

    # User A authenticates
    test_client.cookies.set("aegisops_session", raw_token_a)

    # 1. User A attempts to view Org B's members -> 403 Forbidden
    res_members = test_client.get(f"/api/v1/organizations/{org_b_id}/members")
    assert res_members.status_code == 403

    # 2. User A attempts to view Org B's service -> 404 Not Found (tenant-isolated query)
    res_svc = test_client.get(f"/api/v1/services/{sv_b_id}")
    assert res_svc.status_code == 404

    # 3. User A attempts to view Org B's incident -> 404 Not Found
    res_inc = test_client.get(f"/api/v1/incidents/{inc_b_id}")
    assert res_inc.status_code == 404


def test_rbac_role_hierarchy_and_permissions(test_client):
    with TestingSessionLocal() as db:
        pwd_hash, salt = hash_password("pass")
        org = Organization(name="Role Org")
        db.add(org)
        db.flush()

        # Viewer User
        viewer = User(
            email="viewer@example.com", hashed_password=pwd_hash, salt=salt, name="Viewer"
        )
        db.add(viewer)
        db.flush()
        db.add(Membership(user_id=viewer.id, organization_id=org.id, role="viewer"))

        svc = Service(organization_id=org.id, name="prod-api")
        db.add(svc)
        db.flush()

        inc = Incident(
            organization_id=org.id,
            service_id=svc.id,
            title="Alert incident",
            status="open",
            severity="high",
            fingerprint="fp-role-1",
            started_at=datetime.now(UTC),
        )
        db.add(inc)
        db.flush()

        inv = InvestigationRun(
            incident_id=inc.id,
            organization_id=org.id,
            service_id=svc.id,
            status="running",
            summary="Underway",
        )
        db.add(inv)
        raw_token, _ = create_user_session(db, viewer.id)
        svc_id = svc.id
        inc_id = inc.id
        inv_id = inv.id
        db.commit()

    test_client.cookies.set("aegisops_session", raw_token)
    test_client.cookies.set("aegisops_csrf", "dummy-csrf")
    headers = {"x-csrf-token": "dummy-csrf"}

    # 1. Viewer cannot create a service -> 403
    res_svc = test_client.post(
        "/api/v1/services",
        json={"name": "new-svc", "environment": "staging"},
        headers=headers,
    )
    assert res_svc.status_code == 403

    # 2. Viewer cannot update a service -> 403
    res_patch = test_client.patch(
        f"/api/v1/services/{svc_id}",
        json={"description": "new desc"},
        headers=headers,
    )
    assert res_patch.status_code == 403

    # 3. Viewer cannot verify service connection -> 403
    res_verify = test_client.post(
        f"/api/v1/services/{svc_id}/verify-connection",
        json={"url": "https://example.com/healthz"},
        headers=headers,
    )
    assert res_verify.status_code == 403

    # 4. Viewer cannot trigger investigation -> 403
    res_inv = test_client.post(
        f"/api/v1/incidents/{inc_id}/investigations",
        json={"agent_version": "v1.0.0"},
        headers=headers,
    )
    assert res_inv.status_code == 403

    # 5. Viewer cannot cancel investigation -> 403
    res_cancel = test_client.post(
        f"/api/v1/investigations/{inv_id}/cancel",
        headers=headers,
    )
    assert res_cancel.status_code == 403

    # 6. But Viewer CAN read incidents and services -> 200
    assert test_client.get("/api/v1/services").status_code == 200
    assert test_client.get(f"/api/v1/incidents/{inc_id}").status_code == 200


def test_ssrf_validator_guards(test_client):
    # Direct validator tests
    with pytest.raises(ValueError, match="cloud instance metadata"):
        validate_connector_url("http://169.254.169.254/latest/meta-data")

    with pytest.raises(ValueError, match="Loopback connections are prohibited"):
        validate_connector_url("http://127.0.0.1:8000/metrics", allow_local_demo=False)

    with pytest.raises(ValueError, match="Private network connections are prohibited"):
        validate_connector_url("http://10.0.1.1:9090", allow_local_demo=False)

    with pytest.raises(ValueError, match="Private network connections are prohibited"):
        validate_connector_url("http://192.168.1.100", allow_local_demo=False)

    with pytest.raises(ValueError, match="Only HTTP and HTTPS are permitted"):
        validate_connector_url("ftp://example.com/file")

    with pytest.raises(ValueError, match="cloud instance metadata"):
        validate_connector_url("http://metadata.google.internal/computeMetadata/v1")

    # API endpoint SSRF rejection
    with TestingSessionLocal() as db:
        pwd_hash, salt = hash_password("pass")
        org = Organization(name="SSRF Org")
        db.add(org)
        db.flush()
        admin = User(email="admin@ssrf.org", hashed_password=pwd_hash, salt=salt, name="Admin")
        db.add(admin)
        db.flush()
        db.add(Membership(user_id=admin.id, organization_id=org.id, role="admin"))
        svc = Service(organization_id=org.id, name="target-svc")
        db.add(svc)
        raw_token, _ = create_user_session(db, admin.id)
        svc_id = svc.id
        db.commit()

    test_client.cookies.set("aegisops_session", raw_token)
    test_client.cookies.set("aegisops_csrf", "admin-csrf")
    headers = {"x-csrf-token": "admin-csrf"}

    res = test_client.post(
        f"/api/v1/services/{svc_id}/verify-connection",
        json={"url": "http://169.254.169.254/latest/meta-data"},
        headers=headers,
    )
    assert res.status_code == 400
    assert "SSRF Protection" in res.json()["detail"]


def test_distributed_tracing_endpoint_and_gateway(test_client):
    # 1. Invalid trace id format
    with TestingSessionLocal() as db:
        pwd_hash, salt = hash_password("pass")
        org = Organization(name="Trace Org")
        db.add(org)
        db.flush()
        user = User(email="tracer@org.com", hashed_password=pwd_hash, salt=salt, name="Tracer")
        db.add(user)
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=org.id, role="member"))
        svc = Service(organization_id=org.id, name="trace-svc")
        db.add(svc)
        db.flush()
        inc = Incident(
            organization_id=org.id,
            service_id=svc.id,
            title="Trace Incident",
            status="open",
            severity="critical",
            fingerprint="fp-trace",
            started_at=datetime.now(UTC),
        )
        db.add(inc)
        db.flush()
        inv = InvestigationRun(
            incident_id=inc.id,
            organization_id=org.id,
            service_id=svc.id,
            status="running",
        )
        db.add(inv)
        raw_token, _ = create_user_session(db, user.id)
        org_id = org.id
        svc_id = svc.id
        inc_id = inc.id
        inv_id = inv.id
        db.commit()

    test_client.cookies.set("aegisops_session", raw_token)

    # Bad format (not 32 hex chars)
    bad_res = test_client.get("/api/v1/traces/invalid-trace-id")
    assert bad_res.status_code == 400

    # Mocked TempoClient returning spans
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    mock_summary = TraceSummaryRead(
        trace_id=trace_id,
        service_name="shop-api",
        root_operation="GET /cart",
        duration_ms=1.0,
        span_count=1,
        error_span_count=0,
        spans=[
            SpanRead(
                span_id="0000000000000001",
                trace_id=trace_id,
                name="GET /cart",
                service_name="shop-api",
                start_time_unix_nano=1000000,
                end_time_unix_nano=2000000,
                duration_ms=1.0,
                status_code="STATUS_CODE_OK",
                attributes={"http.status_code": 200},
            )
        ],
    )

    with patch("apps.api.app.main.TempoClient") as MockTempo:
        instance = MockTempo.return_value
        instance.get_trace_summary.return_value = mock_summary

        res = test_client.get(f"/api/v1/traces/{trace_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["trace_id"] == trace_id
        assert data["service_name"] == "shop-api"
        assert len(data["spans"]) == 1

    # Test Gateway tool execution
    with patch("apps.api.app.telemetry.tempo.TempoClient") as MockGwTempo:
        gw_inst = MockGwTempo.return_value
        gw_inst.get_trace_summary.return_value = mock_summary

        with TestingSessionLocal() as db:
            run_rec = db.query(InvestigationRun).filter(InvestigationRun.id == inv_id).first()
            inc_rec = db.query(Incident).filter(Incident.id == inc_id).first()
            scope = Scope(
                organization_id=org_id,
                service_id=svc_id,
                run_id=inv_id,
            )
            gw = ReadOnlyToolGateway(
                scope=scope,
                incident=inc_rec,
                run_record=run_rec,
                db_session=db,
            )
            result = gw.get_trace_summary(trace_id)
            assert result["service_name"] == "shop-api"
            assert "duration_ms" in result
            assert "evidence_id" in result

            # Verify evidence item persisted in db
            ev = db.query(EvidenceItem).filter(EvidenceItem.run_id == inv_id).first()
            assert ev is not None
            assert ev.source == "traces"
