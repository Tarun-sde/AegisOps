# Phase 0 model comparison — preflight

Date: 2026-10-10. Status: **BLOCKED before live inference**.

## Verified observations

- `GOOGLE_API_KEY` and `GROQ_API_KEY` are both nonempty in local `.env`, checked with `dotenv_values` without printing values. `git check-ignore .env` confirms exclusion. Presence does not prove valid credentials, model access, or billing eligibility.
- Installed: Google ADK 2.11.0, google-genai 2.29.0, httpx 0.28.1, python-dotenv 1.2.4. Neither LiteLLM nor the OpenAI SDK is installed. No dependencies were added.
- `git ls-remote origin HEAD refs/heads/main` returned `b0014ab9ad39e4657f20c4f771d71c259067653e` for both refs. The Phase 0 commit is pushed.
- GitHub Actions API queried for that exact SHA returned one completed, successful [Phase 0 foundation run, 38043157853](https://github.com/Tarun-sde/AegisOps/actions/runs/38043157853), created 2026-10-10T09:56:24Z. This verifies hosted CI for the existing commit, not subsequent work.
- No connected browser sessions were available for inspecting authenticated provider account pages.

## Checks run in this preflight

- `.venv/bin/python -m pytest -q -m 'not integration'` stalled after one test in the sandbox and was interrupted (exit 130).
- `timeout 60s .venv/bin/python -m pytest -q -m 'not integration'` outside the sandbox: **36 passed, 2 deselected, 4 warnings in 1.33s**, exit 0. This includes both deterministic ADK fixtures and negative budget/evidence tests. Warnings concern Authlib/Starlette httpx deprecations, a Python typing deprecation, and ADK's experimental JSON-schema function declaration. This reproduces the environment distinction recorded in BUG-20261010-003; the low-level sandbox cause remains unconfirmed.
- `git diff --check`: passed. Runtime code, dependencies, and offline tests were not changed. Integration/browser/build/security audits were not rerun for these documentation-only changes.

## Live evidence ledger

| Provider | Requested model | Supported scenario | Conflicting scenario | Inference requests / tool calls | Latency / tokens / estimated inference cost |
|---|---|---|---|---|---|
| Google | `gemini-3.8-flash` | NOT RUN | NOT RUN | 0 / 0 | Not measured / not measured / $0 (no requests) |
| Groq | `openai/gpt-oss-120b` | NOT RUN | NOT RUN | 0 / 0 | Not measured / not measured / $0 (no requests) |

No provider error, real function-call response, structured model output, citation result, or inconclusive behavior was observed. Actual billed cost was not inspected. Billing was not enabled or changed.

## Blocking facts

1. **Actual account eligibility remains unverified.** Google's [pricing](https://ai.google.dev/gemini-api/docs/pricing) lists free input/output for the requested Gemini model. Its [billing documentation](https://ai.google.dev/gemini-api/docs/billing) directs users to the project's Billing Tier in AI Studio. Groq's [rate-limit documentation](https://console.groq.com/docs/rate-limits) lists GPT-OSS 120B under free-plan limits and directs users to their organization's settings for actual limits. Public documentation does not identify the tier behind either local key. The user was asked to confirm both exact key-owning project/account tiers before inference.
2. **Documents disagree on the Phase 0 gate.** `PROJECT_STATE.md` and `PHASE_00_FOUNDATION.md` say complete/Phase 1 unlocked pending authorization. ADR-018's final follow-up requires live-model and hosted-CI passes to unlock Phase 1. Master-plan §17 specifies a reproducible mocked-tool gate. Per `AGENTS.md`, implementation was paused and this conflict reported rather than silently editing the gate. Hosted CI is now confirmed; live inference remains unverified.
3. **The existing live guard requires positive authorized spend.** `run_spike` rejects $0. It must not be bypassed by supplying a fictional positive budget. A free-only path needs documented account evidence before execution.

## Integration assessment and recommendation

There is **no observed model-quality or speed winner**. Keep Gemini as the existing configurable candidate pending a live comparison; this is continuity, not an empirical recommendation. Groq remains a requested comparison candidate. The supported/conflicting fixtures and ADK Runner should be reused so evidence validation and scenario scoring remain comparable.

ADK documents a [LiteLLM integration](https://adk.dev/agents/models/litellm/); installed ADK exposes the `BaseLlm` extension contract as another possible boundary. Groq documents its [OpenAI-compatible API](https://console.groq.com/docs/openai). No integration was selected or security-verified in this preflight. LiteLLM's published [March 2026 security incident](https://github.com/BerriAI/litellm-docs/blob/main/blog/security_update_march_2026/index.md) makes exact-version provenance and current vulnerability checks necessary before any installation; it does not establish that all later versions are compromised. A custom adapter would avoid that dependency but would add protocol-conversion code to maintain and test. No adapter or automatic fallback was added.

Only synthetic evidence is authorized for this experiment. Public free-tier availability is neither an account billing guarantee nor approval to send customer telemetry. Phase 1 monitoring/ingestion remains untouched.

Governing decisions: ADR-001/002/003/012/015/018, DEC-217–219, DEC-221, DEC-224, DEC-229, and the preflight record DEC-230. No new architecture ADR is selected while the conflict is pending.

---

## Current continuation result — developer Decisions 1 and 2 (DEC-231–236)

**Foundation COMPLETE; offline comparison harness VERIFIED; live comparison BLOCKED; Phase 1 LOCKED.** The preflight sections above are historical. The developer resolved the gate conflict: live-model verification is separate and mandatory before Phase 1 formally unlocks. Current source of truth is this section, PROJECT_STATE and ADR-018's clarification. Previous decision history remains intact.

### Actual provider account-tier verification

| Check | Google/Gemini | Groq |
|---|---|---|
| Key nonempty in ignored .env | Yes, no value displayed | Yes, no value displayed |
| Authenticated console accessible | No connected browser | No connected browser |
| Other account verification access | gcloud absent; Google ADC file absent | No authenticated organization console/session available |
| Exact key-owning account and Free tier confirmed | **NO — UNVERIFIED** | **NO — UNVERIFIED** |
| Supported / conflicting live inference | **NOT RUN / NOT RUN** | **NOT RUN / NOT RUN** |
| Real model requests / real tool calls | 0 / 0 | 0 / 0 |
| Model latency / tokens / provider errors | Not measured / not measured / none observed | Not measured / not measured / none observed |
| Estimated cost for this task's inference | $0 (no requests) | $0 (no requests) |

No billing activation, payment-method change, paid request, model-list-as-billing inference, or fabricated tier attestation was performed. Running `--live` without `--tier-evidence` for all four provider/scenario combinations exited **1 before network**, with ValueError, zero model/tool calls, null latency/usage and a zero no-request cost. Those are **blocked preflight artifacts**, not failed live model calls. Local artifacts: `artifacts/preflight-{gemini,groq}-{supported,conflicting}.json` (ignored).

### Implemented and verified offline

- Existing `spike.py`, prompt and synthetic tool are reused; deterministic `test_spike.py` is unchanged. Gemini is provisional primary; Groq is explicitly selected with `--provider groq`. No automatic switching or additional agent.
- `groq_adapter.py` uses ADK's supported LiteLlm bridge with **LiteLLM 1.104.2**, **OpenAI 2.54.0** transitively locked, fixed Groq HTTPS endpoint, explicit key, no retries, low reasoning effort and no provider built-in tools. The subclass advertises no combined native schema/tools support, matching [Groq documentation](https://console.groq.com/docs/structured-outputs). ADK's own `set_model_response` tool supplies schema output for independent Pydantic/citation checks.
- Budgets remain four model calls, twelve synthetic retrieval calls, 2048 output tokens per model call, 30s HTTP timeout and 180s run timeout. Gemini counts input tokens up to 16000; Groq caps serialized ADK request bytes at 16000 (a context-size guard, **not** a measured provider token count). No retry is attempted on 401, 429 or 500.
- Both fixtures require the expected status. Conflicting evidence requires support and contradiction citations, all resolved against the backend-fixed returned ledger. Unknown evidence and scope/action violations remain rejected.
- Reports retain per-response latency/usage/model version when returned, total elapsed time, configured provider/model, request/tool counts, prompt/fixture hashes and partial events after errors. Error bodies are excluded; only exception class and numeric HTTP status are stored. Unknown cost/usage remains null. A successful verified-free run would estimate $0; actual billing remains uninspected. Cleanup errors cannot erase already-observed calls.
- `free_tier.py` validates operator-reviewed records against the exact key SHA-256, provider/source, Free tier and a verification timestamp no older than one hour (future timestamps rejected). Nonzero paid ceilings are rejected even with a valid free-tier record. This enforces a **manual evidence prerequisite**, not automatic account lookup or an immutable provider billing guarantee. No real-key record exists yet.

### Exact checks and outcomes

| Command / check | Outcome |
|---|---|
| `UV_CACHE_DIR=.cache/uv .tools/bin/uv lock` | Resolved 121 packages; added 31 packages, filelock 4.1.0 → 3.32.7 required by LiteLLM <4; other existing versions retained |
| Official PyPI Linux wheel download/hash/startup-hook inspection | SHA-256 `416c3538ea78b08d637ec45564a919232aa2093e73adb9dd7752f7cff2ec585e` matched; no .pth/sitecustomize/usercustomize files; PyPI listed no vulnerabilities |
| `pip-audit -r /tmp/aegisops-audit-requirements.txt --no-deps --disable-pip --progress-spinner off` | No known vulnerabilities before install; requirements exported from complete frozen lock |
| `UV_CACHE_DIR=.cache/uv .tools/bin/uv sync --frozen --all-groups --no-build` | Passed; registry wheels only |
| `.venv/bin/pip-audit --progress-spinner off` | Exit 0, no known vulnerabilities in installed set |
| `timeout 60s .venv/bin/python -m pytest -q -m 'not integration' --tb=short` (outside sandbox) | **59 passed, 2 deselected, 132 warnings in 5.65s**, exit 0 |
| `.venv/bin/ruff check apps agents` | Exit 0, all checks passed |
| `.venv/bin/ruff format --check apps agents` | Exit 0, 19 files already formatted |
| `.venv/bin/mypy apps/api/app agents/incident_investigator/spike.py agents/incident_investigator/free_tier.py agents/incident_investigator/groq_adapter.py` | Exit 0, no issues in 7 source files |
| `.venv/bin/python -m agents.incident_investigator.spike --scenario supported --output artifacts/spike-supported.json` and corresponding `conflicting` command | Both exit 0/PASSED; two deterministic model turns, one retrieval each; complete/inconclusive respectively |
| Four `--live --provider {gemini,groq} --scenario {supported,conflicting}` invocations **without tier evidence** | All exit 1/BLOCKED before inference; zero calls |
| `git diff --check` | Passed after removing Markdown trailing whitespace |

Warnings include existing Authlib/Starlette httpx deprecations, Python typing deprecation, ADK experimental schema function declarations, and GOOGLE_GENAI_USE_VERTEXAI deprecation in the bridge environment. No silent dependency upgrades were made to suppress them. Initial bridge tests were **52 passed / 2 failed** because the mock response omitted documented `service_tier`; corrected fixture yielded **54 passed** before adding five more boundary tests. See BUG-20261010-005. Security checks are scoped evidence, not a guarantee against unknown vulnerabilities.

### Resume procedure once account access is available

1. In the authenticated Google AI Studio **Projects/Billing** view, match the configured key to its project and verify Free tier. For Groq, match the key to its organization and inspect its plan/billing page. Do not change billing. Stop for paid/unknown status.
2. Only after actually checking those pages, the trusted local operator may save a reviewed record under ignored `artifacts/`, using the schema in `free_tier.py`: provider (`gemini`/`groq`), tier (`free`), `key_sha256` (SHA-256 of the exact key, no raw key), `account_reference`, `source` (`google_ai_studio_project_billing`/`groq_organization_billing`), UTC `verified_at`, `verified_by` (`operator`). Never create this record from public pricing or key presence. Do not commit account identifiers or screenshots. Recheck immediately if account/key/billing changes; the one-hour expiry is only a freshness guard.
3. Run one scenario at a time, Gemini first; stop on any billing/quota/access concern. Example after verification:

```bash
.venv/bin/python -m agents.incident_investigator.spike --live --provider gemini --scenario supported --tier-evidence artifacts/tier-gemini.json --output artifacts/live-gemini-supported.json
.venv/bin/python -m agents.incident_investigator.spike --live --provider gemini --scenario conflicting --tier-evidence artifacts/tier-gemini.json --output artifacts/live-gemini-conflicting.json
.venv/bin/python -m agents.incident_investigator.spike --live --provider groq --scenario supported --tier-evidence artifacts/tier-groq.json --output artifacts/live-groq-supported.json
.venv/bin/python -m agents.incident_investigator.spike --live --provider groq --scenario conflicting --tier-evidence artifacts/tier-groq.json --output artifacts/live-groq-conflicting.json
```

The full four-case experiment is capped at sixteen model calls, with no retries or provider fallback. Rate limits can still block it; do not upgrade billing. CLI selectively reads the named provider/config settings from `.env` without interpolation; explicitly set process environment takes precedence. Model IDs remain configurable, but unreviewed IDs are rejected pending availability/pricing validation.

### Comparison recommendation and honest interview evidence

**Neither model has passed live ADK tool calling. There is no observed winner.** Keep Gemini primary and Groq secondary as instructed. Gemini uses the native ADK adapter and provider token-count API; Groq uses a pinned supported translation dependency and an explicit schema/tool capability correction. Both use the same synthetic evidence, output contract and deterministic checks. Differences in reasoning settings and input-size guards must be disclosed in any later latency comparison. Two small scenarios cannot establish production diagnosis accuracy or a reliable latency distribution.

Verified interview lesson: distinguish framework dispatch, HTTP protocol compatibility under mocks, actual model quality and account billing eligibility. We verified the first two offline and left the latter two honestly open. Phase 1 monitoring and ingestion, production data, multi-agent work and fallback remain excluded. The gate interpretation change is explicitly developer-approved (DEC-231); ADR-020 records only the requested isolated secondary provider integration.

### GitHub verification

Original foundation commit `b0014ab9ad39e4657f20c4f771d71c259067653e` is pushed; [run 38043157853](https://github.com/Tarun-sde/AegisOps/actions/runs/38043157853) completed successfully. This run does not verify the new comparison changes. The continuation will be committed after secret checks; its hosted CI result must be checked for the exact pushed SHA and reported separately.
