# AegisOps

**AI-powered incident intelligence and response platform.**

AegisOps detects application incidents using production-grade observability infrastructure (OpenTelemetry, Prometheus, Alertmanager, Loki), ingests authenticated alerts idempotently into a FastAPI/PostgreSQL control plane, presents an audit-ready Next.js incident feed, and investigates incidents through scoped, evidence-grounded **Google ADK** AI agents.

> **Status:** **Phase 6 Verified.** PostgreSQL transactional outbox pattern, Celery outbox delivery worker with `FOR UPDATE SKIP LOCKED` leasing and jittered exponential backoff, HMAC-SHA256 signed event envelopes with 300s replay bounds, self-hosted n8n operator automation workflows (`incident-created`, `incident-investigated`, `approval-requested`, `incident-resolved`), human-governed remediation proposals with canonical SHA-256 parameter hashing, RBAC gating (`admin`/`owner` only), lazy and periodic expiry, Next.js Proposals & Deliveries UI (`/app/proposals`), and complete Phase 6 verification suite (20/20 unit/integration/security tests passing) are implemented and verified. Phase 7 (Remediation Execution & Staging Safety Sandbox) is unlocked and ready.

---

## Architecture (Core Telemetry, Investigation, Outbox & Remediation Proposals)

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
    |                                                (Incidents, Outbox, Proposals)
    |                                                     |
    |                                              Next.js Dashboard
    |                                              (/app/incidents, /app/runbooks, /app/proposals)
    |
    |-- Structured JSON logs (with redaction)
              |
        OTel Collector Contrib 0.120.0
              |
         Loki 3.4.2 (TSDB storage)

Transactional Outbox Pipeline
    |
    PostgreSQL outbox_events (Atomic with incident / proposal state changes)
    |
    Celery Outbox Dispatcher (FOR UPDATE SKIP LOCKED, lease timeout, exponential backoff)
    |-- HMAC-SHA256 Signed Envelope (X-AegisOps-Signature, 300s replay window)
          |
    n8n Operator Workflows (Community 1.82.2, internal webhooks)
          |
    Notification Sink (Slack / Discord / Webhook Demo Sink)

Remediation Governance (Zero-Execution Invariant in Phase 6)
    |
    ADK Investigation Result ---> Action Catalog Validation (Allowed IDs & Typed Schemas)
                                  |
                                  +--> Immutable Action Proposal (Canonical SHA-256 Hash)
                                        |
                                        +--> Authorized Human Review (Admin / Owner RBAC)
                                              |-- Approve / Reject / Lazy Expiry
                                              |-- Zero Execution in Phase 6 (execute_action raises NotImplementedError)
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
- Proposals & Outbox Deliveries: `http://localhost:3000/app/proposals`

### 3. Run Automated End-to-End Pipeline Verifications
Execute the Phase 1 automated system verification script:
```bash
.tools/bin/uv run --frozen --all-groups python scripts/verify_phase1_e2e.py
```

Execute the Phase 5 RAG and Investigation E2E demonstration script:
```bash
uv run --frozen --all-groups python scripts/verify_phase5_rag_e2e.py
```

Execute the Phase 6 Outbox, n8n, and Human Approval E2E verification script:
```bash
uv run --frozen --all-groups python scripts/verify_phase6_outbox_n8n_e2e.py
```

### 4. Running Tests
```bash
# Code linters, formatting, and strict type-checking
make check

# Backend and unit tests (Python pytest & Node.js test runner)
make test

# Phase 6 Outbox and Proposals comprehensive test suite (20 tests)
uv run --frozen --all-groups pytest -v apps/api/tests/test_phase6_outbox_and_proposals.py

# Run RAG quantitative retrieval evaluation benchmark (32 queries across 5 runbooks)
uv run --frozen --all-groups python evaluations/rag/evaluate.py

# Alertmanager rule promtool tests
docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability exec prometheus promtool test rules /etc/prometheus/rules/test_api_alerts.yml

# Isolated release gate: real backend + seeded browser tests + Beat/worker fault cleanup
# Requires Docker Compose with !override support and installed project/browser dependencies.
make browser

# Isolated PostgreSQL migration round-trip & DB constraints test
docker compose -p aegisops-verify -f docker-compose.yml -f docker-compose.verify.yml --profile verify run --rm verify
docker compose -p aegisops-verify -f docker-compose.yml -f docker-compose.verify.yml --profile verify down -v
```

The browser gate creates a fresh Compose project and verification database, applies migrations,
seeds synthetic users/incidents, and builds the production frontend with an allocated loopback API
port. It never reuses the development stack or its `.env`. Ordinary password login and CSRF checks
remain enabled. Beat and the worker reset a real isolated demo fault after a fixture-only shortened
expiry; production TTLs are unchanged. Browser coverage proves persisted **offline** investigation
creation and a visible HTTP 403 failure, not live model accuracy or the complete telemetry pipeline.
The gate removes its containers, volumes and image tags on exit. Runtime evidence is saved under
`artifacts/aegisops-browser-*/`. Run frontend build/typecheck commands sequentially: they share `.next`.
`npm run test:web` is the inner command and requires the environment provisioned by `make browser`.

---

## Project Documentation
- [`AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md`](AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md): Approved master architecture, phase gates, and roadmaps.
- [`AGENTS.md`](AGENTS.md): Operational instructions and security rules for coding agents.
- [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md): Current phase status, verified deliverables, and upcoming milestones.
- [`docs/ENGINEERING_DECISIONS.md`](docs/ENGINEERING_DECISIONS.md): Granular decision log with 10-point interview-defensible explanations (`DEC-001` through `DEC-315`).
- [`docs/ADR/`](docs/ADR/): Architecture Decision Records (`ADR-001` through `ADR-026`).
- [`docs/PHASE_REPORTS/`](docs/PHASE_REPORTS/): Verification reports and empirical benchmark artifacts (Phases 0–6).
- [`automations/n8n/README.md`](automations/n8n/README.md): n8n Community integration guide, webhook security, and operator workflows.
