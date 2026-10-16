import json
from datetime import UTC, datetime
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agents.incident_investigator.tools.gateway import ReadOnlyToolGateway
from agents.incident_investigator.tools.redaction import redact_sensitive_text
from apps.api.app.models import (
    Base,
    EvidenceItem,
    Incident,
    InvestigationRun,
    Organization,
    Service,
)
from apps.api.app.schemas import Scope


@pytest.fixture
def test_db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    org = Organization(id=uuid4(), name="Test Org")
    session.add(org)
    session.flush()

    ironlog_service = Service(
        id=uuid4(),
        organization_id=org.id,
        name="ironlog",
        environment="production",
        healthcheck_url="https://ironlog.example.com/health",
        github_repo=None,  # Not configured
    )
    shop_service = Service(
        id=uuid4(),
        organization_id=org.id,
        name="shop-api",
        environment="staging",
        healthcheck_url="http://shop-api:3001/health",
        github_repo="AegisOps/shop-api",
    )
    session.add_all([ironlog_service, shop_service])
    session.commit()

    yield session, org, ironlog_service, shop_service
    session.close()


def test_ironlog_incident_never_queries_shop_api(test_db_session):
    session, org, ironlog_service, _ = test_db_session
    incident = Incident(
        id=uuid4(),
        organization_id=org.id,
        service_id=ironlog_service.id,
        title="Ironlog Service Outage",
        severity="critical",
        status="open",
        fingerprint="fp123",
        started_at=datetime.now(UTC),
    )
    session.add(incident)
    session.commit()

    scope = Scope(
        organization_id=org.id,
        service_id=ironlog_service.id,
        run_id=uuid4(),
    )
    gateway = ReadOnlyToolGateway(
        scope=scope,
        incident=incident,
        db_session=session,
    )

    # 1. Search logs: must query {service_name="ironlog"}, never shop-api
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = Mock()
        mock_resp.read.return_value = json.dumps({"data": {"result": []}}).encode("utf-8")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp

        res = gateway.search_service_logs(query="outage", limit=5)
        assert res["status"] == "NO_LOGS"
        assert res["uninstrumented"] is True

        called_url = mock_urlopen.call_args.args[0].full_url
        query_params = parse_qs(urlsplit(called_url).query)
        assert "shop-api" not in query_params["query"][0]
        assert '{service_name="ironlog"} |= "outage"' == query_params["query"][0]

    # 2. Deployments: ironlog has no github_repo, must NOT fall back to AegisOps/shop-api
    deploy_res = gateway.get_recent_deployments(limit=5)
    assert deploy_res["repository"] is None
    assert deploy_res["uninstrumented"] is True
    assert "No deployment repository configured" in deploy_res["limitation"]

    # 3. Metrics: must query service="ironlog" and not route="/checkout"
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = Mock()
        mock_resp.read.return_value = json.dumps({"data": {"result": []}}).encode("utf-8")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp

        metric_res = gateway.query_service_metrics("http_requests_total")
        assert metric_res["uninstrumented"] is True
        called_url = mock_urlopen.call_args.args[0].full_url
        query_params = parse_qs(urlsplit(called_url).query)
        promql = query_params["query"][0]
        assert 'service="ironlog"' in promql
        assert "/checkout" not in promql


def test_trace_summary_cross_service_isolation(test_db_session):
    session, org, ironlog_service, _ = test_db_session
    scope = Scope(
        organization_id=org.id,
        service_id=ironlog_service.id,
        run_id=uuid4(),
    )
    gateway = ReadOnlyToolGateway(
        scope=scope,
        db_session=session,
    )

    with patch("apps.api.app.telemetry.tempo.TempoClient.get_trace_summary") as mock_get_summary:
        mock_summary = Mock()
        mock_summary.service_name = "other-service"
        mock_span = Mock()
        mock_span.service_name = "foreign-api"
        mock_summary.spans = [mock_span]
        mock_get_summary.return_value = mock_summary

        trace_res = gateway.get_trace_summary("0123456789abcdef0123456789abcdef")
        assert "error" in trace_res
        assert "Access denied" in trace_res["error"]
        assert "ironlog" in trace_res["error"]


def test_gateway_mixed_service_trace_filters_foreign_spans(test_db_session):
    session, org, ironlog_service, _ = test_db_session
    run_id = uuid4()
    incident = Incident(
        id=uuid4(),
        organization_id=org.id,
        service_id=ironlog_service.id,
        title="Ironlog Trace Test",
        severity="critical",
        status="open",
        fingerprint="fp_trace_test",
        started_at=datetime.now(UTC),
    )
    session.add(incident)
    session.flush()

    scope = Scope(
        organization_id=org.id,
        service_id=ironlog_service.id,
        run_id=run_id,
    )
    inv = InvestigationRun(
        id=run_id,
        incident_id=incident.id,
        organization_id=org.id,
        service_id=ironlog_service.id,
        status="running",
        started_at=datetime.now(UTC),
    )
    session.add(inv)
    session.commit()
    gateway = ReadOnlyToolGateway(
        scope=scope,
        incident=incident,
        run_record=inv,
        db_session=session,
    )

    with patch("apps.api.app.telemetry.tempo.TempoClient.get_trace_summary") as mock_get_summary:
        mock_summary = Mock()
        mock_summary.service_name = "ironlog"

        span_authorized = Mock()
        span_authorized.span_id = "span-auth-01"
        span_authorized.parent_span_id = None
        span_authorized.name = "GET /api/health"
        span_authorized.service_name = "ironlog"
        span_authorized.start_time_unix_nano = 1_000_000_000
        span_authorized.end_time_unix_nano = 1_010_000_000
        span_authorized.duration_ms = 10.0
        span_authorized.status_code = "STATUS_CODE_OK"
        span_authorized.attributes = {
            "organization_id": str(org.id),
            "service_id": str(ironlog_service.id),
        }

        span_foreign_service = Mock()
        span_foreign_service.span_id = "span-foreign-02"
        span_foreign_service.parent_span_id = "span-auth-01"
        span_foreign_service.name = "POST /charge"
        span_foreign_service.service_name = "external-stripe-gateway"
        span_foreign_service.start_time_unix_nano = 1_002_000_000
        span_foreign_service.end_time_unix_nano = 1_008_000_000
        span_foreign_service.duration_ms = 6.0
        span_foreign_service.status_code = "STATUS_CODE_OK"
        span_foreign_service.attributes = {}

        span_foreign_tenant = Mock()
        span_foreign_tenant.span_id = "span-foreign-tenant-03"
        span_foreign_tenant.parent_span_id = None
        span_foreign_tenant.name = "GET /api/health"
        span_foreign_tenant.service_name = "ironlog"
        span_foreign_tenant.start_time_unix_nano = 1_003_000_000
        span_foreign_tenant.end_time_unix_nano = 1_007_000_000
        span_foreign_tenant.duration_ms = 4.0
        span_foreign_tenant.status_code = "STATUS_CODE_OK"
        span_foreign_tenant.attributes = {
            "organization_id": "00000000-0000-0000-0000-foreign999999",
        }

        mock_summary.spans = [span_authorized, span_foreign_service, span_foreign_tenant]
        mock_get_summary.return_value = mock_summary

        trace_res = gateway.get_trace_summary("0123456789abcdef0123456789abcdef")
        assert "error" not in trace_res
        assert trace_res["span_count"] == 1
        assert len(trace_res["spans"]) == 1
        assert trace_res["spans"][0]["span_id"] == "span-auth-01"
        assert trace_res["spans"][0]["service"] == "ironlog"

        # Evidence item snippet in database must only contain authorized spans
        ev_id = trace_res["evidence_id"]
        ev = session.query(EvidenceItem).filter(EvidenceItem.evidence_id == ev_id).first()
        assert ev is not None
        assert "span-auth-01" in ev.redacted_snippet
        assert "span-foreign-02" not in ev.redacted_snippet
        assert "span-foreign-tenant-03" not in ev.redacted_snippet


def test_production_remediation_proposal_disallowed(test_db_session):
    session, org, ironlog_service, _ = test_db_session
    # ironlog_service.environment is "production"
    incident = Incident(
        id=uuid4(),
        organization_id=org.id,
        service_id=ironlog_service.id,
        title="Ironlog Service Outage",
        severity="critical",
        status="open",
        fingerprint="fp123",
        started_at=datetime.now(UTC),
    )
    session.add(incident)
    session.commit()

    scope = Scope(
        organization_id=org.id,
        service_id=ironlog_service.id,
        run_id=uuid4(),
    )
    gateway = ReadOnlyToolGateway(
        scope=scope,
        incident=incident,
        db_session=session,
    )

    with pytest.raises(ValueError, match="restricted to environments"):
        gateway.create_remediation_proposal(
            action_catalog_id="restart_demo_service",
            parameters={
                "service_name": "ironlog",
                "reason": "Testing restart",
                "grace_period_seconds": 10,
            },
            reason="Service is down",
            expected_outcome="Restores service",
        )


def test_redaction_comprehensive():
    jwt_part = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    sample = (
        "Connected to mongodb+srv://admin_user:P@ssw0rd123!@cluster0.abcde.mongodb.net/ironlog_db "
        f"User token: {jwt_part} "
        "Cookie: session_id=s%3Aabc123xyz.cookie_signature; other=val "
        "SSN: 000-12-3456 "
        "password=SecretKey!999 "
        "Bearer super-secret-bearer-token-456"
    )
    redacted = redact_sensitive_text(sample)
    assert "P@ssw0rd123!" not in redacted
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
    assert "[REDACTED_JWT]" in redacted
    assert "s%3Aabc123xyz.cookie_signature" not in redacted
    assert "[REDACTED_COOKIE]" in redacted
    assert "000-12-3456" not in redacted
    assert "[REDACTED_SSN]" in redacted
    assert "SecretKey!999" not in redacted
    assert "super-secret-bearer-token-456" not in redacted
    assert "admin_user:[REDACTED]@" in redacted


def test_incident_title_secrets_redacted_before_evidence_persistence(test_db_session):
    """Prove incident-title secrets never reach evidence ledger or database (Priority 0.4)."""
    session, org, ironlog_service, _ = test_db_session
    raw_title = (
        "Outage on mongodb+srv://db_admin:P@ssw0rd999!@cluster0.ironlog.io/prod "
        "with Bearer secret-auth-token-123 and cookie session=cookie_value_789"
    )
    incident = Incident(
        id=uuid4(),
        organization_id=org.id,
        service_id=ironlog_service.id,
        title=raw_title,
        severity="critical",
        status="open",
        fingerprint="fp-secrets",
        started_at=datetime.now(UTC),
    )
    session.add(incident)
    session.commit()

    from apps.api.app.models import EvidenceItem, InvestigationRun

    inv = InvestigationRun(
        id=uuid4(),
        incident_id=incident.id,
        organization_id=org.id,
        service_id=ironlog_service.id,
        status="running",
    )
    session.add(inv)
    session.commit()

    scope = Scope(
        organization_id=org.id,
        service_id=ironlog_service.id,
        run_id=inv.id,
    )
    gateway = ReadOnlyToolGateway(
        scope=scope,
        incident=incident,
        run_record=inv,
        db_session=session,
    )

    snapshot = gateway.get_incident_snapshot()

    # 1. Returned title must be redacted
    assert "P@ssw0rd999!" not in snapshot["title"]
    assert "secret-auth-token-123" not in snapshot["title"]
    assert "cookie_value_789" not in snapshot["title"]
    assert "[REDACTED]" in snapshot["title"]
    assert "[REDACTED_COOKIE]" in snapshot["title"]

    # 2. In-memory evidence ledger must be redacted
    ev_item = gateway.evidence_ledger[snapshot["evidence_id"]]
    assert "P@ssw0rd999!" not in ev_item.redacted_snippet
    assert "secret-auth-token-123" not in ev_item.redacted_snippet
    assert "cookie_value_789" not in ev_item.redacted_snippet

    # 3. Persisted database EvidenceItem must be redacted
    db_ev = session.query(EvidenceItem).filter(EvidenceItem.run_id == inv.id).first()
    assert db_ev is not None
    assert "P@ssw0rd999!" not in db_ev.redacted_snippet
    assert "secret-auth-token-123" not in db_ev.redacted_snippet
    assert "cookie_value_789" not in db_ev.redacted_snippet
    assert "[REDACTED]" in db_ev.redacted_snippet
