"""Comprehensive targeted quality tests for Phase 2 corrective fix.

Covers scenarios T01 - T10:
- T01: Controlled application exception (S01 checkout 500 fault)
- T02: Genuine database pool exhaustion fixture
- T03: Insufficient evidence (honest INCONCLUSIVE)
- T04: Misleading logs resistance
- T05: Fabricated citation rejection
- T06: Cross-run citation rejection
- T07: Offline model authenticity
- T08: Live Gemini smoke test (bounded or BLOCKED on quota)
- T09: Missing live credentials rejection (no silent fallback)
- T10: Confidence schema contract (qualitative only)
"""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from pydantic import ValidationError

from agents.incident_investigator.agent import run_investigation_agent
from agents.incident_investigator.tools.gateway import ReadOnlyToolGateway
from agents.incident_investigator.validator import (
    validate_citation_integrity,
    validate_claim_support,
)
from apps.api.app.schemas import (
    Evidence,
    EvidenceRef,
    Hypothesis,
    HypothesisRead,
    InvestigationResult,
    Scope,
)

load_dotenv()


@pytest.fixture
def run_scope() -> Scope:
    return Scope(
        organization_id=uuid4(),
        service_id=uuid4(),
        run_id=uuid4(),
    )


# ---------------------------------------------------------------------------
# T01 — Controlled application exception (S01)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t01_controlled_application_exception(run_scope: Scope) -> None:
    gateway = ReadOnlyToolGateway(scope=run_scope)
    ev_log = "ev_log_s01_app_exc"
    ev_metric = "ev_metric_s01_500"

    gateway.evidence_ledger[ev_log] = Evidence(
        organization_id=run_scope.organization_id,
        service_id=run_scope.service_id,
        run_id=run_scope.run_id,
        evidence_id=ev_log,
        source="logs",
        observed_at=datetime.now(UTC),
        locator="loki:shop-api",
        redacted_snippet=(
            '{"event":"http_request_error","message":"HTTP 500: checkout payment '
            'gateway failure on POST /checkout","error_category":"APPLICATION_EXCEPTION",'
            '"error_code":"CHECKOUT_GATEWAY_TIMEOUT"}'
        ),
    )
    gateway.evidence_ledger[ev_metric] = Evidence(
        organization_id=run_scope.organization_id,
        service_id=run_scope.service_id,
        run_id=run_scope.run_id,
        evidence_id=ev_metric,
        source="metrics",
        observed_at=datetime.now(UTC),
        locator="promql:http_5xx_error_rate",
        redacted_snippet='[{"labels":{"route":"/checkout","status_code":"500"},"value":35.0}]',
    )

    result = await run_investigation_agent(gateway, execution_mode="offline")
    assert result.status == "complete"
    assert len(result.hypotheses) == 1
    hypo = result.hypotheses[0]

    # Must identify payment gateway timeout / application exception
    assert "payment" in hypo.cause.lower() or "gateway" in hypo.cause.lower()
    # Must NOT identify database pool exhaustion
    assert "database connection pool" not in hypo.cause.lower()
    assert hypo.confidence in ("medium", "high")
    assert len(hypo.supporting_evidence) >= 1


# ---------------------------------------------------------------------------
# T02 — Genuine database pool exhaustion fixture
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t02_database_pool_exhaustion_fixture(run_scope: Scope) -> None:
    gateway = ReadOnlyToolGateway(scope=run_scope)
    ev_log = "ev_log_db_pool"
    ev_metric = "ev_metric_db_timeouts"

    gateway.evidence_ledger[ev_log] = Evidence(
        organization_id=run_scope.organization_id,
        service_id=run_scope.service_id,
        run_id=run_scope.run_id,
        evidence_id=ev_log,
        source="logs",
        observed_at=datetime.now(UTC),
        locator="loki:shop-api",
        redacted_snippet=(
            '{"level":"error","message":"FATAL: remaining connection slots are reserved '
            'for non-replication superuser connections; pool exhaustion detected in pg_pool"}'
        ),
    )
    gateway.evidence_ledger[ev_metric] = Evidence(
        organization_id=run_scope.organization_id,
        service_id=run_scope.service_id,
        run_id=run_scope.run_id,
        evidence_id=ev_metric,
        source="metrics",
        observed_at=datetime.now(UTC),
        locator="promql:http_5xx_error_rate",
        redacted_snippet='[{"labels":{"route":"/checkout","status_code":"500"},"value":12.0}]',
    )

    result = await run_investigation_agent(gateway, execution_mode="offline")
    assert result.status == "complete"
    assert len(result.hypotheses) == 1
    hypo = result.hypotheses[0]
    # In T02, the agent correctly identifies database pool exhaustion
    assert "pool exhaustion" in hypo.cause.lower() or "connection pool" in hypo.cause.lower()
    assert "payment processing gateway" not in hypo.cause.lower()


# ---------------------------------------------------------------------------
# T03 — Insufficient evidence (honest INCONCLUSIVE)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t03_insufficient_evidence_inconclusive(run_scope: Scope) -> None:
    gateway = ReadOnlyToolGateway(scope=run_scope)
    ev_metric = "ev_metric_zero_errs"
    gateway.evidence_ledger[ev_metric] = Evidence(
        organization_id=run_scope.organization_id,
        service_id=run_scope.service_id,
        run_id=run_scope.run_id,
        evidence_id=ev_metric,
        source="metrics",
        observed_at=datetime.now(UTC),
        locator="promql:http_5xx_error_rate",
        redacted_snippet='[{"labels":{"route":"/checkout","status_code":"200"},"value":0.0}]',
    )

    result = await run_investigation_agent(
        gateway, scenario="inconclusive", execution_mode="offline"
    )
    assert result.status == "inconclusive"
    assert len(result.missing_evidence) >= 1
    assert "No HTTP 500" in result.missing_evidence[0] or "insufficient" in result.summary.lower()


# ---------------------------------------------------------------------------
# T04 — Misleading logs resistance
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t04_misleading_logs_resistance(run_scope: Scope) -> None:
    gateway = ReadOnlyToolGateway(scope=run_scope)
    ev_log = "ev_log_misleading"

    # Misleading log text mentions DB in user body, but code is CHECKOUT_GATEWAY_TIMEOUT
    gateway.evidence_ledger[ev_log] = Evidence(
        organization_id=run_scope.organization_id,
        service_id=run_scope.service_id,
        run_id=run_scope.run_id,
        evidence_id=ev_log,
        source="logs",
        observed_at=datetime.now(UTC),
        locator="loki:shop-api",
        redacted_snippet=(
            '{"event":"http_request_error","message":"HTTP 500: checkout payment '
            'gateway failure on POST /checkout (user comment: maybe database down?)",'
            '"error_category":"APPLICATION_EXCEPTION","error_code":"CHECKOUT_GATEWAY_TIMEOUT"}'
        ),
    )

    result = await run_investigation_agent(gateway, execution_mode="offline")
    assert result.status == "complete"
    assert len(result.hypotheses) == 1
    hypo = result.hypotheses[0]
    # Agent identifies the true payment gateway timeout and qualifies confidence or notes assumption
    assert "payment" in hypo.cause.lower() or "gateway" in hypo.cause.lower()
    assert hypo.confidence in ("medium", "high")
    if hypo.confidence == "medium":
        assert len(hypo.unverified_assumptions) >= 1


# ---------------------------------------------------------------------------
# T05 — Fabricated citation rejection
# ---------------------------------------------------------------------------
def test_t05_fabricated_citation_rejection(run_scope: Scope) -> None:
    res = InvestigationResult(
        status="complete",
        summary="Fabricated root cause claim.",
        hypotheses=[
            Hypothesis(
                cause="Fabricated cause",
                confidence="high",
                supporting_evidence=[
                    EvidenceRef(evidence_id="ev_fake_999999", supports="Invented proof")
                ],
            )
        ],
    )
    with pytest.raises(ValueError, match="Unknown evidence reference"):
        validate_citation_integrity(res, scope=run_scope, returned_ledger={})


# ---------------------------------------------------------------------------
# T06 — Cross-run citation rejection
# ---------------------------------------------------------------------------
def test_t06_cross_run_citation_rejection(run_scope: Scope) -> None:
    other_run_id = uuid4()
    foreign_evidence = Evidence(
        organization_id=run_scope.organization_id,
        service_id=run_scope.service_id,
        run_id=other_run_id,  # belongs to a different run
        evidence_id="ev_log_cross_run",
        source="logs",
        observed_at=datetime.now(UTC),
        locator="loki:shop-api",
        redacted_snippet='{"message":"error from past run"}',
    )
    res = InvestigationResult(
        status="complete",
        summary="Cross-run citation claim.",
        hypotheses=[
            Hypothesis(
                cause="Claim from other run",
                confidence="high",
                supporting_evidence=[
                    EvidenceRef(evidence_id="ev_log_cross_run", supports="Foreign proof")
                ],
            )
        ],
    )
    with pytest.raises(ValueError, match="outside the authorized run scope"):
        validate_citation_integrity(
            res, scope=run_scope, returned_ledger={"ev_log_cross_run": foreign_evidence}
        )


# ---------------------------------------------------------------------------
# T07 — Offline model authenticity
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t07_offline_model_authenticity(run_scope: Scope) -> None:
    gateway = ReadOnlyToolGateway(scope=run_scope)
    res = await run_investigation_agent(gateway, execution_mode="offline")
    assert res.execution_mode == "offline"
    assert res.provider == "offline"
    # Never claims Gemini generated offline output
    assert res.provider != "gemini"


# ---------------------------------------------------------------------------
# T08 — Live Gemini smoke test (bounded or BLOCKED on quota)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t08_live_gemini_smoke_test(run_scope: Scope) -> None:
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        pytest.skip("GOOGLE_API_KEY not configured; live test skipped")

    gateway = ReadOnlyToolGateway(scope=run_scope)
    try:
        res = await run_investigation_agent(gateway, use_live_model=True, execution_mode="live")
        assert res.execution_mode == "live"
        assert res.provider == "gemini"
    except Exception as exc:
        err_msg = str(exc)
        # If rate-limited or quota exhausted on free tier, verify that it was cleanly caught
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            pytest.skip(f"Live Gemini Free-tier quota exceeded: {err_msg}")
        elif "404" in err_msg:
            pytest.skip(f"Live Gemini model not found: {err_msg}")
        else:
            raise


# ---------------------------------------------------------------------------
# T09 — Missing live credentials rejection (no silent fallback)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t09_missing_live_credentials_rejection(
    run_scope: Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    gateway = ReadOnlyToolGateway(scope=run_scope)

    # Must raise ValueError and NOT silently fall back to offline model
    with pytest.raises(ValueError, match="Silent fallback to offline model is prohibited"):
        await run_investigation_agent(gateway, execution_mode="live")


# ---------------------------------------------------------------------------
# T10 — Confidence schema contract (qualitative only)
# ---------------------------------------------------------------------------
def test_t10_confidence_schema_contract() -> None:
    # 1. Valid qualitative values accepted
    for valid_conf in ("low", "medium", "high"):
        h = Hypothesis(
            cause="Test cause",
            confidence=valid_conf,  # type: ignore[arg-type]
            supporting_evidence=[EvidenceRef(evidence_id="ev_1", supports="test")],
        )
        assert h.confidence == valid_conf

    # 2. Unsupported numerical confidence rejected at public contract boundary
    with pytest.raises(ValidationError):
        Hypothesis(
            cause="Test cause",
            confidence="0.95",  # type: ignore[arg-type]
            supporting_evidence=[EvidenceRef(evidence_id="ev_1", supports="test")],
        )

    with pytest.raises(ValidationError):
        Hypothesis(
            cause="Test cause",
            confidence=0.95,  # type: ignore[arg-type]
            supporting_evidence=[EvidenceRef(evidence_id="ev_1", supports="test")],
        )

    # 3. Backward-compatible coercion on HypothesisRead for legacy database rows
    legacy_row = {
        "id": uuid4(),
        "run_id": uuid4(),
        "cause": "Legacy cause",
        "confidence": "0.95",
        "supporting_evidence": [{"evidence_id": "ev_1", "supports": "test"}],
        "contradicting_evidence_ids": [],
        "created_at": datetime.now(UTC),
    }
    read_obj = HypothesisRead.model_validate(legacy_row)
    assert read_obj.confidence == "high"  # safely coerced without crash or data corruption


# ---------------------------------------------------------------------------
# Evidence Claim Support Tests: Generic 500s cannot prove DB pool exhaustion
# ---------------------------------------------------------------------------
def test_claim_support_rejects_generic_metrics_for_db_exhaustion(run_scope: Scope) -> None:
    ev_metric = "ev_metric_500"
    ledger = {
        ev_metric: Evidence(
            organization_id=run_scope.organization_id,
            service_id=run_scope.service_id,
            run_id=run_scope.run_id,
            evidence_id=ev_metric,
            source="metrics",
            observed_at=datetime.now(UTC),
            locator="promql:http_5xx",
            redacted_snippet='[{"value": 50.0}]',
        )
    }

    # Hypothesis claims database pool exhaustion but ONLY cites generic HTTP 5xx metric
    bad_res = InvestigationResult(
        status="complete",
        summary="Unsupported DB pool claim",
        hypotheses=[
            Hypothesis(
                cause="Database connection pool exhaustion",
                confidence="high",
                supporting_evidence=[
                    EvidenceRef(evidence_id=ev_metric, supports="Metrics show 500s")
                ],
            )
        ],
    )
    with pytest.raises(
        ValueError,
        match="Generic HTTP 5xx error metrics cannot substantiate database pool exhaustion",
    ):
        validate_claim_support(bad_res, returned_ledger=ledger)
