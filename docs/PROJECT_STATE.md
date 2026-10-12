# AegisOps — Current Project State

**Updated:** 2026-10-12  
**Current phase:** Phase 6 (Reliable n8n Automation, Transactional Outbox, and Human-Governed Remediation Proposals) — COMPLETED & VERIFIED  
**Overall state:** `PHASE 6 IMPLEMENTED AND VERIFIED LOCALLY; 139/139 UNIT/INTEGRATION TESTS PASSING; PLAYWRIGHT WEB TESTS PASSING; E2E DEMO SCRIPT VERIFIED; PHASE 7 UNLOCKED & READY (NOT STARTED)`  
**Source:** `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md` Phase 6; `docs/PHASE_REPORTS/PHASE_6.md`; `docs/ADR/ADR-026-phase6-outbox-n8n-remediation-proposals.md`; DEC-300–DEC-315.  
**Governing ADR:** ADR-026  

---

## 1. Implemented and Verified in Phase 6

- [x] **PostgreSQL Transactional Outbox Pattern (DEC-300, ADR-026):**
  - Migration `0008_phase6_outbox_and_proposals.py` adding `outbox_events`, `action_proposals`, and `proposal_approvals`.
  - Guaranteed atomic publication: business entity state changes (`incident.created`, `investigation.completed`, `proposal.created`, `proposal.approved`, `incident.resolved`) and outbox event records commit within the exact same database transaction.
  - 64KB bounded event payload limit preventing memory bloat and database denial-of-service.
- [x] **Reliable Outbox Delivery Dispatcher (DEC-301, DEC-302, ADR-026):**
  - Concurrency-safe batch claiming using database leasing (`locked_until`) and PostgreSQL `FOR UPDATE SKIP LOCKED`.
  - Network delivery performed strictly outside open database transactions, preventing database connection exhaustion during HTTP latency.
  - Exponential backoff with random jitter (`calculate_backoff_delay`, base 2.0s, max 3600s).
  - Strict bounded retries transitioning permanently failed events to `DEAD_LETTERED` after `max_attempts` (default 5).
- [x] **Cryptographic Webhook Signatures & Replay Protection (DEC-303, ADR-026):**
  - HMAC-SHA256 envelope signing (`X-AegisOps-Signature`, `X-AegisOps-Timestamp`, `X-AegisOps-Event-ID`, `X-AegisOps-Key-ID`).
  - Constant-time digest verification resisting timing attacks.
  - 300-second clock-skew tolerance rejecting expired or future-dated replay attacks.
- [x] **Receiver-Side Idempotency Deduplication (DEC-304, DEC-315, ADR-026):**
  - In-memory / durable receiver deduplication using event ID and stable idempotency keys.
  - Mandatory Exit Gate verified: repeated delivery of identical events returns `duplicate_ignored` with zero duplicate logical demo tickets created.
- [x] **Operator-Authored Internal n8n Infrastructure (DEC-305, DEC-306, ADR-026):**
  - Self-hosted n8n Community instance pinned to `n8nio/n8n:1.82.2` under Docker Compose `automation` profile.
  - Strict Licensing Boundary (DEC-306): n8n is strictly operator-authored for internal notification topologies (`incident-created`, `incident-investigated`, `approval-requested`, `incident-resolved`). Zero customer workflow builder, embedded editor, or SaaS workflow exposure.
  - PostgreSQL remains the sole authoritative source of truth; n8n is an untrusted downstream notification adapter.
- [x] **Deterministic Action Catalog & Immutable Proposals (DEC-308, DEC-309, ADR-026):**
  - Supported catalog items: `restart_demo_service`, `rollback_demo_release`, `request_staging_rollback`.
  - Typed Pydantic parameter validation disallowing arbitrary shell commands, raw URLs, container controls, or unauthorized parameters.
  - Canonical SHA-256 parameter hashing (`compute_parameters_hash`) ensuring key-order-independent, tamper-evident action payloads.
- [x] **Strict RBAC Approval State Machine (DEC-310, DEC-311, ADR-026):**
  - Lifecycle: `PROPOSED -> APPROVED / REJECTED / EXPIRED`.
  - Exact-payload approval validation: approver must supply the exact matching `parameters_hash`. Parameter tampering triggers 400 Bad Request.
  - Role gating: only `admin` or `owner` can approve. `viewer` role rejected with 403 Forbidden.
  - Tenant isolation: foreign organization members rejected with 404/403.
  - Lazy expiry: proposals past `expires_at` automatically transition to `EXPIRED` on access, preventing stale action execution.
- [x] **ZERO-Execution Security Boundary in Phase 6 (DEC-312, ADR-026):**
  - Action proposals can only be proposed, reviewed, approved, rejected, or expired.
  - No execution engine, shell runner, SSH adapter, Docker socket, or Kubernetes client is implemented or reachable.
  - Calling catalog `execute_action` strictly raises `NotImplementedError`. Executor endpoints `/api/v1/actions/execute` and `/api/v1/actions/remediate` return 404 Not Found.
- [x] **Next.js Human Review & Outbox Delivery UI (DEC-313, ADR-026):**
  - Route `/app/proposals` displaying real-time pending approvals, status badges, formatted immutable parameter JSON, and canonical SHA-256 hash preview.
  - Modal dialogs for Approve and Reject with mandatory reviewer comment.
  - Delivery ledger table showing recent outbox events, delivery status (`PENDING`, `DELIVERED`, `DEAD_LETTERED`), attempt counts, and manual flush trigger.
  - Top navigation updated with "Proposals" link and badge `Phase 6 · Outbox & Approvals`.

---

## 2. Current Test & Verification Summary

| Test Suite | Command | Exit Code | Result |
|---|---|---|---|
| Python Static Checks | `uv run --frozen --all-groups ruff check conftest.py apps agents scripts` | 0 | PASSED (0 lint errors across all 70 files) |
| Python Formatting | `uv run --frozen --all-groups ruff format --check conftest.py apps agents scripts` | 0 | PASSED (70 files verified formatted) |
| Python Type Checking | `uv run --frozen --all-groups mypy apps/api/app ...` | 0 | PASSED (36 source files type-checked clean) |
| Python Unit & Integration Tests | `pytest -q -m 'not integration'` | 0 | PASSED (139 passed, 3 deselected in 8.56s) |
| Phase 6 Test Suite | `pytest apps/api/tests/test_phase6_outbox_and_proposals.py` | 0 | PASSED (20/20 tests passed in 2.74s) |
| Express Service Tests | `npm test --workspace examples/shop-api` | 0 | PASSED (Build clean, 1/1 test passed in 167ms) |
| Web Lint & Format | `npm run lint && npm run format:check && npm run typecheck` | 0 | PASSED (ESLint clean, Prettier clean, TypeScript clean) |
| Playwright Web Tests | `npm run test:web` | 0 | PASSED (4/4 browser tests passed in 15.0s) |
| Phase 6 E2E Verification | `uv run --frozen --all-groups python scripts/verify_phase6_outbox_n8n_e2e.py` | 0 | PASSED (All 8 steps verified) |

---

## 3. Phase Boundaries & Phase 7 Readiness

### Untested / Blocked / Deferred (Strict Boundaries)
- [ ] **Sandboxed Remediation Execution Engine:** `DEFERRED TO PHASE 7 (AWAITING GATE)`.
- [ ] **Staging Canary Rollback & Restart Execution:** `DEFERRED TO PHASE 7`.
- [ ] **Production Rollback / Remediation Execution:** `OUT OF SCOPE FOR V1 (READ-ONLY + STAGING ALLOWLIST ONLY)`.

### Phase 7 Readiness
**PHASE 7 IS READY & UNLOCKED (NOT STARTED)**

All Phase 6 acceptance criteria (PostgreSQL transactional outbox, concurrency-safe dispatcher leasing, HMAC-SHA256 signing, receiver-side deduplication, n8n Docker profile & versioned workflows, remediation proposal service, RBAC exact-hash approvals, lazy expiry, and zero-execution invariant) are fully satisfied and verified with 100% test pass rate. The repository is ready for Phase 7.
