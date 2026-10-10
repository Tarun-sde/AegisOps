from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agents.incident_investigator.agent import run_investigation_agent
from agents.incident_investigator.tools.gateway import (
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


def test_gateway_budget_and_metrics() -> None:
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

    # 2. Bounded metric query works
    res_metric = gateway.query_service_metrics(metric_name="http_5xx_error_rate", window_minutes=15)
    assert "evidence_id" in res_metric
    ev_id = res_metric["evidence_id"]
    assert ev_id in gateway.evidence_ledger

    # 3. Snapshot works
    snap = gateway.get_incident_snapshot()
    assert "evidence_id" in snap
    assert snap["incident_id"] is not None

    # 4. Search logs works and handles missing server safely
    logs_res = gateway.search_service_logs(query="checkout", limit=10)
    assert "evidence_id" in logs_res

    # 5. Budget enforcement: 12 calls max
    # We have used 4 calls so far. Call 8 more times to exhaust 12 calls.
    for _ in range(8):
        gateway.get_incident_snapshot()

    assert gateway.tool_call_count == 12

    # 13th call must raise BudgetExceededError
    with pytest.raises(BudgetExceededError):
        gateway.get_incident_snapshot()


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
async def test_offline_investigation_supported_scenario() -> None:
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
        scenario="inconclusive",
        use_live_model=False,
    )

    assert result.status == "inconclusive"
    assert len(result.hypotheses) == 0
    assert len(result.missing_evidence) > 0
