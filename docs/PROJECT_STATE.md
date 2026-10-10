# AegisOps — Current Project State

**Updated:** 2026-10-10  
**Current phase:** Phase 1 (Real Telemetry Vertical Slice)  
**Overall state:** `PHASE 1 COMPLETE — REAL TELEMETRY, ALERTING, INGESTION, AND UI VERIFIED; PHASE 2 LOCKED PENDING AUTHORIZATION`  
**Source:** `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md` Section 19; `docs/PHASE_REPORTS/PHASE_1_VERIFICATION.md`; `docs/ADR/ADR-021-real-telemetry-pipeline.md`.

---

## Implemented and verified in Phase 1

- [x] **Sample Commerce Application (`examples/shop-api`):**
  - Node.js 22.23.1 / TypeScript / Express 5.3.0.
  - Endpoints: `GET /healthz`, `GET /products` (deterministic catalog), `POST /checkout` (validation + simulated order IDs), `GET /metrics` (Prometheus-compatible RED metrics).
  - RED metrics instrumented via `prom-client` 15.1.3: `http_requests_total` counter and `http_request_duration_seconds` histogram with bounded labels (`method`, `route`, `status_code`).
  - Structured JSON logging with pre-export sensitive field redaction (Bearer tokens, cookies, passwords, API keys).
  - Native Node 22 `fetch` OTLP/HTTP JSON log forwarder (`POST /v1/logs`) to OpenTelemetry Collector.
  - Demo fault injection: `POST /fault/inject` and `POST /fault/reset` implementing scenario `S01_CHECKOUT_500` (isolated to demo/test via `NODE_ENV !== "production"` and `x-demo-fault-secret`).
  - Automated Node test suite passing: `examples/shop-api/tests/shop_api.test.mjs` (all 10 assertions verified).
- [x] **Observability Infrastructure (`infra/`):**
  - Pinned Docker images: Prometheus 3.3.0 (`prom/prometheus@sha256:...`), Loki 3.4.2 (`grafana/loki@sha256:...`), Alertmanager 0.28.1 (`prom/alertmanager@sha256:...`), OpenTelemetry Collector Contrib 0.120.0 (`otel/opentelemetry-collector-contrib@sha256:...`).
  - Bounded memory limits configured across stack (~242.7 MiB total resident RAM footprint across all 9 containers).
  - OTel Collector receives OTLP HTTP logs on port 4318, applies memory limiter & batch processors, exports to Loki.
  - Prometheus scrapes `shop-api:3001/metrics` every 5 seconds.
  - Loki stores logs locally in filesystem TSDB format with bounded retention.
  - Alertmanager routes firing/resolved alerts to AegisOps FastAPI with Bearer token authentication.
- [x] **Real Alert Rules & Promtool Testing (`infra/prometheus/rules/`):**
  - `HighApiErrorRate` rule: fires when 5xx error ratio > 20% over 1m window with minimum request volume guard (`sum(rate(http_requests_total[1m])) > 0.05`) and 15s evaluation duration.
  - Automated promtool test suite (`infra/prometheus/rules/test_api_alerts.yml`): verified 4 scenarios (healthy traffic, volume guard, sustained 500 ratio firing, resolution).
- [x] **Database Migrations & Models (`apps/api/`):**
  - Alembic migration `0002_telemetry_incidents.py`: creates `alert_events`, `incidents`, `incident_events` tables.
  - Partial unique index `uq_open_incident_fingerprint` on `incidents (organization_id, service_id, fingerprint) WHERE status = 'open'`: enforces DB-level duplicate protection per active alert episode.
  - SQLAlchemy models and Pydantic v2 schemas for Alertmanager webhook payload, incident entities, and timeline events.
- [x] **FastAPI Ingestion & Incident API (`apps/api/`):**
  - Webhook receiver: `POST /api/v1/webhooks/alertmanager` with timing-safe `hmac.compare_digest` Bearer token authentication, 512KB payload size limit, Pydantic schema validation, and safe service resolution.
  - Deterministic deduplication: skips duplicate webhook deliveries without double-counting; transitions to `resolved` on Alertmanager resolved delivery.
  - Incident queries: `GET /api/v1/incidents` (paginated, filtered by status/severity), `GET /api/v1/incidents/{incident_id}` (detail with 404 validation), `GET /api/v1/incidents/{incident_id}/events` (chronological audit timeline).
- [x] **Next.js Incident Dashboard (`apps/web/`):**
  - Incident feed route `/app/incidents`: renders real PostgreSQL incident data with status/severity badges, relative timestamps, and accessible loading/empty/error states.
  - Incident detail route `/app/incidents/[incidentId]`: displays incident metadata, audit event timeline, and explicit notice that AI-driven investigation is locked pending Phase 2.
  - Playwright browser tests passing (2/2 in 1.9s).
- [x] **End-to-End System Demonstration (`scripts/verify_phase1_e2e.py`):**
  - Full automated 19-step verification executed and passed against running Docker stack:
    1. Service health checks (API, Shop, Prom, Alertmanager, Loki)
    2. Prometheus target scrape confirmed (`shop-api` UP)
    3. Normal traffic (12 requests, 0 alerts)
    4. Fault injection (`S01_CHECKOUT_500` enabled)
    5. Fault traffic (35 failing requests, HTTP 500)
    6. Prometheus error counter incremented (`http_requests_total` = 140.0)
    7. Loki error logs queried successfully
    8. Prometheus alert evaluated as firing
    9. Alertmanager delivered authenticated webhook
    10. FastAPI created incident in PostgreSQL
    11. Web dashboard SSR rendered incident feed
    12. Duplicate webhook delivery skipped (`duplicates_skipped == 1`, DB count unchanged)
    13. Fault reset & recovery traffic sent
    14. Incident resolved in database

---

## Implemented and verified in Phase 0 (Baseline Preserved)

- [x] Repository toolchain and dependency locks (Python 3.14.7, uv 0.13.0, Node.js 22.23.1, npm 10.9.8).
- [x] Core domain contracts and deterministic citation validation engine (`validate_evidence`).
- [x] FastAPI control plane baseline (`/healthz`, `/readyz`).
- [x] PostgreSQL 18 with `pgvector` 0.8.7 and Redis 8.10.2 container foundation.
- [x] Frontend dashboard shell with dark console styling and accessible navigation.
- [x] Google ADK 2.11.0 spike with read-only tools and citation-grounded outputs.
- [x] Live Gemini 3.5 Flash and Groq `gpt-oss-120b` verification on confirmed Free tier.

---

## Untested / Blocked / Deferred (Strict Phase Boundaries)

**Developer authorization gate:** Phase 1 is COMPLETE. Phase 2 remains **LOCKED** until developer explicitly authorizes Phase 2 commencement.

- [ ] **Automated AI Investigation Workflow with Google ADK:** `DEFERRED TO PHASE 2`.
  - Connecting live incidents to background Google ADK agent runs via Celery/Redis.
- [ ] **Full product auth/RBAC and multi-tenant sessions:** `DEFERRED TO PHASE 3`.
- [ ] **Tempo distributed trace investigation:** `DEFERRED TO PHASE 3`.
- [ ] **GitHub deployment correlation & cross-fingerprint clustering:** `DEFERRED TO PHASE 4`.
- [ ] **Runbook RAG with pgvector:** `DEFERRED TO PHASE 5`.
- [ ] **n8n internal automations and remediation approvals:** `DEFERRED TO PHASES 6–7`.

---

## Verification Test Summary

| Test Suite | Command | Exit Code | Result |
|---|---|---|---|
| Python Static Checks | `ruff check apps agents scripts && ruff format --check apps agents scripts && mypy apps/api/app ... scripts/verify_phase1_e2e.py` | 0 | PASSED (0 lint errors, 22 formatted, 8 type-checked) |
| Python Unit Tests | `pytest -v -m 'not integration'` | 0 | PASSED (63 passed, 2 deselected) |
| Python Security Audit | `pip-audit --progress-spinner off` | 0 | PASSED (0 known vulnerabilities) |
| Isolated Compose DB Test | `docker compose -p aegisops-verify -f docker-compose.yml -f docker-compose.verify.yml --profile verify run --rm verify` | 0 | PASSED (2 passed: migration round-trip & DB constraints) |
| Promtool Alert Rules | `promtool test rules test_api_alerts.yml` | 0 | PASSED (4 scenarios verified) |
| Shop API Unit Tests | `npm test` | 0 | PASSED (10 assertions verified) |
| Web Lint & Format | `npm run lint && npm run format:check && npm run typecheck` | 0 | PASSED (ESLint, Prettier, TypeScript workspaces clean) |
| Web Browser Smoke | `PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright npm run test:web` | 0 | PASSED (2/2 Playwright tests passed) |
| Web Production Build | `npm run build` | 0 | PASSED (Next.js webpack clean) |
| Phase 1 End-to-End System | `python scripts/verify_phase1_e2e.py` | 0 | PASSED (All 19 acceptance steps verified live) |
