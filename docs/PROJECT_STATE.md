# AegisOps — Current Project State

**Updated:** 2026-10-16
**Current phase:** Phase 8.5 Critical Defect Repair — REPAIRED LOCALLY, PENDING FINAL INDEPENDENT ACCEPTANCE AUDIT.
**Overall state:** Repaired all independently reproduced defects from Astra's Phase 8.5 acceptance audit across Priority 0 (PromQL cross-tenant leakage, PromQL injection, unauthorized trace retrieval, secret leakage into evidence), Priority 1 (duplicate incidents across active states, consistent manual recovery participation), and Priority 2 (clearing nullable settings, browser text parity, test suite alignment). Gemini's prior 177-test completion claim is explicitly not accepted as proof of product correctness; all repairs are backed by empirical negative and positive regression tests and returned for final independent acceptance audit. Phase 9 remains locked.
**Source:** User Phase 8.5 Defect Repair brief; [completion report](PHASE_8_5_COMPLETION.md); [audit findings](docs/AUDIT_FINDINGS_PHASE_8_5.md).
**Governing Decisions:** DEC-390–401; ADR-023/027/028 security and ADR-029/030 source identity.

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

## 2. Prior Phase 7 Test & Verification Summary

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

### Completed / Deferred / Forbidden (Strict Boundaries)
- [x] **Phase 8 Frontend Integration:** `VERIFIED LOCALLY`; static/unit/browser/accessibility gates passed on 2026-10-14.
- [ ] **Phase 9 40–60 Case Benchmark Evaluation:** `DEFERRED TO PHASE 9 (NOT STARTED)`.
- [ ] **Automated Production Remediation:** `OUT OF SCOPE FOR V1 (STAGING/DEMO ONLY)`.
- [ ] **Unrestricted Infrastructure Shell/Docker Access:** `STRICTLY FORBIDDEN (SECURITY INVARIANT)`.

### Phase 8 Readiness (historical, before Phase 8.1 correction)
**COMPLETE LOCALLY — selected frontend design integrated and acceptance gates passed; evidence limits below remain explicit.**

All Phase 7 targeted local gates passed. Phase 8 frontend integration is verified locally; acceptance evidence is in [the Phase 8 report](PHASE_REPORTS/PHASE_8_FRONTEND_INTEGRATION.md). Hosted CI and live model/full live-system verification are not established by this deterministic local gate. No commit or push performed.


## Phase 8 integration progress — 2026-10-14

Selected design source f469697 is integrated into the existing apps/web application on feat/phase8-frontend-integration. Real service cards, scoped session context, preserved incident UUID routes, persisted investigation/evidence explorer, native proposal review dialog and readable simulation/runbook controls are implemented. Dashboard time-series APIs are unavailable and explicitly labeled; backend and migrations are unchanged. Decisions ADR-028 and DEC-339–350. Final make check, make test (158 Python passed, 6 deselected; Express 1 passed), and make browser (16 passed in 23.4s plus real scheduler/expiry assertions) passed. Core accessibility/readability and 375/768/1440px layout checks passed; desktop/mobile captures reviewed. Local logs/captures: artifacts/phase8-20261014/. Phase 9 remains NOT STARTED.


## Phase 8.1 correction complete locally — 2026-10-14

Restored the committed reference’s full landing and motion, original workspace/card/list/sidebar, analytics frame and persisted investigation presentation. User-authorized ADR-029 supersedes the prior selective visual rewrite. Main Compose web was rebuilt/recreated without replacing API/Postgres/Redis or existing volumes. Final image `sha256:175cc0163b5d9ec2632cac1c5f1ad001e4e0eaf34c61de7630fc4a7416305b71`, Next build `fHtE5t1qf8t8KXjNtc4nA`; 49 runtime source/package hashes match. Main backend/agent/worker/infrastructure files are unchanged.

`make check` PASS; `make test` 158 Python passed, 6 deselected, 132 warnings, Express 1 passed; `make browser` 17 passed in 41.3s on aegisops-browser-83700dc4 plus real scheduler expiry/idempotency checks. All six viewport comparisons passed; delivered hero/sidebar/card widths equal the reference. Actual images refreshed after the final scoped Simulation Lab fix. Nine-route Docker axe serious/critical findings: zero. Full commands, source map, failed attempts, screenshot links and intentional differences: [fidelity report](PHASE_8_1_VISUAL_FIDELITY_REPORT.md). Local evidence: artifacts/phase8-1/.

Dedicated labeled Visual QA organization/service/incident/offline evidence remain available in the existing database for review; no existing user records were modified. Live telemetry aggregation, live-model correctness, Safari/Firefox, physical-device/assistive-technology sessions and hosted CI remain unverified. Six deselected PostgreSQL integration tests were not separately rerun. Work remains uncommitted on feat/phase8-frontend-integration; no push/merge/deploy. Phase 9 NOT STARTED.

## Phase 8.4 — Hero & Scroll Storytelling Restoration Complete Locally — 2026-10-15

Restored the original design reference's architectural hero composition, linework density, and interactive GSAP scroll storytelling using authentic, original AegisOps observability artwork:
- **Hero Elevation & Blueprint:** Replaced the generic left-copy/right-flowchart layout with an expansive upper `.hero-drawing` technical canvas and lower editorial `.hero-caption` band in 54%/30%/16% split. Replaced the 8-box flowchart with the original "AegisOps System Blueprint" SVG (`TopologyDrawing`, 1200×600) featuring 4 layers: structural boundaries with dimension markers, OpenTelemetry trace bus and signal instrumentation, highlighted Shop API → PostgreSQL anomalous path with 720ms latency indicator, and interactive drag-to-inspect rectangle.
- **Scene 01 (Observe) Time-Series Signal Repair:** De-coupled the time-series in `SignalChart` into a permanent 120ms baseline curve (`.signal-baseline`) visible from scroll progress 0.0, and an animated rising anomaly spike (`.signal-line`) with `pathLength="1"` crossing the 500ms threshold to 840ms, synchronized with a scaling alert beacon (`.signal-alert`) and dependency latency indicator.
- **Continuous 4-Scene Incident Narrative:** Unified all four workflow scenes into one continuous investigation of sample incident `INC-DEMO-042` across Observe (latency spike), Investigate/Advise (trace waterfall + connection pool hypothesis), Act (human-governed staging remediation proposal + approval boundary), and Learn (incident ledger + runbook retrieval).
- **Cross-Browser SVG Path Length Normalization:** Declared `pathLength="1"` on all animated stroke paths (`.signal-line`, `.evidence-link`, `.approval-route`, `.history-spine`) to ensure robust GSAP stroke-dash progress scrubbing across all browsers.
- **Verification:** Rebuilt and recreated the live Docker container (`aegisops-web-1` on port 3000). Verified HTTP 200. Automated static checks (`UV_NO_SYNC=1 make check`) passed (Exit 0: Ruff, mypy, ESLint, Prettier, dual workspace TypeScript check). Playwright test suite (`apps/web/tests/branding.spec.ts`) passed (5/5 passed in 19.3s). Captured 24 visual QA screenshots across 5 viewports (1920×1080, 1440×900, 1024×768, 390×844, 375×812), all 4 scroll phases, reverse scrubbing, and reduced motion in `artifacts/hero-storytelling-qa/`. Decisions DEC-372–376. No commit, push, or merge performed.


## Final design parity correction — 2026-10-15

User-authorized correction in progress under DEC-377–382. Earlier local functional results do not establish final visual parity. See [active report](PHASE_REPORTS/PHASE_8_FINAL_DESIGN_PARITY.md). No phase-complete or 99% claim; Phase 9 remains NOT STARTED.


## Final parity verification — 2026-10-15

DEC-377–383 locally verified; final user visual approval remains pending. 435 matched-state/supplemental PNGs across the five requested viewports; actual captures have zero page errors, console warnings or horizontal overflow. Serious/critical axe findings are zero on audited home/incident and browser-gate core surfaces. Static gate passed; unit gate 158 Python + 1 Express passed; final isolated browser gate 25 passed plus real scheduler/expiry/idempotency checks. Delivered Docker source/package/public asset hashes match all 62 checked files. Minor caption wrapping differences remain documented; no numerical fidelity claim. See [final report](PHASE_REPORTS/PHASE_8_FINAL_DESIGN_PARITY.md), source matrix and animation matrix. Phase 9 remains NOT STARTED.

## Phase 8.5 — Work Package 1: Security and Tenant Isolation Complete Locally — 2026-10-15

Addressed audit findings AUD-001 (Alertmanager Webhook Multi-Tenant Isolation) and AUD-002 (Connector URL SSRF & DNS Rebinding Hardening) under governing decisions DEC-390 and DEC-391:
- **AUD-001 Webhook Tenant-to-Service Isolation (DEC-390):**
  - Removed insecure first-organization fallback and automatic service creation from untrusted incoming alert payloads in `resolve_webhook_target_service`.
  - Enforced authenticated tenant-to-service mapping: incoming Alertmanager webhooks must explicitly specify a verified target organization via URL path (`/api/v1/webhooks/alertmanager/{target_org}`), query param (`?organization=` or `?organization_id=`), header (`X-Organization` or `X-Organization-Id`), or alert labels. Missing target org returns HTTP 400; non-existent org returns HTTP 404; identifier mismatch returns HTTP 400.
  - Required target service to be pre-registered under the resolved organization; unregistered services return HTTP 404 without database row creation.
  - Implemented dual-layer webhook authentication: supports platform-wide `ALERTMANAGER_SECRET` and per-tenant deterministic secret `compute_tenant_webhook_secret(org_id)` derived via HMAC-SHA256 from the master secret. Cross-tenant alert spoofing (Token A used to inject alerts targeting Tenant B) returns HTTP 401 Unauthorized.
  - Fully preserved deterministic alert deduplication and correlation engines (`correlate_alert`).
- **AUD-002 SSRF, DNS Resolution, and Redirect Hardening (DEC-391):**
  - Hardened `validate_connector_url` with pre-flight DNS resolution using `socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)`. All resolved IPv4 and IPv6 addresses are validated against loopback, RFC 1918 private subnets, link-local, carrier-grade NAT (`100.64.0.0/10`), multicast, unspecified, reserved, and cloud metadata endpoints (`169.254.169.254`, `169.254.170.2`, `100.100.100.200`, `fd00:ec2::254`, `metadata.google.internal`), including IPv4-mapped IPv6 and 6to4 addresses.
  - Implemented `SSRFSafeRedirectHandler` (subclassing `urllib.request.HTTPRedirectHandler`) to re-validate every redirect hop against SSRF rules, prohibit protocol downgrade (HTTPS -> HTTP), and enforce a hard ceiling of 3 redirect hops.
  - Implemented `SSRFSafeHTTPConnection` and `SSRFSafeHTTPSConnection` which verify the connected socket's peer IP (`sock.getpeername()[0]`) at TCP connect time, eliminating DNS rebinding (TOCTOU).
  - Hardened `/api/v1/services/{id}/verify-connection` endpoint to return HTTP 400 Bad Request with `"SSRF Protection: ..."` for SSRF violations.
- **Verification Evidence:**
  - `uv run pytest apps/api/tests/test_webhooks_and_incidents.py apps/api/tests/test_auth_rbac_tracing.py apps/api/tests/test_incident_lifecycle_correlation.py`: Exit 0 (29 passed, 0 failed).
  - Full test suite `uv run pytest`: Exit 0 (165 passed, 6 skipped, 132 warnings in 13.61s; +6 new security regression tests over 159 baseline).
  - Static type check `uv run mypy apps/api/app/auth.py apps/api/app/main.py`: Exit 0 (Success: no issues found in 2 source files).
  - Linter check `uv run ruff check apps/api/app apps/api/tests`: Exit 0 (All checks passed!).
  - Format check `uv run ruff format --check apps/api/app apps/api/tests`: Exit 0.
  - Work remains uncommitted on `feat/phase8-frontend-integration`; no push or deployment performed.

## Phase 8.5 — Complete Functional Integration Complete Locally — 2026-10-15

Completed all work packages (WP1 through WP6), resolving audit findings AUD-001 through AUD-018:
- **WP1: Security & Multi-Tenant Isolation (AUD-001, AUD-002, DEC-390, DEC-391):**
  - Removed first-organization webhook fallback and untrusted automatic service creation. Enforced strict tenant-to-service mapping and HMAC-SHA256 authenticated webhook tokens.
  - Hardened connector URL verification with pre-flight DNS resolution, IPv4/IPv6 private IP filtering, cloud metadata blocking, redirect validation, and TCP socket peer IP verification against DNS rebinding.
- **WP2: Persistent Application Connection Management (AUD-003, AUD-004, AUD-010, DEC-392):**
  - Database schema migration `0010_service_connection_and_monitoring.py` persisting healthcheck URLs, verification timestamps, probe latencies, HTTP codes, and monitoring intervals. Added `service_health_observations` audit table.
  - Frontend `ServiceSettings` component with inline connection testing, observation history, and configuration updates. Dynamic `<HealthStatus>` replacing hardcoded "Monitoring unknown".
- **WP3: Continuous Monitoring & Observability (AUD-005, AUD-007, AUD-008, DEC-393):**
  - Celery Beat scheduled periodic probing (`aegisops.probe_monitored_services`) with bounded timeouts and SSRF defenses.
  - Cold-start and transient glitch dampening: degraded state transitions for transient failures; 3 consecutive failure threshold qualifications before incident creation.
  - Deterministic incident creation with SHA-256 fingerprint deduplication and auto-recovery transition to resolved when service recovers.
  - Prometheus file service discovery (`targets.yml`) and instrumentation documentation in `docs/EXTERNAL_APPLICATION_INSTRUMENTATION.md`.
- **WP4: Google ADK & Real AI Investigations (AUD-006, AUD-009, AUD-013, AUD-014, DEC-394):**
  - Dynamic tool scoping to authenticated incident service (removed hardcoded `shop-api` and `/checkout` bias).
  - Loki queries scoped to authorized service; Tempo trace spans verified against service name (`UNAUTHORIZED_SERVICE_TRACE`).
  - Deployment repo resolved from service metadata; honest `uninstrumented: True` when unconfigured.
  - Sensitive data redaction extended for MongoDB/SQL URIs with credentials, JWT tokens, session cookies, and SSNs.
  - Production remediation proposals strictly prohibited; staging-only allowlisted execution preserved.
- **WP5: Functional Analytics & Application UX (AUD-011, AUD-012, AUD-016, AUD-017, DEC-395):**
  - Tenant-safe performance metrics API (`GET /api/v1/services/{id}/metrics`) querying Prometheus with sanitized PromQL templates and bounded windows.
  - `ServiceAnalytics` connected to real metrics API, rendering live SVG charts or honest uninstrumented states without mock data.
  - Multi-organization workspace switching in `app-shell.tsx` with header forwarding. Dynamic overview counts replacing static placeholders.
- **WP6: End-to-End Tests, Documentation, and Cleanup (AUD-015, AUD-018, DEC-396):**
  - Comprehensive unit, integration, contract, and agent isolation test suites.
  - Full repo verification: `make check` (Ruff, mypy, ESLint, Prettier, dual workspace TypeScript) passed with 0 errors. Python test suite: 177 passed, 6 skipped in 19.17s. Next.js production build: 13/13 static pages generated in 3.4s.
  - All 18 audit findings (AUD-001 through AUD-018) fully resolved and documented in `docs/PHASE_8_5_COMPLETION.md`.

## Phase 8.5 — Acceptance Audit Conditions Resolved Locally — 2026-10-16

Astra completed an independent acceptance audit and issued **APPROVED WITH CONDITIONS**. All 6 required conditions have been resolved, backed by empirical regression tests, static checks, and full containerized E2E validation:

### Acceptance Conditions Resolved
1. **Python Syntax Error Investigation & Parenthesization (Condition 1):**
   - Investigated `apps/api/app/main.py:1185` and `scripts/verify_browser_gate.py:95`.
   - Identified root cause: `pyproject.toml` configures `target-version = "py314"`. Under Python 3.14 / Ruff 0.17.0 grammar, unparenthesized exception tuples are accepted by CPython 3.14's PEG parser and preferred by Ruff's `py314` single-line formatter. However, PEP 8 and Python <= 3.13 flag unparenthesized tuples as invalid syntax mimicking Python 2 syntax.
   - Formatted the exception clauses with multi-line parenthesized tuples and trailing commas. Both files verified clean via `python -m py_compile`.
2. **Removal of Unsafe Unscoped PromQL Fallback (Condition 2, DEC-397):**
   - Completely eliminated the fallback `or http_requests_total{service="shop-api"}` from `apps/api/app/telemetry/promql.py`. All telemetry queries now require `service_id` or `(service, organization_id)`.
   - In `infra/prometheus/prometheus.yml`, configured the `shop-api` scrape job with static trusted labels `service_id="00000000-0000-0000-0000-000000000066"` and `organization_id="00000000-0000-0000-0000-000000000064"`, matching `get_or_create_demo_scope`.
   - Added regression test `test_no_unscoped_promql_fallback_for_demo_shop_api` in `apps/api/tests/test_service_metrics.py`.
3. **Migration 0011 Preflight & Read-Only Detection Query (Condition 3, DEC-400):**
   - Added comprehensive preflight documentation and read-only SQL check to `apps/api/alembic/versions/0011_active_incident_fingerprint_unique.py` and `docs/MIGRATION_0011_PREFLIGHT.md`.
   - Query detects duplicate active episodes before applying the partial unique index.
   - Runbook provides safe human-governed remediation to `resolved` status with audit trail notes without destructive deletion of operational incident data.
4. **Independent Browser E2E Gate Execution (Condition 4):**
   - Executed `make browser` (`python scripts/verify_browser_gate.py`).
   - Result: Exit code 0, 27/27 Playwright tests passed in 1.2m across desktop and mobile viewports.
   - Watchdog assertions passed: Celery Beat schedule file in `/tmp` as UID 10001, isolated Compose project `aegisops-browser-08d60dc4` cleanly torn down. Evidence recorded at `artifacts/aegisops-browser-08d60dc4`.
5. **Mixed-Service Trace Provenance & Span-Level Isolation (Condition 5, DEC-398):**
   - In `apps/api/app/telemetry/tempo.py`, merged resource attributes (`res_attrs`) directly into `span_attrs` so individual spans retain `organization_id` and `service_id` provenance tags.
   - In `apps/api/app/main.py`, `get_trace` filters spans in mixed-service traces, stripping foreign microservice/tenant spans and failing closed with 404 if no authorized spans remain. Returns a sanitized `TraceSummaryRead`.
   - In `agents/incident_investigator/tools/gateway.py`, `get_trace_summary` filters spans to authorized tenant provenance and persists only authorized spans into evidence items.
   - Added regression tests in `apps/api/tests/test_auth_rbac_tracing.py` and `agents/incident_investigator/tests/test_service_evidence_isolation.py`.
6. **Worker Concurrency Controls & Locking Architecture (Condition 6, DEC-402):**
   - In `apps/worker/tasks.py`, wrapped `db.flush()` on incident creation in `try...except (IntegrityError, DBAPIError)`. If a concurrent worker task or manual recheck wins the race against the PostgreSQL partial unique index, the second worker catches the conflict, rolls back the failed flush, retrieves the newly committed incident record, and appends the failure telemetry to the existing incident timeline instead of crashing.
   - Documented distributed locking requirements (`SELECT FOR UPDATE` or Redis mutex `lock:probe:{service_id}`) for high-concurrency scaling in `docs/ENGINEERING_DECISIONS.md`.

### Current Verification Status
- `make check`: PASS (Ruff check/format clean across 88 files, mypy 49 files clean, ESLint clean, Prettier clean, TypeScript clean across `@aegisops/web` and `@aegisops/shop-api`).
- Pytest: 185 passed, 6 skipped, 132 warnings in 13.31s (`uv run pytest apps/api/tests agents/incident_investigator/tests -q`).
- Express Tests: 1 passed in 598ms (`npm test`).
- PostgreSQL Integration Tests: 5 passed, 1 skipped, 179 deselected in 20.70s (`make integration`).
- Browser E2E Gate: 27 passed, 0 failed in 1.2m (`make browser`, exit code 0).
- Next.js Production Build: 13/13 static pages compiled in 2.2s with 0 errors (`npm --prefix apps/web run build`).
- **Phase 8.5 status:** REPAIRED LOCALLY, NOT CLAIMED FULLY VERIFIED. Returned for final independent acceptance audit by Astra.


