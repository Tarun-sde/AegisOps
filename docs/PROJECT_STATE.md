# AegisOps — Current Project State

**Updated:** 2026-10-13  
**Current phase:** Three-blocker release-gate remediation (DEC-336–DEC-338) — VERIFIED LOCALLY; Phase 8 — UNLOCKED for frontend development, NOT STARTED.
**Overall state:** Triple isolated gate PASSED (3/3 consecutive runs): 8 Playwright passed, 0 failed/skipped; PostgreSQL multi-session concurrency suite verified (5 passed against real containerized PostgreSQL); persisted investigation and independent 403 denial verified; non-root Beat schedule, dispatch and unattended cleanup verified. Hosted CI NOT VERIFIED.
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
| Gate scripts typing | `UV_CACHE_DIR="$PWD/.cache/uv" uv run --no-sync mypy scripts/verify_browser_gate.py scripts/browser_gate_fixture.py` | Exit 0: 2 files clean |
| Fast simulation E2E (in-memory SQLite) | `PYTHONPATH=. uv run --frozen --all-groups python scripts/verify_phase7_simulation_remediation_e2e.py` | Exit 0: 10/10 steps passed (unit coverage with mocked network boundaries) |
| PostgreSQL concurrency suite (real PostgreSQL 18) | `docker compose -p aegisops-verify -f docker-compose.yml -f docker-compose.verify.yml --profile verify run --rm verify` | Exit 0: 5 passed, 1 skipped, 158 deselected in 10.21s (proposal claim race, simulation expiry race, outbox dispatch lease race) |
| Isolated browser gate (Run 1 / 3) | `UV_NO_SYNC=1 make browser` | Exit 0 (`aegisops-browser-c10d48c1`): 8 passed (9.2s), UID 10001 & schedule check passed, cleanup passed |
| Isolated browser gate (Run 2 / 3) | `UV_NO_SYNC=1 make browser` | Exit 0 (`aegisops-browser-098d8852`): 8 passed (9.2s), UID 10001 & schedule check passed, cleanup passed |
| Isolated browser gate (Run 3 / 3) | `UV_NO_SYNC=1 make browser` | Exit 0 (`aegisops-browser-9d6d8741`): 8 passed (10.0s), UID 10001 & schedule check passed, cleanup passed |

**Browser gate triple verification (3/3 consecutive runs):**
`UV_NO_SYNC=1 make browser` was executed three consecutive times from a clean state. All three runs passed with 0 failures:
- **Run 1:** Project `aegisops-browser-c10d48c1`: production build passed, Beat schedule in `/tmp` as UID 10001 passed, 8 Playwright tests passed (9.2s), unattended fault reset verified, idempotent periodic cleanup verified.
- **Run 2:** Project `aegisops-browser-098d8852`: production build passed, Beat schedule assertions passed, 8 Playwright tests passed (9.2s), unattended fault reset and idempotency verified.
- **Run 3:** Project `aegisops-browser-9d6d8741`: production build passed, Beat schedule assertions passed, 8 Playwright tests passed (10.0s), unattended fault reset and idempotency verified.

All three gates used isolated PostgreSQL/Redis/API/worker/scheduler/shop-api stacks, dynamic loopback ports, and fresh migrations/fixtures. All containers, volumes, and networks were torn down cleanly after each run. Hosted CI and live model inference remain NOT VERIFIED.

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
