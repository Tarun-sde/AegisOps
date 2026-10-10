from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from google.adk.models.llm_request import LlmRequest

from agents.incident_investigator.spike import RequestBudget, SyntheticTool, run_spike
from apps.api.app.schemas import Scope


@pytest.mark.parametrize(
    "scenario,expected", [("supported", "complete"), ("conflicting", "inconclusive")]
)
async def test_real_adk_dispatch_with_fake_model(scenario, expected):
    report = await run_spike(scenario)
    assert report["mode"] == "offline_fake_model_synthetic_tool"
    assert report["tool_calls"] == 1
    assert report["model_calls"] == 2
    assert report["result"]["status"] == expected
    assert len(report["returned_evidence"]) == 2
    assert any(event["tool_responses"] == ["get_log_snippets"] for event in report["events"])
    assert report["actual_billed_usd"] is None


def test_tool_call_cap_and_fixed_scope():
    scope = Scope(organization_id=UUID(int=1), service_id=UUID(int=2), run_id=UUID(int=3))
    tool = SyntheticTool(scope, "supported")
    for _ in range(12):
        tool.get_log_snippets()
    with pytest.raises(ValueError, match="budget"):
        tool.get_log_snippets()
    with pytest.raises(TypeError):
        tool.get_log_snippets(organization_id="alien")
    assert all(item.organization_id == scope.organization_id for item in tool.ledger.values())


async def test_model_call_cap():
    budget = RequestBudget(None, Decimal(0))
    for _ in range(4):
        await budget.before_model(None, LlmRequest())
    with pytest.raises(ValueError, match="budget"):
        await budget.before_model(None, LlmRequest())


@pytest.mark.parametrize("count,max_usd", [(None, "0.1"), (16001, "0.1"), (1000, "0.001")])
async def test_live_budget_rejects_before_generation(count, max_usd):
    client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                count_tokens=AsyncMock(return_value=SimpleNamespace(total_tokens=count))
            )
        )
    )
    budget = RequestBudget(client, Decimal(max_usd))
    with pytest.raises(ValueError):
        await budget.before_model(None, LlmRequest())
    assert budget.calls == 0


async def test_missing_key_fails_before_network(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="BLOCKED"):
        await run_spike(live=True, max_usd=Decimal("0.10"))


@pytest.mark.parametrize("ceiling", ["0", "NaN", "Infinity", "-1", "0.11"])
async def test_invalid_live_spend_fails_before_network(monkeypatch, ceiling):
    monkeypatch.setenv("GOOGLE_API_KEY", "synthetic-placeholder-not-a-real-key")
    with pytest.raises(ValueError, match="ceiling"):
        await run_spike(live=True, max_usd=Decimal(ceiling))
