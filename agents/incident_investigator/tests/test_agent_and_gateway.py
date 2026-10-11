from datetime import UTC, datetime
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

from agents.incident_investigator.agent import run_investigation_agent
from agents.incident_investigator.tools.gateway import (
    ALLOWED_METRICS,
    BudgetExceededError,
    ReadOnlyToolGateway,
)
from agents.incident_investigator.tools.redaction import redact_sensitive_text
from apps.api.app.schemas import (
    Evidence,
    EvidenceRef,
    Hypothesis,
    InvestigationResult,
    Scope,
    validate_evidence,
)

pytestmark = pytest.mark.usefixtures("telemetry_http")


def test_redact_sensitive_telemetry() -> None:
    text = (
        "Authorization: Bearer secret_token_12345 "
        "Basic dXNlcjpwYXNz "
        "password=my_super_secret_password "
        "postgres://user:superpass@localhost:5432/db"
    )
    redacted = redact_sensitive_text(text)
    assert "secret_token_12345" not in redacted
    assert "dXNlcjpwYXNz" not in redacted
    assert "my_super_secret_password" not in redacted
    assert "superpass" not in redacted
    assert "[REDACTED]" in redacted


@pytest.mark.parametrize("telemetry_http", ["supported"], indirect=True)
def test_gateway_budget_and_metrics(telemetry_http) -> None:
    scope = Scope(
        organization_id=uuid4(),
        service_id=uuid4(),
        run_id=uuid4(),
    )
    gateway = ReadOnlyToolGateway(scope=scope)

    # 1. Invalid metric query rejected
    res_bad = gateway.query_service_metrics(
        metric_name="arbitrary_promql_injection", window_minutes=5
    )
    assert res_bad.get("error") is not None
    telemetry_http.assert_not_called()

    # 2. Bounded metric query works
    res_metric = gateway.query_service_metrics(metric_name="http_5xx_error_rate", window_minutes=15)
    assert "evidence_id" in res_metric
    ev_id = res_metric["evidence_id"]
    assert ev_id in gateway.evidence_ledger
    assert res_metric["series"] == [{"labels": {}, "value": 0.25}]
    metric_url = urlsplit(telemetry_http.call_args.args[0].full_url)
    assert parse_qs(metric_url.query) == {"query": [ALLOWED_METRICS["http_5xx_error_rate"]]}
    assert gateway.evidence_ledger[ev_id].run_id == scope.run_id

    # 3. Snapshot works
    snap = gateway.get_incident_snapshot()
    assert "evidence_id" in snap
    assert snap["incident_id"] is not None

    # 4. Parse the synthetic Loki stream through the real gateway
    logs_res = gateway.search_service_logs(query="checkout", limit=10)
    assert "evidence_id" in logs_res
    assert logs_res["record_count"] == 1
    assert "CHECKOUT_GATEWAY_TIMEOUT" in logs_res["records"][0]["message"]
    log_url = urlsplit(telemetry_http.call_args.args[0].full_url)
    assert parse_qs(log_url.query) == {
        "query": ['{service_name="shop-api"} |= "checkout"'],
        "limit": ["10"],
    }

    # 5. Budget enforcement: 12 calls max
    # We have used 4 calls so far. Call 8 more times to exhaust 12 calls.
    for _ in range(8):
        gateway.get_incident_snapshot()

    assert gateway.tool_call_count == 12

    # 13th call must raise BudgetExceededError
    with pytest.raises(BudgetExceededError):
        gateway.get_incident_snapshot()


@pytest.mark.parametrize("window,expected", [(0, 1), (31, 30)])
def test_gateway_bounds_metric_window(window, expected, monkeypatch):
    gateway = ReadOnlyToolGateway(
        scope=Scope(organization_id=uuid4(), service_id=uuid4(), run_id=uuid4())
    )
    persist = Mock(wraps=gateway._persist_evidence)
    monkeypatch.setattr(gateway, "_persist_evidence", persist)
    result = gateway.query_service_metrics("http_5xx_error_rate", window_minutes=window)
    assert "evidence_id" in result
    assert persist.call_args.kwargs["query_metadata"]["window_minutes"] == expected


@pytest.mark.parametrize("telemetry_http", ["unavailable"], indirect=True)
async def test_unavailable_telemetry_returns_no_fabricated_evidence(telemetry_http):
    gateway = ReadOnlyToolGateway(
        scope=Scope(organization_id=uuid4(), service_id=uuid4(), run_id=uuid4())
    )
    metrics = gateway.query_service_metrics("http_5xx_error_rate")
    logs = gateway.search_service_logs("500")
    assert "Connection refused" in metrics["error"]
    assert "Connection refused" in logs["error"]
    assert metrics["series"] == []
    assert logs["records"] == []
    assert "evidence_id" not in metrics
    assert "evidence_id" not in logs
    assert gateway.evidence_ledger == {}
    result = await run_investigation_agent(gateway, execution_mode="offline")
    assert result.status == "inconclusive"
    assert result.hypotheses == []
    assert result.missing_evidence
    assert {ev.source for ev in gateway.evidence_ledger.values()} == {"alert"}
    assert telemetry_http.call_count == 4


def test_evidence_validator_rejects_hallucinations() -> None:
    scope = Scope(
        organization_id=uuid4(),
        service_id=uuid4(),
        run_id=uuid4(),
    )
    gateway = ReadOnlyToolGateway(scope=scope)
    snap = gateway.get_incident_snapshot()
    real_ev_id = snap["evidence_id"]

    # Valid result
    valid_res = InvestigationResult(
        status="complete",
        summary="Service failure detected.",
        hypotheses=[
            Hypothesis(
                cause="Internal error in checkout",
                confidence="high",
                supporting_evidence=[
                    EvidenceRef(evidence_id=real_ev_id, supports="Snapshot confirms alert")
                ],
                contradicting_evidence_ids=[],
                next_check="Check retry policies",
            )
        ],
        missing_evidence=[],
        suggested_action_catalog_ids=[],
        limitations=[],
    )

    validated = validate_evidence(valid_res, scope=scope, returned_ledger=gateway.evidence_ledger)
    assert validated.status == "complete"
    assert len(validated.hypotheses) == 1

    # Fabricated / Hallucinated evidence ID must raise ValueError in validate_evidence
    hallucinated_res = InvestigationResult(
        status="complete",
        summary="Hallucinated failure cause.",
        hypotheses=[
            Hypothesis(
                cause="Fabricated root cause",
                confidence="high",
                supporting_evidence=[
                    EvidenceRef(evidence_id="ev_fake_99999999", supports="Invented proof")
                ],
                contradicting_evidence_ids=[],
                next_check="None",
            )
        ],
        missing_evidence=[],
        suggested_action_catalog_ids=[],
        limitations=[],
    )

    with pytest.raises(ValueError, match="Unknown evidence reference"):
        validate_evidence(hallucinated_res, scope=scope, returned_ledger=gateway.evidence_ledger)


def test_evidence_validator_rejects_cross_run_and_cross_service() -> None:
    scope = Scope(
        organization_id=uuid4(),
        service_id=uuid4(),
        run_id=uuid4(),
    )

    other_run_ev = Evidence(
        organization_id=scope.organization_id,
        service_id=scope.service_id,
        run_id=uuid4(),  # Different run!
        evidence_id="ev_other_run",
        source="logs",
        observed_at=datetime.now(UTC),
        locator="loki:checkout",
        redacted_snippet="error in checkout",
    )

    ledger = {"ev_other_run": other_run_ev}

    bad_res = InvestigationResult(
        status="complete",
        summary="Cross run reference.",
        hypotheses=[
            Hypothesis(
                cause="Cross-run reference failure",
                confidence="high",
                supporting_evidence=[
                    EvidenceRef(evidence_id="ev_other_run", supports="Proof from another run")
                ],
                contradicting_evidence_ids=[],
                next_check="None",
            )
        ],
        missing_evidence=[],
        suggested_action_catalog_ids=[],
        limitations=[],
    )

    with pytest.raises(ValueError, match="Evidence is outside the authorized run scope"):
        validate_evidence(bad_res, scope=scope, returned_ledger=ledger)


@pytest.mark.asyncio
@pytest.mark.parametrize("telemetry_http", ["supported"], indirect=True)
async def test_offline_investigation_supported_scenario(telemetry_http) -> None:
    scope = Scope(
        organization_id=uuid4(),
        service_id=uuid4(),
        run_id=uuid4(),
    )
    gateway = ReadOnlyToolGateway(scope=scope)

    result = await run_investigation_agent(
        gateway,
        scenario="supported",
        use_live_model=False,
    )

    assert result.status == "complete"
    assert len(result.hypotheses) == 1
    assert result.hypotheses[0].confidence == "high"
    assert "payment processing gateway timeout" in result.hypotheses[0].cause
    assert result.execution_mode == "offline"
    assert result.provider == "offline"
    assert telemetry_http.call_count == 2
    assert len(result.hypotheses[0].supporting_evidence) > 0
    # Every cited evidence must be present in gateway evidence ledger
    for ref in result.hypotheses[0].supporting_evidence:
        assert ref.evidence_id in gateway.evidence_ledger


@pytest.mark.asyncio
async def test_offline_investigation_inconclusive_scenario() -> None:
    scope = Scope(
        organization_id=uuid4(),
        service_id=uuid4(),
        run_id=uuid4(),
    )
    gateway = ReadOnlyToolGateway(scope=scope)

    result = await run_investigation_agent(
        gateway,
        scenario="supported",
        use_live_model=False,
    )

    assert result.status == "inconclusive"
    assert len(result.hypotheses) == 0
    assert len(result.missing_evidence) > 0
