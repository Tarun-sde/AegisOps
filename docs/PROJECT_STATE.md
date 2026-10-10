# AegisOps — Current Project State

**Updated:** 2026-10-10  
**Current phase:** Phase 2 (End-to-End AI Investigation MVP)  
**Overall state:** `PHASE 2 COMPLETE — END-TO-END AI INVESTIGATION MVP (GOOGLE ADK + REAL TELEMETRY) VERIFIED; PHASE 3 READY FOR AUTHORIZATION`  
**Source:** `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md` Phase 2; `docs/PHASE_REPORTS/PHASE_2_VERIFICATION.md`; `docs/ADR/ADR-022-adk-investigation-worker.md`.

---

## Implemented and verified in Phase 2

- [x] **Asynchronous Investigation Worker (`apps/worker/`):**
  - Celery application connected to Redis broker (`redis://redis:6379/0`).
  - Durable background task `investigate_incident_task` orchestrating the investigation lifecycle.
  - Active-run idempotency guard preventing duplicate concurrent investigations on the same incident.
  - Worker container deployed and running healthily in `docker-compose.yml`.
- [x] **Google ADK Single-Agent Runner (`agents/incident_investigator/`):**
  - Google ADK 2.11.0 `Agent`, `Runner.run_async`, and `ToolContext` integration.
  - `OfflineInvestigationModel` inheriting from `google.adk.models.BaseLlm` providing deterministic test responses with $0 cost and zero flaky network dependencies.
  - Transparent support for live Gemini and Groq model providers when API keys are configured.
  - Enforced single-agent topology (no premature multi-agent swarm).
- [x] **Bounded Read-Only Tool Gateway (`agents/incident_investigator/tools/gateway.py`):**
  - Parameterized read-only tools: `get_incident_snapshot`, `query_service_metrics` (Prometheus), and `search_service_logs` (Loki).
  - Hard execution budget capped at 12 calls per investigation; raises `BudgetExceededError` on call 13.
  - Telemetry payload size truncation at 32KB per call.
  - Zero raw SQL, PromQL, LogQL, or shell access permitted to the agent.
- [x] **Sensitive Secret Redaction (`agents/incident_investigator/tools/redaction.py`):**
  - Synchronous pre-export regex filtering replacing Bearer tokens, Basic authorization headers, passwords, connection strings, and private keys with `[REDACTED_SECRET]`.
  - Enforced before tool responses return to the agent or persist into PostgreSQL.
- [x] **Database Migrations & Models (`apps/api/`):**
  - Alembic migration `0003_investigations.py` creating `investigation_runs`, `tool_executions`, `evidence_items`, and `hypotheses` tables.
  - SQLAlchemy ORM models with cascading relationships and foreign key integrity.
  - Evidence records store typed provenance IDs: `ev_alert_{uuid}`, `ev_metric_{uuid}`, `ev_log_{uuid}`.
  - Tool execution audit trail records execution times, parameters, and success status.
- [x] **Deterministic Evidence Citation Validation (`agents/incident_investigator/validator.py`):**
  - Backend function `validate_evidence` cross-references all hypothesis citations against persisted database rows for that specific investigation run.
  - Fabricated or cross-run citations are strictly rejected and automatically downgrade the diagnosis to `INCONCLUSIVE` with an audit error.
- [x] **Honest Inconclusive Diagnosis Protocol:**
  - Emits `diagnosis: INCONCLUSIVE` with low confidence when telemetry is absent or ambiguous, strictly preventing hallucinated root causes.
- [x] **FastAPI Investigation Endpoints (`apps/api/app/main.py`):**
  - `POST /api/v1/incidents/{incident_id}/investigations`: creates run in `queued` state and enqueues Celery task.
  - `GET /api/v1/incidents/{incident_id}/investigations`: lists investigation history for an incident.
  - `GET /api/v1/investigations/{investigation_id}`: returns detailed run metadata, hypotheses, and supporting evidence.
  - `GET /api/v1/investigations/{investigation_id}/events`: returns tool execution audit timeline.
  - `GET /api/v1/investigations/{investigation_id}/evidence`: paginated list of all evidence items collected during the run.
  - `GET /api/v1/evidence/{evidence_id}`: individual evidence item with provenance and raw redacted payload.
  - `POST /api/v1/investigations/{investigation_id}/cancel`: safely transitions active investigation to `cancelled`.
- [x] **Next.js AI Investigation Dashboard (`apps/web/`):**
  - Client component `InvestigationPanel` replacing locked gate on incident detail page `/app/incidents/[incidentId]`.
  - Auto-polls investigation status every 2 seconds during active states.
  - Renders status pills, hypotheses with qualitative confidence badges, supporting evidence chips, inconclusive explanation banner, interactive evidence explorer table, and expandable tool execution audit log.
  - Playwright browser test verifying investigation panel rendering and interaction.
- [x] **Automated End-to-End System Verification (`scripts/verify_phase2_e2e.py`):**
  - 21-step live verification verifying real fault injection -> telemetry scraping -> incident creation -> Celery dispatch -> ADK investigation -> Prometheus & Loki queries -> PostgreSQL evidence persistence -> hypothesis emission -> inconclusive diagnosis -> citation rejection -> tool budget limits -> secret redaction -> UI rendering.

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

**Developer authorization gate:** Phase 2 is COMPLETE. Phase 3 remains **LOCKED** until developer explicitly authorizes Phase 3 commencement.

- [ ] **Distributed Tracing Investigation with Grafana Tempo:** `DEFERRED TO PHASE 3`.
- [ ] **GitHub Deployment / Commit Correlation:** `DEFERRED TO PHASE 3`.
- [ ] **Full Product Auth / RBAC and Multi-Tenant Sessions:** `DEFERRED TO PHASE 3`.
- [ ] **Runbook RAG with pgvector and Lexical Search:** `DEFERRED TO PHASE 4`.
- [ ] **Cross-Incident Fingerprint Clustering & Correlation:** `DEFERRED TO PHASE 4`.
- [ ] **Multi-Agent Specialist Swarm:** `DEFERRED TO PHASE 5`.
- [ ] **Automated Remediation / n8n Internal Workflows:** `DEFERRED TO PHASES 6–7`.

---

## Verification Test Summary

| Test Suite | Command | Exit Code | Result |
|---|---|---|---|
| Python Static Checks | `ruff check apps agents scripts && ruff format --check apps agents scripts && mypy apps/api/app apps/worker agents/incident_investigator` | 0 | PASSED (0 lint errors, all files formatted, 14 source files type-checked clean) |
| Python Unit Tests | `pytest -q -m 'not integration'` | 0 | PASSED (74 passed, 2 deselected in 6.27s) |
| Python Security Audit | `pip-audit --progress-spinner off` | 0 | PASSED (0 known vulnerabilities) |
| Web Lint & Format | `npm --prefix apps/web run lint && npm --prefix apps/web run type-check` | 0 | PASSED (ESLint clean, TypeScript clean) |
| Web Browser E2E Tests | `npm --prefix apps/web test` | 0 | PASSED (3/3 Playwright browser tests passed in 2.7s) |
| Phase 1 Regression E2E | `.venv/bin/python scripts/verify_phase1_e2e.py` | 0 | PASSED (All 19 acceptance steps verified live) |
| Phase 2 End-to-End System | `.venv/bin/python scripts/verify_phase2_e2e.py` | 0 | PASSED (All 21 acceptance steps verified live) |
