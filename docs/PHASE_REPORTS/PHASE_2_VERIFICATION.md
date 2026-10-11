# Phase 2 Corrective Verification Report — End-to-End AI Investigation MVP (Root-Cause Accuracy, Model Authenticity & Confidence Contract)

**Date:** 2026-10-11  
**Phase:** 2 — End-to-End AI Investigation MVP (Corrective Fix)  
**Correction Status:** `CI ISOLATION REPAIR VERIFIED LOCALLY; HOSTED CI BLOCKED BY GIT AUTHENTICATION; PRIOR LIVE GEMINI QUOTA BLOCKER REMAINS SEPARATE`
> Sections 1–8 retain historical corrective verification evidence. Section 9 records the current CI repair; earlier completion statements do not establish current hosted success.

**Governing Documents:** `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md` Phase 2; `AGENTS.md`; `docs/ADR/ADR-022-adk-investigation-worker.md`; `docs/ENGINEERING_DECISIONS.md` (DEC-251–DEC-265).

---

## 1. Executive Summary & Defect Correction

During the initial Phase 2 review, two critical deficiencies were discovered in the verified implementation:
1. **Incorrect Root-Cause Diagnosis:** For scenario `S01_CHECKOUT_500` (which injects a controlled application exception on `/checkout`), the agent previously reported:
   ```text
   Diagnosed: S01_CHECKOUT_500: Database Connection Pool Exhaustion in /checkout (confidence: 0.95)
   ```
   Database connection pool exhaustion belongs to a different scenario (S03). Although the evidence citations (`ev_metric_...`, `ev_log_...`) existed in the database, the cited evidence **did not substantiate the proposed causal claim**. A valid database foreign key citation proves telemetry existence, but not causal truth.
2. **Uncalibrated Numerical Confidence:** The initial verification reported numerical values such as `0.95` and `0.20`, implying mathematical calibration that had not been empirically established. The master plan specifies qualitative confidence (`low | medium | high`).
3. **Model Execution Authenticity:** The initial report conflated deterministic offline ADK runner execution with live Gemini inference. The system lacked an explicit execution mode architecture and failed to guarantee that live failures would not silently fall back to offline mock output.

This corrective task addressed all three deficiencies without changing unrelated functionality or advancing to Phase 3.

---

## 2. Root-Cause Bug Analysis & Telemetry Grounding

### 2.1 Why the S01 Diagnosis Was Wrong
- **Fault Ground Truth:** S01 injects a controlled application exception in `examples/shop-api/src/app.ts` (`POST /checkout` returns HTTP 500). The intended cause is an application-level payment processing gateway timeout.
- **Source of Error:** The initial `OfflineInvestigationModel` and verification assertion conflated S01 with S03 (database connection pool exhaustion). It emitted a predefined database pool exhaustion hypothesis whenever HTTP 500 occurred, regardless of whether database logs were present.
- **Why Valid Citations Failed to Prevent It:** The original `validate_evidence` checked only **Citation Integrity** (verifying that `evidence_id` exists, belongs to the run, and is within the service scope). Because the agent cited real Prometheus 500 metrics and real Loki logs, the validator accepted the hypothesis even though the causal explanation was factually wrong.

### 2.2 How the Defect Was Corrected
1. **Enriched Structured Telemetry:** `examples/shop-api/src/app.ts` was enriched to emit structured JSON error logs:
   ```json
   {
     "level": "error",
     "service": "shop-api",
     "event": "http_request_error",
     "message": "HTTP 500: checkout payment gateway failure on POST /checkout",
     "error_category": "APPLICATION_EXCEPTION",
     "error_code": "CHECKOUT_GATEWAY_TIMEOUT",
     "exception_class": "PaymentGatewayTimeoutException"
   }
   ```
2. **Grounded Hypothesis Selection:** The offline investigation model was rewritten to inspect actual snippets in the evidence ledger. When `CHECKOUT_GATEWAY_TIMEOUT` or payment gateway errors are present, the agent diagnoses:
   ```text
   Controlled application exception: checkout payment processing gateway timeout on /checkout
   ```
   It is strictly prohibited from claiming database connection pool exhaustion unless actual database pool contention telemetry is cited.
3. **Anti-Cheating Integrity:** Ground-truth scenario labels remain strictly within test fixtures and harnesses. The agent infers root cause entirely from authorized operational telemetry retrieved through its read-only tool gateway.

---

## 3. Evidence Support Validation: Citation Integrity vs Claim Support

We established a strict two-stage validation separation in `agents/incident_investigator/validator.py` and `apps/api/app/schemas.py`:

```mermaid
flowchart TD
    Result[Agent Investigation Result] --> CitCheck[Stage 1: Citation Integrity validate_citation_integrity]
    CitCheck -->|Fabricated or Cross-Run ID| RejectCit[REJECT: Unknown evidence reference]
    CitCheck -->|All IDs Valid & Scoped| ClaimCheck[Stage 2: Claim Support validate_claim_support]
    ClaimCheck -->|Generic 500 Metrics alone claiming DB Pool| RejectClaim1[REJECT: Metrics cannot prove DB pool without DB logs]
    ClaimCheck -->|Claims DB Exhaustion while Logs show Gateway Timeout| RejectClaim2[REJECT: Contradiction with cited telemetry]
    ClaimCheck -->|High confidence with metric counters only| RejectClaim3[REJECT: High confidence requires logs or traces]
    ClaimCheck -->|Valid Claim Support| Accept[ACCEPTED: Validated Investigation Result]
```

### 3.1 Stage 1: Deterministic Citation Integrity
- Every cited `evidence_id` must exist in `evidence_ledger`.
- Evidence must match the authorized `organization_id`, `service_id`, and `run_id`.
- Rejects fabricated IDs (`ev_fake_...`) and foreign run references with deterministic `ValueError`.

### 3.2 Stage 2: Causal Claim Support Heuristics
- **Metric vs Root Cause Differentiation:** Generic HTTP 500 error counters cannot substantiate database pool exhaustion without database diagnostic telemetry.
- **Contradiction Detection:** If cited logs explicitly show payment processing gateway failure, hypotheses claiming database pool exhaustion without noting contradictions are rejected.
- **Confidence Bounding:** Purely symptom-level metric counters cannot support `high` confidence without diagnostic logs.

### 3.3 Limitations of Deterministic Validation
Deterministic code can enforce citation provenance, detect explicit contradictions, and block obvious non-sequiturs. However, general natural-language causality cannot be fully verified by keyword heuristics alone. Semantic diagnostic accuracy is therefore independently evaluated using labeled scenario holdouts in the test harness.

---

## 4. Qualitative Confidence Contract & Legacy Handling

### 4.1 Contract Standard
- Public confidence is standardized strictly to `low | medium | high` (`Literal["low", "medium", "high"]`).
- Arbitrary floating-point values (e.g. `0.95`, `0.20`) and percentage strings (e.g. `95%`) are rejected at schema validation boundaries.
- Hypotheses now include `unverified_assumptions: list[str]` to explicitly capture epistemic assumptions and missing telemetry.

### 4.2 Safe Legacy Data Migration
- Alembic migration `0004_qualitative_confidence.py` added `execution_mode`, `provider`, and `unverified_assumptions` columns.
- Existing historical investigations with numerical confidence values are safely coerced in Pydantic schema deserialization (`coerce_legacy_confidence`):
  - `>= 0.8` -> `"high"`
  - `>= 0.5` -> `"medium"`
  - `< 0.5` -> `"low"`
- No historical investigation records were corrupted, deleted, or invalidated.

---

## 5. Model Execution Authenticity: Offline vs Live Mode

The system supports explicit configuration via `AEGISOPS_AGENT_MODE=offline|live`:

| Aspect | Offline Mode (`offline`) | Live Mode (`live`) |
|---|---|---|
| **Purpose** | CI testing, local development, deterministic ADK integration | Real Gemini LLM operational incident investigation |
| **Model ID** | `offline-adk-v2` | Pinned Gemini model (e.g. `gemini-3.5-flash`) |
| **Provider Label** | `provider="offline"` | `provider="gemini"` |
| **Cost** | $0.00 (Zero external API calls) | Free-tier / billed API usage |
| **Tools Used** | Real `ReadOnlyToolGateway` against Prometheus & Loki | Real `ReadOnlyToolGateway` against Prometheus & Loki |
| **ADK Runtime** | Google ADK 2.11.0 `Runner.run_async` | Google ADK 2.11.0 `Runner.run_async` + `google.genai.Client` |

### 5.1 Strict Prevention of Silent Fallback
If `AEGISOPS_AGENT_MODE=live` is selected:
- If `GOOGLE_API_KEY` is missing: Raises explicit `ValueError` immediately.
- If Google GenAI returns 401, 403, 404, or 429: The investigation transitions to `FAILED` with the exact error details.
- **Under no circumstances does the system silently fall back to `OfflineInvestigationModel` and present its output as a Gemini diagnosis.**

---

## 6. Live Gemini Smoke Test Verification

We performed an authenticated live inference test (`test_t08_live_gemini_smoke_test`) using Google ADK and `google.genai.Client`:

- **Execution Mode:** `live`
- **Target Model:** `gemini-3.5-flash`
- **Authentication:** Valid `GOOGLE_API_KEY` present in local `.env`.
- **Observed Result:** Authenticated request reached `https://generativelanguage.googleapis.com`. The Google GenAI API returned:
  ```text
  429 RESOURCE_EXHAUSTED: You exceeded your current quota, please check your plan and billing details.
  Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20
  Please retry in 3h56m40s.
  ```
- **Fallback Verification:** The system did NOT fall back to offline mode. It cleanly captured the 429 status and recorded the provider failure.
- **Reporting Status:** `LIVE GEMINI VERIFICATION BLOCKED (Free-Tier Daily Quota Exhausted: 429 RESOURCE_EXHAUSTED)`.
- **Integrity Compliance:** In strict accordance with Section 8 of the prompt, live Gemini verification is marked as `BLOCKED` rather than fabricating a successful result.

---

## 7. Real Verification Evidence

### 7.1 Decoupled 4-Gate End-to-End Verification (`scripts/verify_phase2_e2e.py`)
Executed live against running Docker Compose services:

```text
====================================================================================
AEGISOPS PHASE 2 CORRECTIVE — VERIFICATION OF ACCURACY, AUTHENTICITY & CONTRACT
====================================================================================

--- PREREQUISITE INFRASTRUCTURE HEALTH ---
[  PASS  ] [     PREREQ     ] Health: FastAPI Control Plane          HTTP 200
[  PASS  ] [     PREREQ     ] Health: Shop API                       HTTP 200
[  PASS  ] [     PREREQ     ] Health: Prometheus                     HTTP 200
[  PASS  ] [     PREREQ     ] Health: Alertmanager                   HTTP 200
[  PASS  ] [     PREREQ     ] Health: Loki                           HTTP 200
[  PASS  ] [     PREREQ     ] Health: Next.js Dashboard              HTTP 200

--- SECTION A: INFRASTRUCTURE CORRECTNESS ---
[  PASS  ] [     INFRA      ] Fault Injection S01_CHECKOUT_500       HTTP 200 (Active)
[  PASS  ] [     INFRA      ] Traffic Generation (500s)              5 checkout requests dispatched
[  PASS  ] [     INFRA      ] Prometheus Real 5xx Metric             500 count = 92
[  PASS  ] [     INFRA      ] Loki Real Error Log Stream             2 streams found
[  PASS  ] [     INFRA      ] Incident Ingestion from Alert          Created incident with fp fp-phase2-1791662815
[  PASS  ] [     INFRA      ] Start AI Investigation                 Run ID: eda443d8-9e43-471d-ac90-0c64139c3932
[  PASS  ] [     INFRA      ] Celery Async Execution                 Terminal status: COMPLETE
[  PASS  ] [     INFRA      ] Tool Executions Recorded               3 tools called: get_incident_snapshot, query_service_metrics, search_service_logs
[  PASS  ] [     INFRA      ] Evidence Items Persisted               3 items: ev_alert_6c6442c8, ev_metric_fcb90e1e, ev_log_c17df0b2
[  PASS  ] [     INFRA      ] Citation Integrity Check               All cited evidence IDs exist in run scope

--- SECTION B: DIAGNOSTIC CORRECTNESS ---
[  PASS  ] [      DIAG      ] S01 Root Cause Accuracy                Grounded diagnosis: 'Controlled application exception: checkout payment processing...'
[  PASS  ] [      DIAG      ] Claim Telemetry Grounding              Cited 2 items matching application failure
[  PASS  ] [      DIAG      ] Qualitative Confidence Contract        Contract obeyed: confidence='high' (no uncalibrated floats)
[  PASS  ] [      DIAG      ] Unverified Assumptions Field           0 explicit assumptions tracked
[  PASS  ] [      DIAG      ] Honest Inconclusive Scenario           Missing evidence acknowledged: 'No HTTP 500 logs or diagnostic error anomalies observed in window'

--- SECTION C: MODEL EXECUTION AUTHENTICITY ---
[  PASS  ] [      AUTH      ] Offline Provider Labeling              execution_mode='offline' provider='offline' (no fake Gemini claim)
[  PASS  ] [      AUTH      ] Silent Fallback Prevention             Live mode with missing credentials raised explicit error (did not fall back)
[  PASS  ] [      AUTH      ] Live Gemini Configured                 API key detected in environment; model gemini-3.5-flash pinned

--- SECTION D: SECURITY & BOUNDARY ENFORCEMENT ---
[  PASS  ] [    SECURITY    ] Fabricated Citation Rejection          Rejected: Unknown evidence reference: 'ev_fake_12345678'
[  PASS  ] [    SECURITY    ] Cross-Run Citation Rejection           Rejected out-of-scope reference
[  PASS  ] [    SECURITY    ] Tool Budget Limit (12 Calls)           13th call rejected: Tool budget exhausted (maximum 12 calls)
[  PASS  ] [    SECURITY    ] Pre-Export Sensitive Redaction         Secrets replaced with [REDACTED]

====================================================================================
PHASE 2 CORRECTIVE VERIFICATION SUMMARY
====================================================================================
Infrastructure Correctness:   16/16 PASS (100.0%)
Diagnostic Correctness:       5/5 PASS (100.0%)
Model Execution Authenticity: 3/3 PASS (100.0%)
Security & Invariants:        4/4 PASS (100.0%)
====================================================================================
RESULT: ALL PHASE 2 CORRECTIVE GATES VERIFIED SUCCESSFULLY
```

### 7.2 Targeted Quality Test Suite (`pytest agents/incident_investigator/tests/test_investigation_quality.py`)
```text
agents/incident_investigator/tests/test_investigation_quality.py::test_t01_controlled_application_exception PASSED
agents/incident_investigator/tests/test_investigation_quality.py::test_t02_database_pool_exhaustion_fixture PASSED
agents/incident_investigator/tests/test_investigation_quality.py::test_t03_insufficient_evidence_inconclusive PASSED
agents/incident_investigator/tests/test_investigation_quality.py::test_t04_misleading_logs_resistance PASSED
agents/incident_investigator/tests/test_investigation_quality.py::test_t05_fabricated_citation_rejection PASSED
agents/incident_investigator/tests/test_investigation_quality.py::test_t06_cross_run_citation_rejection PASSED
agents/incident_investigator/tests/test_t07_offline_model_authenticity PASSED
agents/incident_investigator/tests/test_t08_live_gemini_smoke_test SKIPPED (Quota 429)
agents/incident_investigator/tests/test_t09_missing_live_credentials_rejection PASSED
agents/incident_investigator/tests/test_t10_confidence_schema_contract PASSED
agents/incident_investigator/tests/test_claim_support_rejects_generic_metrics_for_db_exhaustion PASSED

10 passed, 1 skipped in 3.43s
```

### 7.3 Phase 1 Regression Verification (`scripts/verify_phase1_e2e.py`)
```text
ALL PHASE 1 END-TO-END ACCEPTANCE GATES VERIFIED SUCCESSFULLY!
```

### 7.4 Full Non-Integration Test Suite
```text
84 passed, 1 skipped, 2 deselected in 7.26s
```

### 7.5 Browser Playwright Tests (`npm run test:web`)
```text
Running 3 tests using 1 worker
  ✓ shell navigates to workspace and incidents feed on desktop and mobile (935ms)
  ✓ health endpoint responds (29ms)
  ✓ incident detail page displays AI investigation panel (167ms)
3 passed (2.7s)
```

### 7.6 Static Analysis & Type Checking
- `ruff check apps agents scripts`: Code 0 (0 errors).
- `ruff format --check apps agents scripts`: Code 0 (All files formatted).
- `mypy apps/api/app ... scripts/verify_phase2_e2e.py`: Code 0 (Success: no issues found in 15 source files).
- `npm run lint`: Code 0.
- `npm run format:check`: Code 0.
- `npm run typecheck`: Code 0.

---

## 8. Summary of Files Changed

| Path | Purpose |
|---|---|
| `examples/shop-api/src/app.ts` | Enriched structured error logging (`APPLICATION_EXCEPTION`, `CHECKOUT_GATEWAY_TIMEOUT`). |
| `apps/api/alembic/versions/0004_qualitative_confidence.py` | Alembic migration adding `execution_mode`, `provider`, and `unverified_assumptions`. |
| `apps/api/app/models.py` | Updated SQLAlchemy ORM models `InvestigationRun` and `HypothesisRecord`. |
| `apps/api/app/schemas.py` | Standardized qualitative confidence contract (`low`, `medium`, `high`), legacy coercion validator, claim-support validator. |
| `agents/incident_investigator/validator.py` | Dedicated validator implementing two-stage separation (citation integrity vs claim support). |
| `agents/incident_investigator/agent.py` | Telemetry-grounded offline model, explicit `execution_mode`, and silent fallback prohibition. |
| `agents/incident_investigator/investigator.py` | Orchestrator updated with execution mode, provider, and unverified assumptions persistence. |
| `apps/api/app/main.py` | REST API updated to accept and return `execution_mode` and `provider`. |
| `apps/web/app/lib/api.ts` | Frontend client updated with qualitative confidence types and execution mode. |
| `apps/web/app/app/incidents/[incidentId]/investigation-panel.tsx` | UI updated with qualitative badges ("High", "Medium", "Low") and OFFLINE/LIVE mode indicator. |
| `agents/incident_investigator/tests/test_investigation_quality.py` | Targeted test suite covering scenarios T01 through T10. |
| `scripts/verify_phase2_e2e.py` | Decoupled 4-gate E2E verification script (Infrastructure, Diagnostic Correctness, Authenticity, Security). |
| `scripts/verify_phase1_e2e.py` | Alertmanager v2 query update and existing incident resolution robustness. |
| `docs/ADR/ADR-022-adk-investigation-worker.md` | Added Phase 2 Corrective Fix amendment. |
| `docs/ENGINEERING_DECISIONS.md` | Appended decisions DEC-261 through DEC-265. |
| `docs/PROJECT_STATE.md` | Updated with Phase 2 Corrective Fix status. |


## 9. CI isolation repair — 2026-10-11

### Actual hosted failure

Repository `Tarun-sde/AegisOps`, branch `main`, commit `3c6db7d97b97b7ffa06a175d69488e548ad7f041`.
[Run 38118992591](https://github.com/Tarun-sde/AegisOps/actions/runs/38118992591), workflow **AegisOps CI**, job **foundation** (`114409640721`), conclusion **failure**.

| Hosted stage | Observed result |
|---|---|
| Frozen dependencies | success |
| Static checks | success |
| Offline tests and ADK artifacts | failure |
| Dependency security | skipped |
| Browser and production build | skipped |
| Isolated Compose verification | skipped |
| Cleanup and artifact upload | success |

Public GitHub API run, jobs and annotations were inspected. Annotation: `Process completed with exit code 2.` Full log download returned HTTP 403 without authentication. The detailed CI transcript supplied by the developer reports `3 failed, 81 passed, 1 skipped, 2 deselected, 4 warnings`; it is not represented as independently downloaded logs.

### Three independently reproduced causes

1. `test_execute_investigation_lifecycle_offline`: expected COMPLETE, observed INCONCLUSIVE. SQLite supplies a valid incident/run but no deterministic metrics or diagnostic logs. Real telemetry requests fail in an isolated environment, so the offline model correctly abstains. Lifecycle propagation is correct.
2. `test_gateway_budget_and_metrics`: expected `evidence_id`, observed an error with empty series. It made an actual localhost Prometheus request. Local sandbox reproduction reported `<urlopen error [Errno 1] Operation not permitted>`; supplied hosted output reported `<urlopen error [Errno 111] Connection refused>`. Neither should produce successful evidence.
3. `test_offline_investigation_supported_scenario`: expected complete, observed inconclusive. `scenario="supported"` is not diagnostic evidence. The corrected model requires actual error signals; the test supplied none.

Each test failed independently before editing (1 failure per invocation). The implementation's honest INCONCLUSIVE behavior was retained; supported expectations were not weakened.

### Repair and isolation audit

- Root `conftest.py` mocks only `urllib.request.urlopen`, with Prometheus vector and Loki stream wire envelopes. Supported input has a 0.25 error ratio and structured HTTP 500 checkout error with `APPLICATION_EXCEPTION`, `CHECKOUT_GATEWAY_TIMEOUT` and `PaymentGatewayTimeoutException`. Empty and refused responses are separate cases. These are **synthetic test fixtures**, not real telemetry or model accuracy evidence.
- Gateway tests exercise enum rejection before HTTP, query encoding, float normalization, window metadata clamping, log parsing, evidence generation and the 12-call budget. Connection refusal yields no successful metric/log evidence IDs. Lifecycle tests use real SQLite sessions and verify provenance, hashes, citations, terminal status, tool errors and idempotency.
- Real ADK Runner, offline model, claim-support and citation validators execute unchanged. Existing fabricated/cross-scope and misleading-evidence tests remain; misleading evidence must qualify confidence. No-data tests now use the same supported scenario label, proving abstention comes from missing evidence.
- Non-integration tests clear model credentials, select offline mode, block Internet-family socket `connect`/`connect_ex`, and fail teardown for attempted connections even if application code catches the error. Local socketpairs remain available to asyncio. This is a test guard, not a production network policy or protection against arbitrary subprocesses.
- Removed collection-time `.env` loading. The live smoke test is marked `integration` and requires `AEGISOPS_LIVE_TEST=1`; it receives no HTTP mocks. Normal offline selection never contacts Gemini. No live inference was performed for this repair.
- Audited API and agent test files; API clients use in-process transport and in-memory SQLite, readiness probes and Celery dispatch are mocked, provider comparisons mock HTTP. There is no `apps/worker/tests/` directory; lifecycle tests cover the orchestration called by the worker, not live Celery delivery. Existing real Compose tests and Phase 1/2 E2E scripts remain intact.
- `Makefile` includes the root fixture in Ruff checks; API Dockerfile copies it for container test discovery. No workflow job, assertion, security check, production runtime logic, migration or pinned dependency was removed or relaxed.
- Fixture envelope references checked against pinned upstream sources: [Prometheus v3.2.1 API](https://raw.githubusercontent.com/prometheus/prometheus/v3.2.1/docs/querying/api.md) and [Loki v3.4.2 HTTP API](https://raw.githubusercontent.com/grafana/loki/v3.4.2/docs/sources/reference/loki-http-api.md).

### Local commands and actual results

Host: Python **3.14.7**, Node **22.23.1**, npm **10.9.8**; existing `.tools/bin/uv` **0.13.0**. All uv invocations use `--frozen --all-groups`. `make test`, `make spike`, `make check` each exit 127 (`make: command not found`); equivalent recipe commands were executed directly, without installing a host toolchain.

| Command/check | Actual result |
|---|---|
| `UV_CACHE_DIR=.cache/uv .tools/bin/uv sync --frozen --all-groups` | exit 0; 130 packages checked |
| Same sync with `UV_PROJECT_ENVIRONMENT=/tmp/aegisops-ci-env` | exit 0; fresh environment; initial `--offline` attempt lacked cached Celery wheel, online frozen sync succeeded |
| `uv run --frozen --all-groups pytest -q -m 'not integration'` in fresh environment | **89 passed, 3 deselected, 4 warnings in 11.47s** |
| Full fresh-environment suite with pytest collection reversed | **89 passed, 3 deselected, 4 warnings in 5.53s** |
| Same suite in existing pinned API image, current tests mounted read-only, `docker run --network none` | **89 passed, 3 deselected, 4 warnings in 12.04s** |
| Lifecycle test alone | **3 passed, 3 warnings in 2.80s** |
| Gateway budget/metrics test alone | **1 passed, 1 warning in 1.10s** |
| Supported offline agent test alone | **1 passed, 2 warnings in 1.98s** |
| Ruff check and format check over `conftest.py apps agents scripts` | exit 0; 39 files formatted |
| Exact mypy target list in `Makefile` | exit 0; 15 source files |
| `npm run lint`, `npm run format:check`, `npm run typecheck` | all exit 0 |
| Both `python -m agents.incident_investigator.spike` recipe commands | exit 0; supported complete and conflicting inconclusive; each 2 model calls / 1 tool call |
| `npm test` | exit 0; **1 passed, 0 failed** |
| `npm run test:web` | exit 0; **3 passed in 3.1s**; reused existing local web service |
| `npm run build` | exit 0; Next.js production and shop-api TypeScript builds |
| `pip-audit --progress-spinner off`, `npm audit --audit-level=high` | both exit 0; no known vulnerabilities / 0 vulnerabilities |
| Dedicated Compose verification using existing pinned image and current tests mounted read-only | **2 passed, 1 skipped, 89 deselected, 3 warnings in 7.78s**; migration round-trip and readiness pass; live smoke skipped without opt-in; verification services stopped afterward |
| `git diff --check` | exit 0 |

The initial sandbox full-suite run stalled in TestClient and was interrupted (exit 130); Node listener tests also failed in the sandbox. Both passed outside it. No production code was changed to accommodate these host restrictions. The fresh environment and disabled-network container independently verify the repaired tests; the original developer virtualenv is not the sole proof.

### Hosted blocker, security and phase readiness

GitHub CLI is absent. `GIT_TERMINAL_PROMPT=0 git push --dry-run origin main` returned `fatal: could not read Username for 'https://github.com': terminal prompts disabled`; `ssh-add -l` reports no identities. Public run inspection works, but authenticated log access and push remain unavailable. The latest inspected hosted run is still the failed run above. No replacement hosted green run is claimed.

DEC-266 and BUG-20261011-001 record this repair; ADR-022 and DEC-253/255/257/261–265 govern unchanged runtime behavior. No new ADR, architectural deviation, paid model call, secret publication or Phase 3 implementation. Production read-only tools, evidence scope validation, claim support, qualitative confidence and explicit live/offline separation remain intact.

Limits: synthetic fixtures prove deterministic wiring, not live diagnostic accuracy. Window tests verify the existing metadata clamp, not historical time-range enforcement; broader service/tenant authorization remains Phase 3 work. Browser checks reused the existing service; they are not a fresh hosted deployment test. Earlier live Gemini quota evidence was not refreshed. Local deterministic gates pass; **the hosted CI gate remains BLOCKED and Phase 3 stays LOCKED**.

After Git authentication is restored: push `main`, inspect the run matching the exact repair commit, wait for every required foundation step to complete, retrieve any new failure logs, and repair further failures before claiming GREEN. Example: `git push origin main`; with authenticated CLI, `gh run list --branch main --commit "$(git rev-parse HEAD)"`, then `gh run watch <run-id> --exit-status` and `gh run view <run-id> --json headSha,conclusion,jobs,url`.
