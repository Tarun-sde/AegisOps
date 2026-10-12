# AegisOps — Codebase Audit, Cleanup & Foundation Hardening Report

**Audit Date:** 2026-10-12  
**Auditor:** Senior Full-Stack Engineer, Reliability Engineer & Security Reviewer  
**Methodology:** Ponytail Minimalist Engineering (YAGNI, Standard Library & Native Features First, Zero Bloat)  
**Governing Decisions:** DEC-331, DEC-332, DEC-333, DEC-334, DEC-335 (docs/ENGINEERING_DECISIONS.md); ADR-001–ADR-027  
**Current Verification:** Three-blocker fixes VERIFIED LOCALLY (DEC-336–DEC-338); final isolated gate passed all 8 browser tests and scheduler assertions. Earlier dependency audits were not repeated because dependencies did not change.

---

## Final targeted verification — 2026-10-12

`UV_NO_SYNC=1 make browser` exited 0: **8 passed, 0 failed, 0 skipped** in 8.9s. The intercepted HTTP 403 displayed the expected error, no success badge and no persisted run. The positive test created offline run `399d183e-af4a-4e06-b8bb-c74a6cdfa386` for incident `00000000-0000-0000-0000-000000000067`, verified the workspace/incident association, and displayed the persisted identity/state after reload. Beat's explicit UID 10001 and `/tmp/celerybeat-schedule` assertion passed, as did singleton dispatch, pre-TTL fault preservation, unattended real reset and repeated-cleanup idempotency.

The CI-equivalent gate used fresh migrations and authenticated fixtures in isolated project `aegisops-browser-44bb273b`, API `127.0.0.1:32769`, and a production frontend build. Cleanup removed its containers, PostgreSQL volume and network. No source correction or dependency change was needed. Hosted CI and live inference/full telemetry-to-remediation verification remain NOT VERIFIED.

[Final gate transcript](../artifacts/aegisops-browser-44bb273b/gate.txt). This result supersedes the earlier failure/blocked-run entries retained below.

## 1. Executive Summary

This comprehensive audit and targeted remediation inspected, cleaned, refactored, and hardened the AegisOps repository across all completed implementation phases (Phases 0 through 7). Following an independent verification review (Astra), four specific engineering findings were resolved:
1. **Authentication & CSRF Defense:** Next.js server-rendered requests forward authenticated session cookies strictly to the trusted API base; browser client requests include credentials; mutating operations (`POST`, `PUT`, `PATCH`, `DELETE`) automatically attach double-submit CSRF tokens (`x-csrf-token`), rejecting missing/invalid tokens with 403 Forbidden.
2. **Automatic Simulation Expiry Scheduling:** Configured Celery Beat periodic schedule for simulation TTL expiry reconciliation (`aegisops.reconcile_simulation_expiry` every 10s) and outbox dispatch (`aegisops.dispatch_outbox_events` every 15s), backed by row locking (`SELECT FOR UPDATE SKIP LOCKED`) and a dedicated scheduler service in Compose.
3. **Deterministic Browser E2E Coverage:** Replaced conditional incident checks in Playwright with deterministic navigation to seeded incident fixtures, verifying investigation triggers, 401 unauthenticated access rejection, and 403 missing-CSRF rejection.
4. **Documentation & Verification Grounding:** Corrected architecture descriptions (opaque session cookies vs JWT, standard library `scrypt` vs bcrypt, verified pinned versions) and explicitly separated in-process mocked integration testing from live container and browser execution.

**Release-gate correction (2026-10-12): FAIL / NO-GO pending rerun.** The previous browser test could pass on HTTP 403, CI relied on an existing API, and Beat could not write its schedule. Those source fixes are now implemented under DEC-336–DEC-338. The new isolated gate demonstrated real Beat/worker cleanup and persisted investigation creation, but finished with 7 browser tests passed / 1 failed because the negative test's alert selector matched both the application error and Next.js route announcer. The selector is corrected; automatic approval review blocked the rerun due to its usage limit, and approval was requested. Do not interpret previous all-green claims as current release-gate evidence.

---

## 2. Pinned Architecture & Baseline

The AegisOps repository comprises an event-driven incident investigation platform with pinned dependency versions verified against repository manifests and lockfiles:

| Component | Pinned Version & Image | Role & Verified Implementation Details |
| :--- | :--- | :--- |
| **Control Plane API** | FastAPI 0.141.0 (Python 3.14) | Incident ingestion, rule evaluation, proposal lifecycle, simulation control, audit log |
| **Relational & Vector DB** | PostgreSQL 18 via `pgvector:0.8.7-pg18-bookworm` | Multi-tenant relational schema, outbox events, action proposals, vector embeddings (`pgvector`) |
| **Cache & Limiter** | Redis 8.10.2 via `redis:8.10.2-alpine` | Ephemeral rate-limiting, short-term session cache, Celery message broker/result backend |
| **Worker & Scheduler** | Celery 5.6.3 (`celery worker` & `celery beat`) | Background agent execution, transactional outbox dispatch, periodic simulation expiry watchdog |
| **AI Investigator** | Google ADK 2.11.0 + LiteLLM 1.104.2 | Autonomous incident triage, hypothesis generation, evidence citations (Gemini 2.5 / 3.5 Flash) |
| **Observability Stack** | Prometheus 3.2.1, Loki 3.4.2, Tempo 2.7.1, Alertmanager 0.28.1 | Scraped RED metrics, LogQL log streams, OpenTelemetry distributed tracing, alert ingestion |
| **Demo Microservice** | Express 5.3.0 (`shop-api`) | Simulated e-commerce checkout service with RED metrics & in-process fault injection |
| **Frontend Web App** | Next.js 16.4.0 (React 19.3.0) | Operator dashboard shell, SSR data fetching, incident timeline, simulation lab, design tokens |

### Phase Implementation Status Verified

- **Phase 0 (Foundation & Locks):** Pinned `uv.lock` and `package-lock.json`, Docker Compose stack, offline ADK runner (`IncidentInvestigatorRunner`).
- **Phase 1 (Telemetry & Ingestion):** Express RED metrics (`prom-client`), Prometheus scraper, route normalizer, incident ingestion endpoint (`/api/v1/incidents/ingest`), rule-based alert evaluation.
- **Phase 2 (Chaos Simulation):** 6 realistic failure scenarios (S01 checkout crash, S02 latency injection, S03 CPU burn, S04 memory leak, S05 DB pool exhaustion, S06 corrupted cart data), synthetic traffic generator, fault reset API.
- **Phase 3 (Tenancy, RBAC & Outbox):** Multi-tenant organization scoping, role hierarchy (`owner`, `admin`, `operator`, `viewer`), Python standard library `scrypt` password hashing with cryptographic salt, opaque HTTP-only session cookie authentication (`aegisops_session`), double-submit CSRF protection (`aegisops_csrf` / `x-csrf-token`), transactional Outbox pattern (`outbox_events`). *(Note: Authentication uses opaque sessions, not JWT; password hashing uses scrypt, not bcrypt).*
- **Phase 4 (AI Incident Investigator):** Single-agent ADK 2.11.0 engine, deterministic tool registry (`PrometheusTool`, `LokiTool`, `TempoTool`), structured hypothesis evaluation, strict evidence validation.
- **Phase 5 (Telemetry Correlation & RAG):** Live PromQL and LogQL query engines, Tempo trace exemplar correlation, hybrid RAG subsystem (`IncidentEmbeddingService`, `RunbookRetriever`) with vector fallback.
- **Phase 6 (Outbox Worker & Action Proposals):** Reliable asynchronous Outbox Worker with exponential backoff and dead-letter queue, cryptographic action proposals with SHA-256 payload hashing, state machine transitions (`PROPOSED` -> `APPROVED` / `REJECTED` -> `EXECUTED`).
- **Phase 7 (Simulation Lab & Controlled Remediation):** Fault injection lifecycle, human-approved remediation execution (`RemediationExecutor`), atomic execution claiming (`SELECT FOR UPDATE`), staging allowlist enforcement, periodic Celery Beat watchdog.

---

## 3. Remediated Issues & Engineering Decisions

### 3.1 Port Inconsistency between Services (DEC-332)
- **Problem:** `SimulationService` (`apps/api/app/simulation/service.py`) and `RemediationExecutor` (`apps/api/app/actions/executor.py`) defaulted to `http://localhost:4000` when `AEGISOPS_SHOP_API_URL` was unset. However, `examples/shop-api` and `docker-compose.yml` run on port `3001`.
- **Fix:** Corrected both fallback URLs to `http://localhost:3001` (or `http://shop-api:3001` in Docker).

### 3.2 Docker SSR and Tracing Connectivity (DEC-332)
- **Problem:**
  - `docker-compose.yml` omitted `IN_DOCKER: "1"` and `AEGISOPS_TEMPO_URL: http://tempo:3200` in `api-environment`, causing Tempo queries in Docker to fall back to localhost.
  - The `web` service omitted `API_URL: http://api:8000`, causing Next.js SSR fetches to fail against `localhost:8000`.
- **Fix:** Injected `IN_DOCKER: "1"` and `AEGISOPS_TEMPO_URL: http://tempo:3200` into `api-environment`, and configured `API_URL: http://api:8000` with `depends_on: api: {condition: service_healthy}` in `web`.

### 3.3 Decentralized Domain Exception Handling (DEC-331)
- **Problem:** Proposal and incident route handlers manually caught domain exceptions with repetitive try/except boilerplate.
- **Fix:** Implemented centralized FastAPI `@app.exception_handler` mappings in `apps/api/app/main.py` standardizing HTTP error payloads (`{"detail": "..."}`).

### 3.4 Missing Explicit CORS Configuration (DEC-331)
- **Problem:** The FastAPI application lacked explicit `CORSMiddleware`, causing browser cross-origin preflight rejections between port 3000 and 8000.
- **Fix:** Added `CORSMiddleware` with default allowed origins (`http://127.0.0.1:3000`, `http://localhost:3000`), configurable via `AEGISOPS_ALLOWED_ORIGINS`, with `allow_credentials=True`.

### 3.5 Frontend Styling Inconsistencies & Reusable UI Primitives (DEC-333)
- **Problem:** `apps/web` lacked structured CSS variables, resulting in ad-hoc hardcoded hex values and lack of component primitives.
- **Fix:** Established design tokens in `apps/web/app/globals.css`, built zero-dependency primitives (`Badge`, `Button`, `Card`, `AlertBanner`, `Skeleton`) in `apps/web/app/components/`, and implemented `AuthProvider` in `apps/web/app/lib/auth-context.tsx`.

### 3.6 Stale Model Reference in `.env.example` (DEC-332)
- **Problem:** `.env.example` listed `gemini-3.8-flash` which has a 20 RPD daily quota.
- **Fix:** Updated `.env.example` default to `gemini-3.5-flash` per DEC-237.

### 3.7 Static Analysis, Linting & Python 3.14 Cleanliness (DEC-334)
- **Problem:** Nested `if`/`with` structures, redundant `list()` wrapping in `sorted()`, unused unpacked variables, and limited Makefile mypy coverage.
- **Fix:** Resolved Ruff lint findings; updated `Makefile` to typecheck all 48 source files via `mypy --exclude "alembic/versions|tests" apps agents`.

### 3.8 Server-Side Session Forwarding & CSRF Enforcement (DEC-335)
- **Problem:** Server-rendered incident requests failed to forward authenticated session cookies to the API; browser mutations omitted CSRF tokens; API allowed demo token to bypass CSRF check before token verification.
- **Fix:** Centralized requests through `apiFetch` in `apps/web/app/lib/api.ts`:
  - Dynamically extracts session cookies on server via `next/headers` and forwards strictly to `API_BASE` (never leaking to external hosts).
  - Client-side requests attach `credentials: "include"`.
  - Mutating methods (`POST`, `PUT`, `PATCH`, `DELETE`) automatically extract and attach `x-csrf-token` from `aegisops_csrf` cookie.
  - Reordered FastAPI `get_current_user` in `apps/api/app/auth.py` so CSRF double-submit token verification runs before demo token bypass, ensuring missing/invalid CSRF tokens return 403 Forbidden.

### 3.9 Periodic Simulation Expiry Scheduling via Celery Beat (DEC-335)
- **Problem:** Simulation expiry cleanup task existed (`reconcile_simulation_expiry_task`) but lacked a periodic schedule; Docker Compose ran a worker without a scheduler.
- **Fix:**
  - Configured `celery_app.conf.beat_schedule` in `apps/worker/celery_app.py` scheduling `aegisops.reconcile_simulation_expiry` every 10 seconds (expires in 8s) and `aegisops.dispatch_outbox_events` every 15 seconds.
  - Added row-level concurrency locking (`.with_for_update(skip_locked=True)`) in `reconcile_simulation_expiry_task` to prevent race conditions across concurrent worker instances.
  - Added a dedicated single-instance `scheduler` service (`celery beat`) in `docker-compose.yml`.

### 3.10 Deterministic Playwright Testing without Silent Skipping (DEC-335, corrected by DEC-337–DEC-338)
- **Problem:** `apps/web/tests/shell.spec.ts` guarded investigation tests with `if (await firstIncidentLink.isVisible())`, passing silently when incidents failed to load.
- **Current fix:** `make browser` provisions fresh isolated dependencies and two known incidents. The positive browser test requires real login, HTTP 201, UUID identity, correct tenant/incident, persistent lifecycle state and matching UI after reload. The independent intercepted HTTP 403 test requires a visible error, no success badge and no persisted run. Existing 401 and missing-CSRF 403 coverage remains.
- **Scheduler correction (DEC-336):** Beat writes `/tmp/celerybeat-schedule` under the existing non-root UID; one replica is configured. Real dispatch and unattended cleanup were observed in the isolated stack.

---

## 4. Dead Code and Unused Dependencies Removed

1. **Redundant Code Simplifications:**
   - Removed redundant `list()` inside `sorted(...)` in `apps/api/app/lifecycle.py:127`.
   - Collapsed nested `if` statements in `apps/api/app/schemas.py:129` and `agents/incident_investigator/validator.py:175`.
   - Replaced redundant async context manager nesting in `apps/api/app/main.py:check_postgres`.
2. **Dependency Tree Verification:**
   - Zero unnecessary large frontend dependencies (GSAP, Three.js, React Flow, or Tailwind v3/v4 JS runtimes) added.
   - Pinned dependencies verified clean with zero unused direct packages.

---

## 5. Security and Reliability Invariants

1. **Multi-Tenant Isolation:**
   - All database queries for incidents, proposals, simulations, and outbox events strictly filter on `organization_id`.
   - Alien tenant requests return 404 Not Found (or 403 Forbidden), preventing data enumeration.
2. **Opaque Session & CSRF Protection:**
   - Authentication relies on opaque cryptographically random session tokens stored in HTTP-only `aegisops_session` cookies and hashed in the database/Redis.
   - Password hashing uses standard library `hashlib.scrypt` with unique 16-byte cryptographic salts.
   - State mutations require a matching `x-csrf-token` header equal to the `aegisops_csrf` cookie value. Missing or mismatched tokens fail with 403 Forbidden.
3. **Cryptographic Action Proposals:**
   - Action proposals generate a deterministic SHA-256 digest of their target service, action name, and parameters.
   - Approval and execution verify this hash (`verify_hash()`) to prevent parameter tampering or payload drift.
4. **Atomic Execution Claiming:**
   - Proposal execution uses database `SELECT FOR UPDATE` inside a transaction to lock the proposal record and transition its state to `EXECUTING`, preventing duplicate execution under concurrent requests.
5. **Periodic Watchdog Safety:**
   - Expired simulations are reconciled without browser interaction via scheduled Celery Beat tasks locking records with `skip_locked=True`.
6. **Public Demo Guest Boundary:**
   - Public demo users authenticate as `viewer` role; all simulation mutations (`/start`, `/reset`) and action executions (`/execute`) strictly enforce `can("admin")` and fail closed with HTTP 403.
7. **CORS Security:**
   - Specific origin whitelisting (`http://127.0.0.1:3000`, `http://localhost:3000`), preserving cookie/credential safety.

---

## 6. Categorized Verification and Evidence

Verification evidence is categorized strictly by environment and boundary:

### A. Unit-Tested Behavior (In-Memory & Hermetic)
- **Pytest Suite:** 158 passed, 3 deselected, 132 warnings in 21.44s (`UV_NO_SYNC=1 make test`).
  - Covers RBAC, token validation, session expiration, password scrypt hashing, action catalog parameter validation, SHA-256 parameter hashing, and domain state machines.
- **Express Unit Tests:** `npm test --workspace examples/shop-api` (1 comprehensive test passed; 0 failed/skipped).
  - Covers RED metric counters, route normalizers, and in-process fault injection endpoints (`/fault/inject`, `/fault/reset`).

### B. In-Process Mocked Integration Testing
- **Phase 7 Integration Script:** `scripts/verify_phase7_simulation_remediation_e2e.py` (10/10 steps PASS).
  - Uses an isolated in-memory SQLite database (`sqlite:///:memory:`) to verify two-phase approval-to-execution claiming, transactional outbox creation, and immutable parameter hash checks.
  - **Boundaries:** HTTP calls to the demo microservice (`_call_shop_api`) and recovery health probes (`urllib.request.urlopen`) are mocked in this script to validate state transitions independently of container networking.

### C. In-Process Scheduler and Outbox Regression Tests
- **Simulation Expiry & Celery Beat Suite:** `apps/api/tests/test_simulation_expiry_scheduler.py` (5/5 tests PASS).
  - Verifies Celery Beat schedule registration, bounded TTL enforcement, active state preservation before expiry, automatic database cleanup without browser activity, and idempotent re-execution safety.
- **Outbox Worker Suite:** `apps/api/tests/test_phase6_outbox_and_proposals.py` (20/20 tests PASS).
  - Verifies transaction outbox persistence, polling, exponential backoff, and state transition idempotency.

### D. Isolated Runtime Scheduler and Browser Testing
- **Command:** `UV_NO_SYNC=1 make browser` creates a unique Compose project, migrates a new PostgreSQL database, waits for PostgreSQL/Redis/API readiness, seeds guarded synthetic fixtures and builds the production frontend with its allocated loopback API address. It runs the same command as CI.
- **Scheduler:** Actual Beat dispatch and worker success, real fault remaining active before TTL, unattended HTTP reset, and repeated periodic idempotency passed. [Watchdog assertions](../artifacts/aegisops-browser-1968b97b/watchdog.txt) and [container logs](../artifacts/aegisops-browser-1968b97b/compose.log) are ignored local evidence.
- **Browser:** 7 passed / 1 failed. Positive test created run `5b4c8d38-0574-45e4-afa5-97fcafe3a712` for incident `00000000-0000-0000-0000-000000000067`, verified its workspace and persisted/UI identity after reload. Negative creation returned HTTP 403 and displayed an error; an ambiguous locator prevented completion of subsequent assertions. The scoped selector and an explicit scheduler UID/file assertion are implemented but their rerun is blocked.
- **Isolation:** API used dynamically allocated `127.0.0.1:32768`; project `aegisops-browser-1968b97b` and its database volume were removed. No developer database or existing stack supplied fixtures.

### E. Live Model Inference Boundaries
- External Google ADK Gemini API calls require live network access and valid `GOOGLE_API_KEY`. When offline or key is absent, deterministic fallback runners or mock adapters are utilized.

### F. Telemetry & Fault Injection Execution
- This remediation verified real Express fault injection/reset with PostgreSQL and Celery. It did not rerun the complete live observability, model, approval and remediation chain.

### G. Untested or Unavailable Capabilities
- **Automated Production Remediation:** Intentionally omitted in v1. All remediation actions are strictly bounded to staging environments.
- **Arbitrary Host Shell Access:** Strictly forbidden by security invariants.

---

## 7. Verification Results Summary Table

| Check | Command | Result |
|---|---|---|
| Regression tests | `UV_NO_SYNC=1 make test` | Exit 0: Python 158 passed / 3 integration tests deselected / 132 warnings; Express 1 passed |
| Static checks | `UV_NO_SYNC=1 make check` | Exit 0: Ruff check/format (81 files), mypy (48 files), ESLint, Prettier, TypeScript |
| Gate scripts typing | `UV_CACHE_DIR="$PWD/.cache/uv" uv run --no-sync mypy scripts/verify_browser_gate.py scripts/browser_gate_fixture.py` | Exit 0: 2 files |
| Production build | `npm run build` (inside gate) | Passed: Next.js production and shop-api builds |
| Isolated gate | `UV_NO_SYNC=1 make browser` | Exit 2: runtime scheduler checks passed; Playwright 7 passed / 1 failed |
| Compose validation | Gate's `docker compose … config --quiet` on base + verify + browser overlays | Passed before fresh-stack creation |
| Corrected gate | `UV_NO_SYNC=1 make browser` | BLOCKED before execution by automatic approval review usage limit |
| Hosted CI | Not run; no push authorized | NOT VERIFIED |

Full local transcripts: `/tmp/aegisops-release-tests.log`, `/tmp/aegisops-release-static.log`, `/tmp/aegisops-release-gate-2.log`. The last completed browser run is recorded honestly; passing static analysis does not verify the corrected runtime assertions.

---

## 8. Foundation Readiness for Phase 8

**GO — local foundation ready for frontend development.** Final `UV_NO_SYNC=1 make browser` exited 0: all 8 Playwright tests and the explicit non-root schedule assertion passed, with actual periodic dispatch and unattended cleanup. No unresolved local blocker remains from these three findings. Hosted CI and live inference/full telemetry-to-remediation remain NOT VERIFIED. No code correction, dependency change, commit or push was needed for this verification.
