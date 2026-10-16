from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.app.db import get_db
from apps.api.app.main import app
from apps.api.app.models import Base

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


@pytest.fixture(autouse=True)
def mock_public_dns():
    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
        yield mock_dns


@pytest.fixture
def client():
    return TestClient(app)


def test_service_connection_create_and_persistence(client):
    # 1. Register user
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "operator@ironlog.io", "password": "password123", "name": "IronLog Admin"},
    )
    assert reg.status_code == 201
    csrf = reg.cookies["aegisops_csrf"]

    # 2. Create service with healthcheck url
    create_res = client.post(
        "/api/v1/services",
        json={
            "name": "IRONLOG",
            "environment": "production",
            "description": "Cross-platform strength training log",
            "healthcheck_url": "https://ironlog.example.com/api/health",
            "is_monitored": True,
            "monitoring_interval_seconds": 30,
        },
        headers={"x-csrf-token": csrf},
    )
    assert create_res.status_code == 201, create_res.text
    svc = create_res.json()
    assert svc["name"] == "IRONLOG"
    assert svc["healthcheck_url"] == "https://ironlog.example.com/api/health"
    assert svc["monitoring_status"] == "configured"
    assert svc["is_monitored"] is True
    assert svc["monitoring_interval_seconds"] == 30
    service_id = svc["id"]

    # 3. Fetch service via GET /services/{id} and verify persistence
    get_res = client.get(f"/api/v1/services/{service_id}")
    assert get_res.status_code == 200
    fetched = get_res.json()
    assert fetched["healthcheck_url"] == "https://ironlog.example.com/api/health"
    assert fetched["monitoring_status"] == "configured"


def test_service_connection_update_and_clear(client):
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "lead@ironlog.io", "password": "password123", "name": "IronLog Lead"},
    )
    csrf = reg.cookies["aegisops_csrf"]

    # Create unconfigured service
    create_res = client.post(
        "/api/v1/services",
        json={"name": "ironlog-api", "environment": "staging"},
        headers={"x-csrf-token": csrf},
    )
    assert create_res.status_code == 201
    svc_id = create_res.json()["id"]
    assert create_res.json()["monitoring_status"] == "unknown"

    # Patch with healthcheck URL
    patch_res = client.patch(
        f"/api/v1/services/{svc_id}",
        json={
            "healthcheck_url": "https://ironlog-staging.example.com/health",
            "monitoring_interval_seconds": 45,
        },
        headers={"x-csrf-token": csrf},
    )
    assert patch_res.status_code == 200
    patched = patch_res.json()
    assert patched["healthcheck_url"] == "https://ironlog-staging.example.com/health"
    assert patched["monitoring_status"] == "configured"
    assert patched["monitoring_interval_seconds"] == 45

    # Clear healthcheck URL
    clear_res = client.patch(
        f"/api/v1/services/{svc_id}",
        json={"healthcheck_url": ""},
        headers={"x-csrf-token": csrf},
    )
    assert clear_res.status_code == 200
    cleared = clear_res.json()
    assert cleared["healthcheck_url"] is None
    assert cleared["monitoring_status"] == "unknown"


def test_verify_service_connection_success_and_observation(client):
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "sre@ironlog.io", "password": "password123", "name": "IronLog SRE"},
    )
    csrf = reg.cookies["aegisops_csrf"]

    create_res = client.post(
        "/api/v1/services",
        json={"name": "ironlog-prod", "environment": "production"},
        headers={"x-csrf-token": csrf},
    )
    svc_id = create_res.json()["id"]

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("apps.api.app.main.get_ssrf_safe_opener") as mock_opener:
        mock_opener.return_value.open.return_value = mock_resp
        verify_res = client.post(
            f"/api/v1/services/{svc_id}/verify-connection",
            json={"url": "https://ironlog.example.com/healthz"},
            headers={"x-csrf-token": csrf},
        )

    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["success"] is True
    assert v_data["status_code"] == 200
    assert v_data["monitoring_status"] == "reachable"
    assert v_data["last_verified_at"] is not None

    # Verify service updated in DB
    svc_get = client.get(f"/api/v1/services/{svc_id}").json()
    assert svc_get["healthcheck_url"] == "https://ironlog.example.com/healthz"
    assert svc_get["monitoring_status"] == "reachable"
    assert svc_get["last_probe_status_code"] == 200
    assert svc_get["consecutive_successes"] == 1
    assert svc_get["consecutive_failures"] == 0

    # Verify observation logged
    obs_res = client.get(f"/api/v1/services/{svc_id}/health-observations")
    assert obs_res.status_code == 200
    obs_list = obs_res.json()
    assert len(obs_list) == 1
    assert obs_list[0]["status"] == "reachable"
    assert obs_list[0]["status_code"] == 200


def test_verify_service_connection_failure_updates_status(client):
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "sre2@ironlog.io", "password": "password123", "name": "IronLog SRE 2"},
    )
    csrf = reg.cookies["aegisops_csrf"]

    create_res = client.post(
        "/api/v1/services",
        json={"name": "ironlog-failing", "environment": "production"},
        headers={"x-csrf-token": csrf},
    )
    svc_id = create_res.json()["id"]

    mock_resp = MagicMock()
    mock_resp.status = 503
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("apps.api.app.main.get_ssrf_safe_opener") as mock_opener:
        mock_opener.return_value.open.return_value = mock_resp
        # Failure 1: Under threshold (3), service is marked 'degraded'
        verify_res = client.post(
            f"/api/v1/services/{svc_id}/verify-connection",
            json={"url": "https://ironlog.example.com/healthz"},
            headers={"x-csrf-token": csrf},
        )

    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["success"] is False
    assert v_data["status_code"] == 503
    assert v_data["monitoring_status"] == "degraded"

    svc_get = client.get(f"/api/v1/services/{svc_id}").json()
    assert svc_get["monitoring_status"] == "degraded"
    assert svc_get["consecutive_failures"] == 1

    # Failures 2 and 3: Reaches threshold, transitions to 'down' and creates incident
    with patch("apps.api.app.main.get_ssrf_safe_opener") as mock_opener:
        mock_opener.return_value.open.return_value = mock_resp
        client.post(
            f"/api/v1/services/{svc_id}/verify-connection",
            json={"url": "https://ironlog.example.com/healthz"},
            headers={"x-csrf-token": csrf},
        )
        verify_res3 = client.post(
            f"/api/v1/services/{svc_id}/verify-connection",
            json={"url": "https://ironlog.example.com/healthz"},
            headers={"x-csrf-token": csrf},
        )

    v3_data = verify_res3.json()
    assert v3_data["monitoring_status"] == "down"
    svc_get3 = client.get(f"/api/v1/services/{svc_id}").json()
    assert svc_get3["monitoring_status"] == "down"
    assert svc_get3["consecutive_failures"] == 3


def test_clear_github_repo_and_nullable_fields_persistence(client):
    """Test clearing github_repo persists None and doesn't restore old value upon reload."""
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "sre3@ironlog.io", "password": "password123", "name": "IronLog SRE 3"},
    )
    csrf = reg.cookies["aegisops_csrf"]

    # 1. Create service with github_repo and description
    create_res = client.post(
        "/api/v1/services",
        json={
            "name": "ironlog-repo-test",
            "environment": "production",
            "github_repo": "https://github.com/ironlog/core",
            "description": "Initial description",
        },
        headers={"x-csrf-token": csrf},
    )
    assert create_res.status_code == 201
    svc_id = create_res.json()["id"]
    assert create_res.json()["github_repo"] == "https://github.com/ironlog/core"

    # 2. Clear github_repo by explicitly passing null
    patch_res = client.patch(
        f"/api/v1/services/{svc_id}",
        json={"github_repo": None},
        headers={"x-csrf-token": csrf},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["github_repo"] is None

    # 3. Fetch again and verify field is cleared and persisted
    get_res = client.get(f"/api/v1/services/{svc_id}")
    assert get_res.status_code == 200
    assert get_res.json()["github_repo"] is None
    assert get_res.json()["description"] == "Initial description"


def test_service_connection_tenant_isolation(client):
    # Org A
    reg_a = client.post(
        "/api/v1/auth/register",
        json={"email": "tenant_a@example.com", "password": "password123", "name": "Tenant A"},
    )
    csrf_a = reg_a.cookies["aegisops_csrf"]
    svc_a = client.post(
        "/api/v1/services",
        json={"name": "Service-A", "environment": "production"},
        headers={"x-csrf-token": csrf_a},
    ).json()["id"]

    # Org B
    reg_b = client.post(
        "/api/v1/auth/register",
        json={"email": "tenant_b@example.com", "password": "password123", "name": "Tenant B"},
    )
    csrf_b = reg_b.cookies["aegisops_csrf"]

    # Org B attempts to patch Org A's service -> 404
    patch_attempt = client.patch(
        f"/api/v1/services/{svc_a}",
        json={"healthcheck_url": "https://attacker.example.com"},
        headers={"x-csrf-token": csrf_b},
    )
    assert patch_attempt.status_code == 404

    # Org B attempts to verify Org A's service -> 404
    verify_attempt = client.post(
        f"/api/v1/services/{svc_a}/verify-connection",
        json={"url": "https://attacker.example.com"},
        headers={"x-csrf-token": csrf_b},
    )
    assert verify_attempt.status_code == 404

    # Org B attempts to read health observations of Org A's service -> 404
    obs_attempt = client.get(
        f"/api/v1/services/{svc_a}/health-observations",
        headers={"x-csrf-token": csrf_b},
    )
    assert obs_attempt.status_code == 404
