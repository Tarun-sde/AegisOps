# AegisOps — Current Project State

**Updated:** 2026-10-12  
**Current phase:** Three-blocker release-gate remediation (DEC-336–DEC-338) — VERIFIED LOCALLY; Phase 8 — UNLOCKED for frontend development, NOT STARTED.
**Overall state:** Final isolated gate PASSED: 8 Playwright passed, 0 failed/skipped; persisted investigation and independent 403 denial verified; non-root Beat schedule, dispatch and unattended cleanup verified. Hosted CI NOT VERIFIED.
**Source:** Master plan Phase 7/8; [audit](CODEBASE_AUDIT.md); [decision journal](ENGINEERING_DECISIONS.md), DEC-336–DEC-338 and BUG-20261012-001.
**Governing ADR:** ADR-023, ADR-027; existing DEC-335 preserved.

---

## 1. Implemented and Verified in Phase 7

- [x] **Incident Simulation Catalog & Scenarios S01–S06 (DEC-316, ADR-027):**
  - Six real failure scenarios implemented in `examples/shop-api`:
    - `S01_CHECKOUT_500`: Checkout HTTP 500 error injection with trace and metric logging.
    - `S02_SLOW_DB_QUERIES`: Controlled 800ms database query latency injection.
    - `S03_DB_POOL_EXHAUSTION`: Connection pool contention producing 503 timeouts.
    - `S04_BROKEN_RELEASE`: Faulty `0.1.1-buggy` deployment with commit SHA correlation.
    - `S05_SERVICE_UNAVAILABLE`: Probe failure returning 503 on `/healthz`.
    - `S06_SLOW_DOWNSTREAM`: 1200ms downstream dependency latency propagation.
  - Zero host Docker socket exposure; safe in-process fault adapter via `/fault/inject` and `/fault/reset` (in-process latency, pool timeout, runtime version, and probe failure injection avoiding physical database connection exhaustion or host Docker process destruction).
- [x] **Persistent Simulation Run State & Lifecycle Controller (DEC-317, DEC-318, ADR-027):**
  - Migration `0009_phase7_simulation_and_execution.py` adding `simulation_runs`, `simulation_events`, and `action_executions`.
  - State machine: `CREATED -> ACTIVE -> RECOVERING -> COMPLETED` with failure branches `EXPIRED`, `FAILED`, `CANCELLED`.
  - Concurrency guard: Only one active simulation permitted per service/environment.
- [x] **Automatic Expiration & Watchdog Cleanup (DEC-320, ADR-027):**
  - Configurable scenario TTL (default 900s).
  - Dual reconciliation: lazy expiration checks on access and scheduled Celery task `reconcile_simulation_expiry_task`.
- [x] **Sandboxed Remediation Execution Engine (DEC-321, DEC-322, DEC-325, ADR-027):**
  - Deterministic action catalog: `restart_demo_service` and `rollback_demo_release`.
  - Strict Staging-Only Boundary (DEC-322): Execution against production targets fails closed before any network action.
  - Safe HTTP executor interacting with isolated demo services with strict timeouts.
- [x] **Two-Phase Approval-to-Execution Decoupling (DEC-323, ADR-027):**
  - Separate endpoints: `POST /api/v1/actions/proposals/{id}/approve` and `POST /api/v1/actions/proposals/{id}/execute`.
  - Cryptographic parameter verification re-checked at execution time against approval record.
- [x] **Row-Level Claiming & Concurrency-Safe Idempotency (DEC-324, ADR-027):**
  - Atomic claiming via PostgreSQL `SELECT FOR UPDATE` on proposal.
  - Database unique constraint on `(proposal_id)` in `action_executions` prevents duplicate executions.
- [x] **Distinct Operational Recovery Verification (DEC-326, ADR-027):**
  - Action execution success decoupled from service recovery.
  - Dedicated endpoint `POST /api/v1/simulation/runs/{run_id}/verify-recovery` verifies actual health endpoints and emits `service.recovery_observed`.
- [x] **Google ADK Agent Zero Execution Authority (DEC-328, ADR-027):**
  - Agent tool gateway provides `create_remediation_proposal` tool only.
  - Agent cannot approve, execute, or bypass deterministic backend authorization.
- [x] **Comprehensive Auditing & Transactional Outbox (DEC-327, ADR-027):**
  - Full timeline events recorded for simulation starts, activations, resets, expirations, proposal claims, executions, and recovery verifications.
- [x] **Next.js Simulation Lab UI (DEC-330, ADR-027):**
  - Route `/app/simulation-lab` displaying S01–S06 catalog cards, active fault indicator, manual reset and recovery verification controls, remediation review panel, and execution history.

---

## 2. Current Test & Verification Summary

| Check | Exact command | Actual result |
|---|---|---|
| Python and Express regression | `UV_NO_SYNC=1 make test` | Exit 0: 158 Python passed, 3 integration tests deselected, 132 warnings; Express 1 passed, 0 failed/skipped |
| Static checks | `UV_NO_SYNC=1 make check` | Exit 0: Ruff check/format (81 files), mypy (48 files), ESLint, Prettier, both workspace typechecks |
| New verification scripts | `UV_CACHE_DIR="$PWD/.cache/uv" uv run --no-sync mypy scripts/verify_browser_gate.py scripts/browser_gate_fixture.py` | Exit 0: 2 files |
| Earlier isolated attempt | `UV_NO_SYNC=1 make browser` | Historical exit 2: 7 passed / 1 failed; superseded by final rerun |
| Final corrected gate | `UV_NO_SYNC=1 make browser` | Exit 0: production build, scheduler assertions and all 8 Playwright tests passed; 0 failed/skipped |

`UV_NO_SYNC=1 make browser` exited 0: **8 passed, 0 failed, 0 skipped** in 8.9s. The intercepted HTTP 403 displayed the expected error, no success badge and no persisted run. The positive test created offline run `399d183e-af4a-4e06-b8bb-c74a6cdfa386` for incident `00000000-0000-0000-0000-000000000067`, verified the workspace/incident association, and displayed the persisted identity/state after reload. Beat's explicit UID 10001 and `/tmp/celerybeat-schedule` assertion passed, as did singleton dispatch, pre-TTL fault preservation, unattended real reset and repeated-cleanup idempotency.

The CI-equivalent gate used fresh migrations and authenticated fixtures in isolated project `aegisops-browser-44bb273b`, API `127.0.0.1:32769`, and a production frontend build. Cleanup removed its containers, PostgreSQL volume and network. No source correction or dependency change was needed. Hosted CI and live inference/full telemetry-to-remediation verification remain NOT VERIFIED.

Runtime evidence: [full gate transcript](../artifacts/aegisops-browser-44bb273b/gate.txt), [watchdog](../artifacts/aegisops-browser-44bb273b/watchdog.txt), [container logs](../artifacts/aegisops-browser-44bb273b/compose.log). Ignored local artifacts. Earlier unit/static command transcripts remain under `/tmp/aegisops-release-tests.log` and `/tmp/aegisops-release-static.log`.

---

## 3. Phase Boundaries & Phase 8 Readiness

### Untested / Blocked / Deferred (Strict Boundaries)
- [ ] **Phase 8 Full UI Redesign:** `DEFERRED TO PHASE 8 (NOT STARTED)`.
- [ ] **Phase 9 40–60 Case Benchmark Evaluation:** `DEFERRED TO PHASE 9 (NOT STARTED)`.
- [ ] **Automated Production Remediation:** `OUT OF SCOPE FOR V1 (STAGING/DEMO ONLY)`.
- [ ] **Unrestricted Infrastructure Shell/Docker Access:** `STRICTLY FORBIDDEN (SECURITY INVARIANT)`.

### Phase 8 Readiness
**GO — local foundation ready for premium landing page, authentication UI and interactive dashboard development.**

All required targeted local gates passed. Phase 8 implementation remains NOT STARTED. Hosted CI and live model/full live-system verification are not established by this deterministic local gate. No commit or push performed.
