# AegisOps — Current Project State

**Updated:** 2026-10-11  
**Current phase:** Phase 2 (CI isolation repair — local verification complete, hosted verification blocked)
**Overall state:** `PHASE 2 CI REPAIR VERIFIED LOCALLY; HOSTED GATE BLOCKED BY GIT AUTHENTICATION; PHASE 3 LOCKED`
**Source:** `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md` Phase 2; `docs/PHASE_REPORTS/PHASE_2_VERIFICATION.md`; `docs/ADR/ADR-022-adk-investigation-worker.md`; DEC-251–DEC-266.

---

## Implemented and verified in Phase 2 (Including Corrective Fix)

- [x] **Causal Grounding & S01 Diagnosis Accuracy (DEC-261):**
  - Eliminated false "Database Connection Pool Exhaustion" diagnosis for S01 (`S01_CHECKOUT_500`).
  - S01 correctly diagnoses controlled application exception / payment processing gateway timeout on `/checkout` (`CHECKOUT_GATEWAY_TIMEOUT`).
  - Shop API error telemetry enriched with structured `error_category`, `error_code`, and `exception_class`.
  - Hypotheses grounded in actual evidence ledger snippets; generic HTTP 500 metrics prevented from proving database exhaustion without DB logs.
- [x] **Separation of Citation Integrity and Causal Claim Support (DEC-262):**
  - Deterministic citation integrity (`validate_citation_integrity`): verifies existence, run ownership, and tenant bounds.
  - Causal claim support (`validate_claim_support`): verifies observations genuinely justify claims, prevents generic metric leaps, and flags explicit contradictions.
- [x] **Strict Qualitative Confidence Contract (DEC-263):**
  - Standardized public confidence contract strictly to `low | medium | high` (no uncalibrated floats or percentages).
  - Added `unverified_assumptions` list to hypotheses to communicate epistemic uncertainty.
  - Alembic migration `0004_qualitative_confidence.py` applied; API validators safely coerce legacy database records without data corruption.
  - Next.js UI updated with qualitative badges ("High", "Medium", "Low") and unverified assumption callouts.
- [x] **Explicit Execution Mode Architecture & No Silent Fallback (DEC-264):**
  - Explicit configuration `AEGISOPS_AGENT_MODE=offline|live` with `execution_mode` and `provider` persisted in database.
  - Deterministic offline ADK runner explicitly labeled as `provider="offline"` for predictable, zero-cost CI testing.
  - Live Gemini mode connects directly to Google GenAI; missing credentials or quota exhaustion (429) raise explicit errors and fail cleanly without silent fallback to offline mock.
- [x] **Targeted Investigation Quality Test Suite (`agents/incident_investigator/tests/test_investigation_quality.py`):**
  - Covers scenarios T01 through T10 (controlled exception, DB pool exhaustion fixture, honest inconclusive, misleading logs resistance, fabricated citations, cross-run citations, offline authenticity, live smoke test, missing credentials, confidence contract).
- [x] **Asynchronous Investigation Worker (`apps/worker/`):**
  - Celery application connected to Redis broker (`redis://redis:6379/0`).
  - Durable background task `run_investigation_task` orchestrating the investigation lifecycle.
  - Active-run idempotency guard preventing duplicate concurrent investigations on the same incident.
  - Worker container deployed and running healthily in `docker-compose.yml`.
- [x] **Google ADK Single-Agent Runner (`agents/incident_investigator/`):**
  - Google ADK 2.11.0 `Agent`, `Runner.run_async`, and `ToolContext` integration.
  - Bounded tool execution (12-call budget, 32KB payload truncation, read-only Prometheus/Loki access).
  - Pre-export sensitive secret regex redaction in `tools/redaction.py`.
- [x] **FastAPI Investigation Endpoints & Evidence Explorer (`apps/api/`):**
  - Complete REST API for dispatching, inspecting, and cancelling investigations with paginated evidence explorer.
- [x] **Next.js AI Investigation Dashboard (`apps/web/`):**
  - Interactive `InvestigationPanel` with qualitative badges, execution mode indicator ("OFFLINE" vs "LIVE"), and tool audit trail.
- [x] **Decoupled 4-Gate End-to-End Verification (`scripts/verify_phase2_e2e.py`):**
  - 28/28 checks passing: Infrastructure Correctness (16/16), Diagnostic Correctness (5/5), Model Execution Authenticity (3/3), Security & Invariants (4/4).

---

## Implemented and verified in Phase 1 (Baseline Preserved)

- [x] Instrumented Node.js Express service (`examples/shop-api`) with RED metrics and structured JSON logging.
- [x] Controlled demo fault injection `S01_CHECKOUT_500` via authenticated endpoint.
- [x] Observability stack: Prometheus v3.2.1, Alertmanager v0.28.1, Loki 3.4.2, OTel Collector Contrib 0.120.0.
- [x] Prometheus alert rule `HighApiErrorRate` with volume guard, tested via `promtool`.
- [x] Webhook receiver `POST /api/v1/webhooks/alertmanager` with timing-safe authentication and episode deduplication via PostgreSQL partial unique index `uq_open_incident_fingerprint`.
- [x] Incident feed and detail pages in Next.js dashboard.
- [x] Full Phase 1 E2E regression verification passing (`scripts/verify_phase1_e2e.py`).

---

## Implemented and verified in Phase 0 (Baseline Preserved)

- [x] Repository toolchain and dependency locks (Python 3.14.7, uv, Node.js 22.23.1, npm 10.9.8).
- [x] Core domain contracts and deterministic citation validation engine (`validate_evidence`).
- [x] FastAPI control plane baseline (`/healthz`, `/readyz`).
- [x] PostgreSQL 18 with `pgvector` 0.8.7 and Redis 8.10.2 container foundation.
- [x] Frontend dashboard shell with dark console styling and accessible navigation.
- [x] Google ADK 2.11.0 spike with read-only tools and citation-grounded outputs.
- [x] Live Gemini 3.5 Flash and Groq `gpt-oss-120b` verification on confirmed Free tier.

---

## Untested / Blocked / Deferred (Strict Phase Boundaries)

**Developer authorization gate:** Phase 2 deterministic repair checks pass locally, but the latest hosted foundation job failed. Phase 3 remains **LOCKED** pending hosted verification and explicit developer authorization. The earlier live Gemini quota blocker is separate.

- [ ] **Distributed Tracing Investigation with Grafana Tempo:** `DEFERRED TO PHASE 3`.
- [ ] **GitHub Deployment / Commit Correlation:** `DEFERRED TO PHASE 3`.
- [ ] **Full Product Auth / RBAC and Multi-Tenant Sessions:** `DEFERRED TO PHASE 3`.
- [ ] **Runbook RAG with pgvector and Lexical Search:** `DEFERRED TO PHASE 4`.
- [ ] **Cross-Incident Fingerprint Clustering & Correlation:** `DEFERRED TO PHASE 4`.
- [ ] **Multi-Agent Specialist Swarm:** `DEFERRED TO PHASE 5`.
- [ ] **Automated Remediation / n8n Internal Workflows:** `DEFERRED TO PHASES 6–7`.

---

## Historical Verification Test Summary (before CI repair)

| Test Suite | Command | Exit Code | Result |
|---|---|---|---|
| Python Static Checks | `ruff check apps agents scripts && ruff format --check apps agents scripts && mypy apps/api/app apps/worker agents/incident_investigator` | 0 | PASSED (0 lint errors, all files formatted, 14 source files type-checked clean) |
| Python Unit Tests | `pytest -q -m 'not integration'` | 0 | PASSED (74 passed, 2 deselected in 6.27s) |
| Python Security Audit | `pip-audit --progress-spinner off` | 0 | PASSED (0 known vulnerabilities) |
| Web Lint & Format | `npm --prefix apps/web run lint && npm --prefix apps/web run type-check` | 0 | PASSED (ESLint clean, TypeScript clean) |
| Web Browser E2E Tests | `npm --prefix apps/web test` | 0 | PASSED (3/3 Playwright browser tests passed in 2.7s) |
| Phase 1 Regression E2E | `.venv/bin/python scripts/verify_phase1_e2e.py` | 0 | PASSED (All 19 acceptance steps verified live) |
| Phase 2 End-to-End System | `.venv/bin/python scripts/verify_phase2_e2e.py` | 0 | PASSED (All 21 acceptance steps verified live) |


## CI repair verification — 2026-10-11 (DEC-266)

- Latest inspected hosted run: [38118992591](https://github.com/Tarun-sde/AegisOps/actions/runs/38118992591), `main`, commit `3c6db7d97b97b7ffa06a175d69488e548ad7f041`: **completed / failure**. Foundation failed at offline tests; security, browser/build and isolated Compose steps were skipped.
- Root cause: two supported investigation tests supplied no deterministic diagnostic telemetry; the gateway test required real Prometheus. Offline model mode alone does not isolate telemetry. Quality tests also loaded `.env` at collection and included a live Gemini test in offline selection.
- Repair: shared synthetic HTTP fixtures exercise the actual gateway, ADK and SQLite persistence; missing/refused telemetry stays INCONCLUSIVE. Per-test credential isolation and network guards prevent accidental live calls. Live smoke now requires integration selection and `AEGISOPS_LIVE_TEST=1`. No production diagnosis logic or dependency pins changed.
- Clean Python 3.14.7 frozen environment: **89 passed, 3 deselected, 4 warnings**. Reverse order: same counts. Existing API image with current tests mounted read-only and `--network none`: same counts. The three deselections are two existing infrastructure tests and the live smoke test; no test was deleted.
- Original failures independently: lifecycle **3 passed** (supported/empty/refused); gateway **1 passed**; supported agent **1 passed**. Ruff (39 files), mypy (15 files), web lint/format/types, both ADK spikes, Node test (**1 passed**), browser tests (**3 passed**, reused existing web service), production builds and both dependency audits pass.
- `make` is unavailable on this host; its test/spike/check recipes were executed directly. Isolated Compose migration/readiness checks pass (**2 passed, 1 skipped, 89 deselected**); live smoke is the intentional skip. Fresh Docker image build verification remains in progress.
- **External blocker:** `gh` absent; HTTPS push has no credential helper/usable credentials, and the SSH agent has no identities. Public GitHub API permits run/step inspection but full log download returns HTTP 403. Hosted repair success cannot be claimed until the commit is pushed and its exact run completes successfully.
- Full evidence, limitations and resume procedure: [Phase 2 report, CI repair addendum](PHASE_REPORTS/PHASE_2_VERIFICATION.md#9-ci-isolation-repair--2026-10-11).
