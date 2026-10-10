# ADR-021: Real Telemetry Pipeline, Alertmanager Webhook Ingestion, and Deduplicated Incident Persistence

- **Status:** ACCEPTED — VERIFIED
- **Date:** 2026-10-10
- **Governing rules:** `docs/AGENTS_DECISION_LOG_RULES.md`, `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md` Phase 1.
- **Related decisions:** ADR-004, ADR-006, ADR-007, ADR-013, DEC-241–DEC-250.

## Context and Problem Statement

Phase 0 established domain contracts, deterministic evidence validation, and an ADK investigation spike against synthetic fixtures. However, an operational observability platform requires a real end-to-end signal pipeline:
1. Genuine application telemetry (HTTP RED metrics and structured logs).
2. Continuous metrics scraping and log ingestion.
3. Deterministic alert evaluation with volume guards and divide-by-zero protection.
4. Secure webhook delivery from Alertmanager to the FastAPI control plane.
5. Concurrency-safe, deduplicated incident persistence in PostgreSQL without duplicate incident creation.
6. A responsive, accessible Next.js dashboard presenting real operational data.

## Decision

1. **Instrumentation & Telemetry Export:**
   - Instrument `examples/shop-api` with `prom-client` exposing Prometheus RED metrics (`http_requests_total`, `http_request_duration_seconds`) with bounded labels (`method`, `route`, `status_code`).
   - Format structured JSON logs with diagnostic fields (`request_id`, `route`, `status_code`, `duration_ms`, `error_category`) and pre-export redaction of credentials/tokens.
   - Forward logs asynchronously via standard OTLP/HTTP JSON (`POST /v1/logs`) using Node 22 native `fetch` to OpenTelemetry Collector, which batches and routes to Grafana Loki.
2. **Alerting Pipeline:**
   - Prometheus v3.2.1 scrapes `shop-api:3001/metrics` every 5s.
   - Alert rule `HighApiErrorRate` computes the 5xx ratio over 1m with a strict request volume guard (`> 0.05 req/s`) and 15s evaluation window, tested via `promtool`.
   - Alertmanager v0.28.1 groups alerts by `(alertname, service)` and delivers authenticated webhooks with `Authorization: Bearer <secret>`.
3. **Control Plane Ingestion & Deduplication:**
   - FastAPI endpoint `POST /api/v1/webhooks/alertmanager` verifies Bearer credentials with `hmac.compare_digest` and enforces payload size limits (512KB).
   - Ingested alerts are recorded in `alert_events`.
   - Active episode deduplication is enforced by PostgreSQL transactional checks (`SELECT ... WHERE status = 'open' FOR UPDATE`) and a database-level partial unique index `uq_open_incident_fingerprint` on `(organization_id, service_id, fingerprint) WHERE status = 'open'`.
   - Duplicate firing webhooks append timeline events (`alert_firing_duplicate`) and update `updated_at`, without creating duplicate incidents.
   - Resolved webhooks transition incidents to `resolved` and record resolution timestamps. Subsequent firing alerts create a new incident episode.
4. **Minimal Frontend Integration:**
   - Next.js dashboard routes `/app/incidents` and `/app/incidents/[incidentId]` consume typed API responses with loading, empty, and error states.

## Alternatives Considered and Rejected

1. **Direct Application-to-PostgreSQL Logging:** Rejected. Duplicating raw application logs into PostgreSQL creates write amplification, wastes disk space, and violates single-responsibility boundaries. Raw telemetry belongs in Loki.
2. **Application-Level Deduplication Without DB Constraints:** Rejected. Under concurrent webhook delivery, race conditions can cause duplicate incidents without database-enforced unique constraints.
3. **Synthetic / Mocked Webhook Tests as Sole Verification:** Rejected. Phase 1 acceptance strictly requires an actual system-level chain: fault injection -> metrics -> Prometheus alert -> Alertmanager webhook -> PostgreSQL incident -> Next.js dashboard.

## Verification Evidence

- Full end-to-end chain verified via `scripts/verify_phase1_e2e.py`:
  - 35 consecutive 500 errors induced in `shop-api`.
  - Prometheus detected elevated error rate and evaluated `HighApiErrorRate` alert as firing.
  - Alertmanager delivered authenticated webhook to FastAPI.
  - Incident persisted in PostgreSQL and displayed on Next.js UI.
  - Duplicate webhook delivery returned `duplicates_skipped == 1`, with 0 new incidents created.
  - Traffic recovery resolved the alert and closed the incident.
- Unit and integration tests: 63 pytest tests passing, shop-api comprehensive test passing, promtool alert rule tests passing, Playwright browser tests passing.
