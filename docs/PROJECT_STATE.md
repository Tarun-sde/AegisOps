# AegisOps — Current Project State

**Updated:** 2026-10-11  
**Current phase:** Phase 4 (Richer Incident Correlation, Lifecycle Management & GitHub Read-Only Integration)
**Overall state:** `PHASE 4 IMPLEMENTED AND VERIFIED LOCALLY; 107/107 UNIT TESTS PASSING; PHASE 5 UNLOCKED`
**Source:** `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md` Phase 4; `docs/PHASE_REPORTS/PHASE_4_VERIFICATION.md`; `docs/ADR/ADR-024-incident-lifecycle-correlation-github.md`; DEC-277–DEC-282.

---

## Implemented and verified in Phase 4

- [x] **Auditable 6-State Incident Lifecycle Machine (DEC-277, ADR-024):**
  - Explicit state transition matrix: `OPEN -> ACKNOWLEDGED -> MITIGATING -> RESOLVED -> CLOSED`, with `REOPENED` support.
  - Optimistic concurrency control via monotonic `version` counter preventing lost updates and race conditions (HTTP 409 Conflict).
  - RBAC authorization enforcement: Viewers rejected from mutating status (HTTP 403 Forbidden).
  - Append-only `incident_events` audit records (`incident_status_changed`, `incident_resolved`, `incident_closed`, `incident_reopened`).
  - Endpoints: `PATCH /api/v1/incidents/{incident_id}` with `expected_version` and optional `reason`.
- [x] **Deterministic Multi-Alert Correlation Engine (DEC-278, ADR-024):**
  - Correlates incoming Alertmanager alerts within a bounded 30-minute episode window.
  - Groups alerts matching `organization_id`, `service_id`, and `environment` into an active incident episode.
  - Duplicate delivery deduplication: identical fingerprint alerts record `alert_firing_duplicate` and do not increment correlated alert count or create duplicate incidents.
  - Distinct alert correlation: distinct alerts on same service elevate severity and increment `correlated_alert_count` with explainable event reason.
  - Strict negative boundaries: alerts from different organizations, different services, different environments, or outside the 30-minute window never merge.
  - Idempotent resolution handling: duplicate resolved alerts skip duplicate increments.
- [x] **Sample Application Release Instrumentation (DEC-279, ADR-024):**
  - Updated `examples/shop-api` with verified deployment version metadata.
  - Gauge `shop_api_build_info` exposing `version`, `commit_sha`, `environment`, and `build_id`.
  - Added endpoints `GET /version` and `POST /fault/release` for controlled bad-release simulation (`0.1.1-buggy`).
  - Structured logs and OTLP spans carry actual release revision attributes.
- [x] **Scoped GitHub Read-Only Integration (DEC-280, ADR-024):**
  - `ScopedGitHubClient` using standard library `urllib.request` with strictly read-only scopes.
  - Token isolation: secrets never leak to client bundles, logs, or agent prompts.
  - API resilience: bounded pagination (max 5 records), timeouts (5s), rate-limit handling (`x-ratelimit-remaining`), offline fallback.
  - Fallback: if GitHub Deployments API lacks records or errors out, gracefully falls back to verified commit history labeled as `commit history only`.
- [x] **Deployment-Aware Google ADK Investigation & Evidence Validation (DEC-281, DEC-282):**
  - Registered `get_recent_deployments` tool on `ReadOnlyToolGateway` with server-enforced service-to-repository scoping (T7 defense).
  - Anti-hallucination evidence validator (`validator.py`): rejects unverified deployment citations, enforces that deployment precedence is temporal correlation and not automated proof without corroborating telemetry.
  - Support for contradictory observations: logs/traces showing independent root cause override deployment timing assumptions.
- [x] **Frontend Incident Detail Lifecycle & Deployment UI (apps/web):**
  - `LifecycleControls`: interactive status buttons, version indicator, optional justification comment, optimistic locking error handling.
  - `DeploymentContext`: verified deployment card showing commit SHA, repository, environment, and honest fallback when disconnected.
  - Enhanced timeline event badges with color coding for correlated alerts, lifecycle transitions, and duplicates.
- [x] **Database Migration & Tests:**
  - Alembic revision `0006_phase4_lifecycle_correlation_github.py` adding `version`, `environment`, `correlated_alert_count` to `incidents`; and `github_repo`, `current_version`, `current_commit_sha` to `services`.
  - 107 unit tests passing across Phase 0–4 (`pytest -q -m 'not integration'`).
  - Clean TypeScript typecheck (`tsc --noEmit`), ESLint, and Node tests.

---

## Untested / Blocked / Deferred (Strict Phase Boundaries)

- [ ] **Runbook RAG with pgvector and Lexical Search:** `UNLOCKED IN PHASE 5`.
- [ ] **Multi-Agent Specialist Swarm:** `DEFERRED TO PHASE 5 / 6`.
- [ ] **Automated Remediation / n8n Internal Workflows:** `DEFERRED TO PHASES 6–7`.
- [ ] **Automated Production Remediation / Actions:** `OUT OF SCOPE FOR V1`.

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
- `make` is unavailable on this host; its test/spike/check recipes were executed directly. Isolated Compose migration/readiness checks pass (**2 passed, 1 skipped, 89 deselected**); live smoke is the intentional skip. Fresh API image build passes; its offline suite with networking disabled also passes (89 tests), and its isolated Compose checks pass (2 tests, 1 opt-in live smoke skipped).
- **External blocker:** `gh` absent; HTTPS push has no credential helper/usable credentials, and the SSH agent has no identities. Public GitHub API permits run/step inspection but full log download returns HTTP 403. Hosted repair success cannot be claimed until the commit is pushed and its exact run completes successfully.
- Full evidence, limitations and resume procedure: [Phase 2 report, CI repair addendum](PHASE_REPORTS/PHASE_2_VERIFICATION.md#9-ci-isolation-repair--2026-10-11).
