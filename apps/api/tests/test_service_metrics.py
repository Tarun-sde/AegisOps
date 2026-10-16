import json
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.app.auth import create_user_session, hash_password
from apps.api.app.db import get_db
from apps.api.app.main import app
from apps.api.app.models import Base, Membership, Organization, Service, User
from apps.api.app.telemetry.promql import build_service_metrics_queries, escape_promql_label_value

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
def api_client():
    return TestClient(app)


def test_service_metrics_tenant_isolation_and_uninstrumented(api_client):
    with TestingSessionLocal() as db:
        # Org 1 with user 1 and ironlog service
        pwd_hash, salt = hash_password("pass123")
        uid = uuid4().hex[:8]
        org1 = Organization(id=uuid4(), name=f"Org 1 {uid}")
        user1 = User(
            id=uuid4(),
            email=f"user1_{uid}@org1.com",
            hashed_password=pwd_hash,
            salt=salt,
            name="User 1",
        )
        db.add_all([org1, user1])
        db.flush()
        db.add(Membership(user_id=user1.id, organization_id=org1.id, role="member"))

        ironlog = Service(
            id=uuid4(),
            organization_id=org1.id,
            name="ironlog",
            environment="production",
            healthcheck_url="https://ironlog.example.com/health",
        )
        db.add(ironlog)

        # Org 2 with another service
        org2 = Organization(id=uuid4(), name="Org 2")
        db.add(org2)
        db.flush()
        foreign_svc = Service(
            id=uuid4(),
            organization_id=org2.id,
            name="foreign-service",
            environment="staging",
        )
        db.add(foreign_svc)

        token1, _ = create_user_session(db, user1.id)
        db.commit()

        ironlog_id = str(ironlog.id)
        foreign_id = str(foreign_svc.id)

    api_client.cookies.set("aegisops_session", token1)

    # 1. Cross-tenant query must be rejected with 404
    cross_res = api_client.get(f"/api/v1/services/{foreign_id}/metrics")
    assert cross_res.status_code == 404

    # 2. Query ironlog with mock Prometheus returning no data (uninstrumented)
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = Mock()
        mock_resp.read.return_value = json.dumps({"data": {"result": []}}).encode("utf-8")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp

        res = api_client.get(f"/api/v1/services/{ironlog_id}/metrics?window=15m")
        assert res.status_code == 200
        data = res.json()
        assert data["service_id"] == ironlog_id
        assert data["is_instrumented"] is False
        assert data["status"] == "uninstrumented"
        assert "No Prometheus metrics scraped" in data["message"]
        assert data["metrics"]["request_rate"]["points"] == []

    # 3. Query instrumented service with mocked time-series points
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = Mock()
        mock_data = {
            "data": {
                "result": [
                    {
                        "metric": {"service": "ironlog"},
                        "values": [
                            [1700000000, "12.5"],
                            [1700000060, "15.0"],
                            [1700000120, "18.2"],
                        ],
                    }
                ]
            }
        }
        mock_resp.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp

        res = api_client.get(f"/api/v1/services/{ironlog_id}/metrics?window=1h")
        assert res.status_code == 200
        data = res.json()
        assert data["is_instrumented"] is True
        assert data["status"] == "instrumented"
        req_rate = data["metrics"]["request_rate"]
        assert len(req_rate["points"]) == 3
        assert req_rate["current_value"] == 18.2
        assert req_rate["points"][0]["value"] == 12.5

    # 4. Invalid window rejected
    bad_res = api_client.get(f"/api/v1/services/{ironlog_id}/metrics?window=100years")
    assert bad_res.status_code == 422


def test_cross_tenant_identical_service_name_query_isolation(api_client):
    """Prove identical service names across separate organizations produce isolated queries."""
    with TestingSessionLocal() as db:
        pwd_hash, salt = hash_password("pass123")
        # Org Alpha with service "payments"
        org_alpha = Organization(id=uuid4(), name="Org Alpha")
        user_alpha = User(
            id=uuid4(),
            email="alpha@example.com",
            hashed_password=pwd_hash,
            salt=salt,
            name="Alpha User",
        )
        db.add_all([org_alpha, user_alpha])
        db.flush()
        db.add(Membership(user_id=user_alpha.id, organization_id=org_alpha.id, role="owner"))
        svc_alpha = Service(
            id=uuid4(),
            organization_id=org_alpha.id,
            name="payments",
            environment="production",
        )
        db.add(svc_alpha)

        # Org Beta with service "payments"
        org_beta = Organization(id=uuid4(), name="Org Beta")
        user_beta = User(
            id=uuid4(),
            email="beta@example.com",
            hashed_password=pwd_hash,
            salt=salt,
            name="Beta User",
        )
        db.add_all([org_beta, user_beta])
        db.flush()
        db.add(Membership(user_id=user_beta.id, organization_id=org_beta.id, role="owner"))
        svc_beta = Service(
            id=uuid4(),
            organization_id=org_beta.id,
            name="payments",
            environment="production",
        )
        db.add(svc_beta)

        token_alpha, _ = create_user_session(db, user_alpha.id)
        token_beta, _ = create_user_session(db, user_beta.id)
        db.commit()

        svc_alpha_id = str(svc_alpha.id)
        svc_beta_id = str(svc_beta.id)
        org_alpha_id = str(org_alpha.id)
        org_beta_id = str(org_beta.id)

    # Org Alpha query inspection
    api_client.cookies.set("aegisops_session", token_alpha)
    captured_queries_alpha: list[str] = []

    with patch("urllib.request.urlopen") as mock_urlopen:

        def side_effect(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            if "query" in qs:
                captured_queries_alpha.append(qs["query"][0])
            mock_resp = Mock()
            mock_resp.read.return_value = json.dumps({"data": {"result": []}}).encode("utf-8")
            mock_resp.__enter__ = Mock(return_value=mock_resp)
            mock_resp.__exit__ = Mock(return_value=False)
            return mock_resp

        mock_urlopen.side_effect = side_effect
        res = api_client.get(f"/api/v1/services/{svc_alpha_id}/metrics?window=15m")
        assert res.status_code == 200

    # Assert Alpha queries contain Alpha's service_id and organization_id, never Beta's
    assert len(captured_queries_alpha) > 0
    for q in captured_queries_alpha:
        assert f'service_id="{svc_alpha_id}"' in q
        assert f'organization_id="{org_alpha_id}"' in q
        assert svc_beta_id not in q
        assert org_beta_id not in q

    # Org Beta query inspection
    api_client.cookies.set("aegisops_session", token_beta)
    captured_queries_beta: list[str] = []

    with patch("urllib.request.urlopen") as mock_urlopen:

        def side_effect(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            if "query" in qs:
                captured_queries_beta.append(qs["query"][0])
            mock_resp = Mock()
            mock_resp.read.return_value = json.dumps({"data": {"result": []}}).encode("utf-8")
            mock_resp.__enter__ = Mock(return_value=mock_resp)
            mock_resp.__exit__ = Mock(return_value=False)
            return mock_resp

        mock_urlopen.side_effect = side_effect
        res = api_client.get(f"/api/v1/services/{svc_beta_id}/metrics?window=15m")
        assert res.status_code == 200

    assert len(captured_queries_beta) > 0
    for q in captured_queries_beta:
        assert f'service_id="{svc_beta_id}"' in q
        assert f'organization_id="{org_beta_id}"' in q
        assert svc_alpha_id not in q
        assert org_alpha_id not in q


def test_promql_injection_adversarial_payload():
    """Verify adversarial service name strings cannot break out of PromQL string literals."""
    payload = 'shop-api", other_label=~".*", dummy="'
    escaped = escape_promql_label_value(payload)
    assert '\\"' in escaped
    import re

    # Ensure no unescaped double-quotes exist that could close the PromQL string literal
    assert re.findall(r'(?<!\\)"', escaped) == []

    sid = uuid4()
    oid = uuid4()
    queries = build_service_metrics_queries(
        service_id=sid,
        organization_id=oid,
        service_name=payload,
        is_demo_org=False,
    )

    req_query = queries["request_rate"][0]
    # The literal must remain quoted and escaped, preventing label breakout
    assert f'service="{escaped}"' in req_query
    assert f'service_id="{sid}"' in req_query
    assert f'organization_id="{oid}"' in req_query


def test_no_unscoped_promql_fallback_for_demo_shop_api():
    """Verify demo shop-api queries strictly require service_id or organization_id.

    Proves no unscoped fallback leg exists even when is_demo_org=True.
    """
    import re

    sid = uuid4()
    oid = uuid4()
    queries = build_service_metrics_queries(
        service_id=sid,
        organization_id=oid,
        service_name="shop-api",
        is_demo_org=True,
    )
    for q_name, (query_str, _unit) in queries.items():
        # Every query must contain service_id and organization_id scoping
        assert f'service_id="{sid}"' in query_str
        assert f'organization_id="{oid}"' in query_str
        # No unscoped leg like `service="shop-api"}` without organization_id
        unscoped_matches = re.findall(r'service="shop-api"(?!\s*,\s*organization_id)', query_str)
        assert len(unscoped_matches) == 0, f"Found unscoped fallback in {q_name}: {query_str}"
