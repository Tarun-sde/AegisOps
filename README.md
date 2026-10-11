# AegisOps

**AI-powered incident intelligence and response platform.**

AegisOps detects application incidents using production-grade observability infrastructure (OpenTelemetry, Prometheus, Alertmanager, Loki), ingests authenticated alerts idempotently into a FastAPI/PostgreSQL control plane, presents an audit-ready Next.js incident feed, and investigates incidents through scoped, evidence-grounded **Google ADK** AI agents.

> **Status:** **Phase 5 Verified.** Production-grade multi-tenant Retrieval-Augmented Generation (RAG) knowledge subsystem, pgvector HNSW vector indexing, hybrid search with Reciprocal Rank Fusion (RRF $k=60$), semantic heading-aware chunker, pre-ingestion secret redaction, dual embeddings (Google GenAI text-embedding-004 + offline hash double), auditable document lifecycle, related incidents retrieval, Google ADK evidence grounding, Next.js Runbook management UI (`/app/runbooks`), and 32-query benchmark (Recall@5 = 87.5% passing $\ge 80\%$ gate) are implemented and verified. Phase 6 (Multi-Agent Swarm) is unlocked and ready.

---

## Architecture (Core Telemetry, Investigation & RAG Data Path)

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
    |                                                PostgreSQL 18 + pgvector
    |                                                (Full-Text & HNSW Vector Index)
    |                                                     |
    |                                              Next.js Dashboard
    |                                              (/app/incidents, /app/runbooks)
    |
    |-- Structured JSON logs (with redaction)
              |
        OTel Collector Contrib 0.120.0
              |
         Loki 3.4.2 (TSDB storage)

Google ADK Agent (incident_investigator)
    |
    |-- ReadOnlyToolGateway (Strict Tenant Bounds & Budget Limits)
          |-- retrieve_runbook() ---------> Hybrid RRF (k=60) pgvector Search
          |-- get_related_incidents() ----> Historical Incident Correlation
          |-- query_logs(), query_metrics(), get_trace()
          |-- get_recent_deployments() ---> Read-Only GitHub Client
    |
    |-- Evidence Validator (Enforces Runtime Telemetry Grounding & Rejects Fake IDs)
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
- Runbooks Knowledge Base: `http://localhost:3000/app/runbooks`

### 3. Run the Automated End-to-End Pipeline Verification
Execute the 19-step automated system verification script:
```bash
.tools/bin/uv run --frozen --all-groups python scripts/verify_phase1_e2e.py
# (or if make is installed: make verify-e2e)
```

Execute the Phase 5 RAG and Investigation E2E demonstration script:
```bash
uv run --frozen --all-groups python scripts/verify_phase5_rag_e2e.py
```

### 4. Running Tests
```bash
# Code linters, formatting, and strict type-checking
make check

# Backend and unit tests (Python pytest & Node.js test runner)
make test

# Run RAG quantitative retrieval evaluation benchmark (32 queries across 5 runbooks)
uv run --frozen --all-groups python evaluations/rag/evaluate.py

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
- [`docs/ENGINEERING_DECISIONS.md`](docs/ENGINEERING_DECISIONS.md): Granular decision log with 10-point interview-defensible explanations (`DEC-001` through `DEC-298`).
- [`docs/ADR/`](docs/ADR/): Architecture Decision Records (`ADR-001` through `ADR-025`).
- [`docs/PHASE_REPORTS/`](docs/PHASE_REPORTS/): Verification reports and empirical benchmark artifacts.
- [`docs/PHASE_5_RAG_EVALUATION.md`](docs/PHASE_5_RAG_EVALUATION.md): RAG benchmark methodology, queries, and comparative scores.
