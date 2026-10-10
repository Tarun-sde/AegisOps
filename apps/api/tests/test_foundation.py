from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.app import main
from apps.api.app.schemas import Approval, Evidence, InvestigationResult, Scope, validate_evidence


@pytest.fixture
def scope():
    return Scope(organization_id=UUID(int=1), service_id=UUID(int=2), run_id=UUID(int=3))


@pytest.fixture
def evidence(scope):
    return Evidence(
        **scope.model_dump(),
        evidence_id="ev_1",
        source="synthetic",
        observed_at=datetime.now(UTC),
        redacted_snippet="Synthetic checkout error",
        locator="fixture:checkout",
    )


@pytest.fixture
def result():
    return InvestigationResult.model_validate(
        {
            "status": "complete",
            "summary": "Synthetic checkout error",
            "hypotheses": [
                {
                    "cause": "Synthetic exception",
                    "confidence": "medium",
                    "supporting_evidence": [
                        {"evidence_id": "ev_1", "supports": "Exception observed"}
                    ],
                }
            ],
        }
    )


def test_health_and_no_product_routes():
    with TestClient(main.app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "api"}
        assert client.post("/api/v1/actions/proposals").status_code == 404


def test_ready_success(monkeypatch):
    monkeypatch.setattr(main, "check_postgres", AsyncMock())
    monkeypatch.setattr(main, "check_redis", AsyncMock())
    with TestClient(main.app) as client:
        assert client.get("/readyz").json() == {
            "status": "ready",
            "checks": {"postgres": "ok", "redis": "ok"},
        }


@pytest.mark.parametrize("failure", [TimeoutError, OSError, KeyError, ValueError])
def test_ready_fails_closed_without_secret_details(monkeypatch, failure):
    monkeypatch.setattr(main, "check_postgres", AsyncMock(side_effect=failure("SECRET_PASSWORD")))
    monkeypatch.setattr(main, "check_redis", AsyncMock())
    with TestClient(main.app) as client:
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["checks"]["postgres"] == "unavailable"
        assert "SECRET_PASSWORD" not in response.text


def test_valid_evidence(result, scope, evidence):
    assert validate_evidence(result, scope=scope, returned_ledger={"ev_1": evidence}) == result


@pytest.mark.parametrize("field", ["organization_id", "service_id", "run_id"])
def test_reject_cross_scope(field, result, scope, evidence):
    alien = evidence.model_copy(update={field: uuid4()})
    with pytest.raises(ValueError, match="outside"):
        validate_evidence(result, scope=scope, returned_ledger={"ev_1": alien})


def test_reject_unreturned_id(result, scope):
    with pytest.raises(ValueError, match="Unknown"):
        validate_evidence(result, scope=scope, returned_ledger={})


def test_reject_fabricated_contradiction(result, scope, evidence):
    payload = result.model_dump()
    payload["hypotheses"][0]["contradicting_evidence_ids"] = ["invented"]
    with pytest.raises(ValueError, match="Unknown"):
        validate_evidence(
            InvestigationResult.model_validate(payload),
            scope=scope,
            returned_ledger={"ev_1": evidence},
        )


def test_reject_mismatched_ledger_key(result, scope, evidence):
    with pytest.raises(ValueError, match="Unknown"):
        validate_evidence(
            result,
            scope=scope,
            returned_ledger={"ev_1": evidence.model_copy(update={"evidence_id": "ev_2"})},
        )


def test_action_allowlist(result, scope, evidence):
    payload = result.model_dump()
    payload["suggested_action_catalog_ids"] = ["restart_production"]
    with pytest.raises(ValueError, match="catalog"):
        validate_evidence(
            InvestigationResult.model_validate(payload),
            scope=scope,
            returned_ledger={"ev_1": evidence},
        )


@pytest.mark.parametrize(
    "change",
    [
        {"hypotheses": []},
        {"extra_authority": "execute"},
        {"summary": ""},
        {"summary": "x" * 4001},
        {"status": "inconclusive"},
    ],
)
def test_malformed_result(change, result):
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(result.model_dump() | change)


def test_confidence_is_not_numeric(result):
    payload = result.model_dump()
    payload["hypotheses"][0]["confidence"] = 0.94
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(payload)


def test_naive_timestamps_rejected(evidence):
    with pytest.raises(ValidationError):
        Evidence.model_validate(evidence.model_dump() | {"observed_at": "2026-10-10T12:00:00"})


def test_approval_contract_rejects_production_and_expiry():
    data = dict(
        proposal_id=uuid4(),
        organization_id=uuid4(),
        service_id=uuid4(),
        environment="staging",
        action_catalog_id="demo_restart",
        payload_sha256="a" * 64,
        approver_id=uuid4(),
        decision="approved",
        decided_at="2026-10-10T12:00:00Z",
        expires_at="2026-10-10T12:10:00Z",
    )
    assert Approval.model_validate(data).environment == "staging"
    for update in (
        {"environment": "production"},
        {"expires_at": data["decided_at"]},
        {"payload_sha256": "invalid"},
    ):
        with pytest.raises(ValidationError):
            Approval.model_validate(data | update)
