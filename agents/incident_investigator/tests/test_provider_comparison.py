"""No live providers: exercise the real ADK/LiteLLM path with an HTTP test double."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from agents.incident_investigator.free_tier import FreeTierEvidence, require_free_tier
from agents.incident_investigator.spike import RequestBudget, run_spike

KEY = "synthetic-test-key-not-a-credential"


def tier_record(provider="groq"):
    return {
        "provider": provider,
        "tier": "free",
        "key_sha256": hashlib.sha256(KEY.encode()).hexdigest(),
        "account_reference": "synthetic-test-account",
        "source": "groq_organization_billing"
        if provider == "groq"
        else "google_ai_studio_project_billing",
        "verified_at": datetime.now(UTC).isoformat(),
        "verified_by": "operator",
    }


def write_evidence(tmp_path, provider="groq", **changes):
    path = tmp_path / "tier.json"
    path.write_text(json.dumps(tier_record(provider) | changes))
    return path


@pytest.mark.parametrize(
    "changes",
    [
        {"tier": "paid"},
        {"tier": "unknown"},
        {"key_sha256": "0" * 64},
        {"source": "google_ai_studio_project_billing"},
        {"verified_by": "pricing_page"},
        {"verified_at": (datetime.now(UTC) - timedelta(hours=2)).isoformat()},
        {"verified_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat()},
        {"verified_at": "2026-10-10T10:00:00"},
    ],
)
def test_reject_unverified_or_mismatched_tier(tmp_path, changes):
    with pytest.raises(ValueError):
        require_free_tier(write_evidence(tmp_path, **changes), "groq", KEY)


def test_tier_must_match_key_and_provider(tmp_path):
    path = write_evidence(tmp_path)
    assert require_free_tier(path, "groq", KEY).tier == "free"
    with pytest.raises(ValueError):
        require_free_tier(path, "gemini", KEY)
    with pytest.raises(ValueError):
        require_free_tier(path, "groq", "different-key")


@pytest.mark.parametrize(
    "provider,key_name", [("gemini", "GOOGLE_API_KEY"), ("groq", "GROQ_API_KEY")]
)
async def test_missing_tier_blocks_before_any_http(monkeypatch, provider, key_name):
    monkeypatch.setenv(key_name, KEY)
    send = AsyncMock(side_effect=AssertionError("Network must not be reached"))
    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    with pytest.raises(ValueError, match="reviewed free-tier"):
        await run_spike(live=True, provider=provider)
    send.assert_not_called()


async def test_paid_ceiling_rejected_even_with_free_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    with pytest.raises(ValueError, match="Paid requests disabled"):
        await run_spike(
            live=True,
            provider="groq",
            max_usd=Decimal("0.01"),
            tier_evidence=write_evidence(tmp_path),
        )


async def test_groq_byte_budget_and_expiring_evidence():
    evidence = FreeTierEvidence.model_validate(tier_record())
    budget = RequestBudget(None, Decimal(0), evidence=evidence, key=KEY)
    request = LlmRequest(contents=[types.Content(parts=[types.Part(text="x" * 16001)])])
    with pytest.raises(ValueError, match="byte budget"):
        await budget.before_model(None, request)
    assert budget.calls == 0
    budget.evidence = evidence.model_copy(
        update={"verified_at": datetime.now(UTC) - timedelta(hours=2)}
    )
    with pytest.raises(ValueError, match="stale"):
        await budget.before_model(None, LlmRequest())


@pytest.mark.parametrize("scenario", ["supported", "conflicting"])
async def test_groq_real_adk_bridge_with_mock_http(tmp_path, monkeypatch, scenario):
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    requests = []

    async def send(client, request, **kwargs):
        assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer " + KEY
        body = json.loads(request.content)
        requests.append(body)
        assert body["model"] == "openai/gpt-oss-120b"
        assert body.get("max_tokens", body.get("max_completion_tokens")) == 2048
        assert body["reasoning_effort"] == "low"
        assert not body.get("response_format")
        names = {tool["function"]["name"] for tool in body["tools"]}
        assert names == {"get_log_snippets", "set_model_response"}
        if len(requests) == 1:
            name, arguments = "get_log_snippets", {}
        else:
            returned = next(m for m in body["messages"] if m["role"] == "tool")
            assert "UNTRUSTED_SOURCE" in returned["content"]
            assert "syn_log_1" in returned["content"]
            assert "syn_log_2" in returned["content"]
            name = "set_model_response"
            arguments = {
                "status": "complete" if scenario == "supported" else "inconclusive",
                "summary": "Offline HTTP test double, not a live model result",
                "hypotheses": [
                    {
                        "cause": "Synthetic checkout failure",
                        "confidence": "low",
                        "supporting_evidence": [
                            {"evidence_id": "syn_log_1", "supports": "Failure observed"}
                        ],
                        "contradicting_evidence_ids": ["syn_log_2"]
                        if scenario == "conflicting"
                        else [],
                    }
                ],
                "limitations": ["Offline synthetic transport"],
            }
        return httpx.Response(
            200,
            request=request,
            json={
                "id": "synthetic-response",
                "object": "chat.completion",
                "created": 0,
                "model": "openai/gpt-oss-120b",
                "service_tier": "on_demand",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": f"test_call_{len(requests)}",
                                    "type": "function",
                                    "function": {"name": name, "arguments": json.dumps(arguments)},
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    report = await run_spike(
        scenario, live=True, provider="groq", tier_evidence=write_evidence(tmp_path)
    )
    assert report["status"] == "PASSED", report["error"]
    assert len(requests) == report["model_calls"] == 2
    assert report["tool_calls"] == 1
    assert report["result"]["status"] == ("complete" if scenario == "supported" else "inconclusive")
    assert report["model_responses"][0]["usage"]["prompt_token_count"] == 100
    assert report["estimated_cost_usd"] == "0"
    assert KEY not in json.dumps(report)


@pytest.mark.parametrize("status", [401, 429, 500])
async def test_groq_http_error_is_sanitized_without_retry(tmp_path, monkeypatch, status):
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    requests = []

    async def send(client, request, **kwargs):
        requests.append(request)
        return httpx.Response(
            status,
            request=request,
            json={"error": {"message": "SECRET_PROVIDER_ERROR " + KEY, "type": "test_error"}},
        )

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    report = await run_spike(live=True, provider="groq", tier_evidence=write_evidence(tmp_path))
    assert report["status"] == "FAILED"
    assert report["error"]["http_status"] == status
    assert len(requests) == report["model_calls"] == 1
    assert report["tool_calls"] == 0
    assert KEY not in json.dumps(report)
    assert "SECRET_PROVIDER_ERROR" not in json.dumps(report)
    assert report["model_responses"] == []
    assert report["estimated_cost_usd"] is None


async def test_gemini_free_budget_counts_input_without_paid_reservation():
    from types import SimpleNamespace

    count = AsyncMock(return_value=SimpleNamespace(total_tokens=100))
    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(count_tokens=count)))
    evidence = FreeTierEvidence.model_validate(tier_record("gemini"))
    budget = RequestBudget(client, Decimal(0), evidence=evidence, key=KEY)
    await budget.before_model(None, LlmRequest())
    assert budget.calls == 1
    assert budget.reserved_usd == 0
    count.assert_awaited_once()
    count.return_value.total_tokens = 16001
    with pytest.raises(ValueError, match="Input token budget"):
        await budget.before_model(None, LlmRequest())
    assert budget.calls == 1


@pytest.mark.parametrize("fault", ["invented_citation", "wrong_status", "missing_contradiction"])
async def test_failed_validation_retains_run_events(monkeypatch, fault):
    from agents.incident_investigator.spike import OfflineModel

    original = OfflineModel.generate_content_async

    async def altered(self, llm_request, stream=False):
        async for response in original(self, llm_request, stream):
            for part in response.content.parts or []:
                call = part.function_call
                if call is None or call.name != "set_model_response":
                    continue
                if fault == "invented_citation":
                    call.args["hypotheses"][0]["supporting_evidence"][0]["evidence_id"] = "invented"
                elif fault == "wrong_status":
                    call.args["status"] = "complete"
                else:
                    call.args["hypotheses"][0]["contradicting_evidence_ids"] = []
            yield response

    monkeypatch.setattr(OfflineModel, "generate_content_async", altered)
    report = await run_spike("conflicting")
    assert report["status"] == "FAILED"
    assert report["error"]["type"] == "ValueError"
    assert report["model_calls"] == 2
    assert report["tool_calls"] == 1
    assert len(report["returned_evidence"]) == 2
    assert report["events"]


async def test_cleanup_failure_does_not_erase_measurements(monkeypatch):
    from google.adk.runners import Runner

    original = Runner.close

    async def close(self):
        await original(self)
        raise RuntimeError("SECRET_CLEANUP_ERROR")

    monkeypatch.setattr(Runner, "close", close)
    report = await run_spike()
    assert report["status"] == "FAILED"
    assert report["model_calls"] == 2
    assert report["tool_calls"] == 1
    assert "SECRET_CLEANUP_ERROR" not in json.dumps(report)
