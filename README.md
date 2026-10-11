# AegisOps

**AI-powered incident intelligence and response platform.**

AegisOps detects application incidents using production-grade observability infrastructure (OpenTelemetry, Prometheus, Alertmanager, Loki), ingests authenticated alerts idempotently into a FastAPI/PostgreSQL control plane, presents an audit-ready Next.js incident feed, and investigates incidents through scoped, evidence-grounded **Google ADK** AI agents.

> **Status:** **Phase 4 Verified.** Auditable 6-state incident lifecycle machine, deterministic multi-alert correlation, scoped read-only GitHub integration, deployment-aware Google ADK investigations, citation validation, Next.js interactive incident timeline, and full observability pipeline are implemented and verified locally and in hosted GitHub Actions CI ([Run 38146836542](https://github.com/Tarun-sde/AegisOps/actions/runs/38146836542), all green). Phase 5 (Runbook RAG & pgvector knowledge subsystem) is unlocked and ready.

---

## Architecture (Core Telemetry & Investigation Data Path)

```
Express/TypeScript (shop-api)
    |
    |-- /metrics (prom-client RED metrics) --------> Prometheus 3.3.0
    |                                                     |
    |                                               Alert rules (HighApiErrorRate)
    |                                                     |
    |                                                Alertmanager 0.28.1
    |                                                     |
    |                                            Bearer-auth webhook
    |                                                     |
    |                                              FastAPI Control Plane
    |                                                     |
    |                                                PostgreSQL 18
    |                                                     |
    |                                              Next.js Dashboard
    |
    |-- Structured JSON logs (with redaction)
              |
        OTel Collector Contrib 0.120.0
              |
         Loki 3.4.2 (TSDB storage)
```

---

## Quickstart & Local Verification

### 1. Prerequisites
- Python 3.14+ with `uv` (`.tools/bin/uv` or system `uv`)
- Node.js 22+ with `npm`
- Docker & Docker Compose v2

### 2. Start the Full Observability & Application Stack
```bash
# Launch core app services + observability pipeline (Prometheus, Loki, Alertmanager, OTel Collector)
docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile core --profile lab --profile observability up -d --wait
# (or if make is installed: make obs-up)
```

Verify service health:
- FastAPI Control Plane: `http://localhost:8000/healthz` (readyz probe at `/readyz`)
- Shop API (Sample App): `http://localhost:3001/healthz` (metrics at `/metrics`)
- Prometheus Web UI: `http://localhost:9090`
- Alertmanager UI: `http://localhost:9093`
- Next.js Web Dashboard: `http://localhost:3000/app/incidents`

### 3. Run the Automated End-to-End Pipeline Verification
Execute the 19-step automated system verification script:
```bash
.tools/bin/uv run --frozen --all-groups python scripts/verify_phase1_e2e.py
# (or if make is installed: make verify-e2e)
```
This script exercises:
1. Service health checks across all components
2. Normal traffic generation (12 requests, 0 alerts)
3. Controlled fault injection (`S01_CHECKOUT_500`) via secured demo endpoint
4. Generation of 35 failing checkout requests (HTTP 500)
5. Prometheus RED metric scrape confirmation (`http_requests_total{status_code="500"}`)
6. Loki log query verification with sensitive token redaction
7. Prometheus alert rule evaluation (`HighApiErrorRate` firing)
8. Authenticated Alertmanager webhook delivery to FastAPI
9. PostgreSQL incident persistence and partial unique index deduplication
10. Web dashboard SSR rendering
11. Duplicate delivery rejection (`duplicates_skipped == 1`)
12. Fault deactivation, recovery traffic, and automated incident resolution

### 4. Running Tests
```bash
# Code linters, formatting, and strict type-checking
.tools/bin/uv run --frozen --all-groups ruff check apps agents scripts
.tools/bin/uv run --frozen --all-groups ruff format --check apps agents scripts
.tools/bin/uv run --frozen --all-groups mypy apps/api/app agents/incident_investigator/spike.py agents/incident_investigator/free_tier.py agents/incident_investigator/groq_adapter.py scripts/verify_phase1_e2e.py
npm run lint && npm run format:check && npm run typecheck

# Backend and unit tests (Python pytest & Node.js test runner)
.tools/bin/uv run --frozen --all-groups pytest -v -m 'not integration'
npm test

# Alertmanager rule promtool tests
docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability exec prometheus promtool test rules /etc/prometheus/rules/test_api_alerts.yml

# Playwright browser tests
PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright npm run test:web

# Isolated PostgreSQL migration round-trip & DB constraints test
docker compose -p aegisops-verify -f docker-compose.yml -f docker-compose.verify.yml --profile verify run --rm verify
docker compose -p aegisops-verify -f docker-compose.yml -f docker-compose.verify.yml --profile verify down -v
```

---

## Project Documentation
- [`AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md`](AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md): Approved master architecture, phase gates, and roadmaps.
- [`AGENTS.md`](AGENTS.md): Operational instructions and security rules for coding agents.
- [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md): Current phase status, verified deliverables, and upcoming milestones.
- [`docs/ENGINEERING_DECISIONS.md`](docs/ENGINEERING_DECISIONS.md): Granular decision log with 10-point interview-defensible explanations (`DEC-001` through `DEC-282`).
- [`docs/ADR/`](docs/ADR/): Architecture Decision Records (`ADR-001` through `ADR-024`).
- [`docs/PHASE_REPORTS/`](docs/PHASE_REPORTS/): Verification reports and empirical benchmark artifacts.
