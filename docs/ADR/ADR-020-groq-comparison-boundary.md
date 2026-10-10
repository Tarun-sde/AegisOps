# ADR-020 — Isolated Groq comparison inside the existing ADK spike

- **Date:** 2026-10-10
- **Status:** VERIFIED OFFLINE AND LIVE on Free tier (DEC-235/239/240).
- **Owner / authority:** Developer's explicit Gemini/Groq comparison request; no change to the single-agent architecture.
- **Problem / constraints:** Compare the same synthetic supported and conflicting fixtures on Gemini 3.8 Flash and Groq GPT-OSS 120B, with no paid requests or automatic switching.
- **Decision:** Native ADK Gemini remains provisional primary. A small ADK LiteLlm adapter pinned to LiteLLM 1.104.2 supplies the secondary Groq candidate. Same Runner, tool ledger, schema and validation; explicit provider selection only. Free-tier evidence must precede any inference. See DEC-232–235 for exact choices.
- **Alternatives:** A custom BaseLlm HTTP implementation avoids a new bridge dependency but creates conversion code and compatibility ownership. Groq's SDK is provider-supported but still needs ADK conversion. A second agent framework or proxy adds an unnecessary execution boundary.
- **Why appropriate:** Uses Google's supported connector and minimizes application protocol code while preserving backend evidence validation and budgets. No live performance superiority is claimed.
- **Costs / risks:** LiteLLM expands the dependency graph and has a documented historical supply-chain incident; exact pins, wheel inspection and vulnerability audit are required, not a blanket security guarantee. Manual tier evidence can become stale and is not a provider-enforced spending cap. The Groq schema/tool capability override follows vendor limitations and must be tested on upgrades.
- **Evidence:** [ADK connector](https://adk.dev/agents/models/litellm/), [LiteLLM Groq](https://docs.litellm.ai/docs/providers/groq), [Groq structured-output limitation](https://console.groq.com/docs/structured-outputs), installed ADK 2.11.0 source. Actual checks/results belong in the comparison report; no live inference has occurred.
- **Revisit:** Security finding, protocol incompatibility, provider billing/tier change, model retirement, or sufficiently broad held-out evaluation favoring another candidate.
- **Interview explanation:** “We kept a single ADK investigator and changed only its model adapter. Both providers must return evidence IDs supplied by the same backend-owned tool and satisfy the same output checks. We separate an offline protocol test from a real model pass and refuse to infer free eligibility from the existence of a key. That gives a defensible comparison without implying production readiness.”
- **Follow-ups:** Does an offline bridge test prove live compatibility? No. Does a clean audit prove the dependency safe? No, only that checked versions have no reported findings in that audit. Why no automatic fallback? It hides provider failures and is outside the requested scope.
- **Related:** ADR-001/002/003/012/015/017/018; DEC-231–235.

- **Verification addendum:** 59 offline tests passed; Ruff/mypy passed; dependency audits clean. Live execution verified on operator-confirmed Free tier: direct generation (0.86s, 93 tokens), ADK supported scenario (4.17s, 1680 tokens, complete), ADK conflicting scenario (2.96s, 2083 tokens, inconclusive). Full evidence: [comparison report](../PHASE_REPORTS/PHASE_00_MODEL_COMPARISON.md). Billed spend: $0.
