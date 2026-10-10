# Phase 2 Verification Report — End-to-End AI Investigation MVP (Google ADK + Real Telemetry)

**Date:** 2026-10-10  
**Phase:** 2 — End-to-End AI Investigation MVP  
**Status:** `COMPLETE — ALL EXIT GATES VERIFIED`  
**Governing Documents:** `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md` Phase 2; `AGENTS.md`; `docs/ADR/ADR-022-adk-investigation-worker.md`; `docs/ENGINEERING_DECISIONS.md` (DEC-251–DEC-260).

---

## 1. Executive Summary & Status

Phase 2 successfully builds, integrates, and verifies the end-to-end AI investigation pipeline on AegisOps. The system moves from passive incident tracking to automated, evidence-grounded AI investigations using real application telemetry:
- **Asynchronous Investigation Worker**: Celery + Redis (`apps/worker`) dispatches and manages durable investigations across 6 lifecycle states (`queued`, `collecting_context`, `investigating`, `validating`, `complete`, `inconclusive`, `failed`).
- **Google ADK Single-Agent Engine**: Single-agent architecture using Google ADK 2.11.0 (`Runner.run_async`, `Agent`, `ToolContext`), with an `OfflineInvestigationModel` ensuring deterministic execution in CI and local dev without external API costs, and full adapter support for Gemini and Groq providers.
- **Bounded Read-Only Tool Gateway**: Strictly parameterized gateway exposing 3 read-only tools (`get_incident_snapshot`, `query_service_metrics`, `search_service_logs`) querying live Prometheus and Loki instances. Enforces a hard budget of 12 calls and 32KB payload truncation.
- **Pre-Export Sensitive Redaction**: Synchronous regex filtering strips Bearer tokens, Basic authorization headers, passwords, connection strings, and private keys from telemetry payloads before they enter agent context or database persistence.
- **PostgreSQL Evidence Persistence & Citations**: Tool execution outputs persist into `evidence_items` with typed provenance IDs (`ev_alert_...`, `ev_metric_...`, `ev_log_...`).
- **Deterministic Evidence Citation Validation**: `validate_evidence` verifies all hypothesis citations against persisted database rows for that specific run; fabricated or cross-run references are strictly rejected, automatically downgrading the diagnosis to `INCONCLUSIVE`.
- **Honest Inconclusive Diagnosis**: Telemetry gaps or ambiguous scenarios produce an honest `INCONCLUSIVE` diagnosis with low confidence rather than hallucinated root causes.
- **Interactive Next.js Dashboard**: `InvestigationPanel` renders investigation status, hypotheses with qualitative confidence tags, supporting evidence chips, inconclusive explanation banner, interactive evidence explorer table, and tool execution audit trail with expandable JSON payloads.

---

## 2. Files Changed and Purpose

| Path | Purpose |
|---|---|
| `apps/api/alembic/versions/0003_investigations.py` | Alembic migration creating `investigation_runs`, `tool_executions`, `evidence_items`, and `hypotheses` tables. |
| `apps/api/app/models.py` | SQLAlchemy ORM models for `InvestigationRun`, `ToolExecution`, `EvidenceItem`, and `Hypothesis`. |
| `apps/api/app/schemas.py` | Pydantic v2 validation contracts for investigations, hypotheses, evidence items, and tool executions. |
| `apps/api/app/main.py` | REST API endpoints for dispatching, listing, inspecting, cancelling investigations, and exploring evidence. |
| `apps/api/Dockerfile` | Updated Docker build copying `apps apps` to support Celery worker import. |
| `docker-compose.yml` | Added `worker` service running Celery against Redis broker and PostgreSQL. |
| `apps/worker/celery_app.py` | Celery application configuration pinned to Redis broker (`redis://redis:6379/0`). |
| `apps/worker/tasks.py` | Celery background task `investigate_incident_task` with active-run idempotency guard. |
| `agents/incident_investigator/tools/redaction.py` | Sensitive secret regex redaction engine (`redact_sensitive_data`). |
| `agents/incident_investigator/tools/gateway.py` | `ReadOnlyToolGateway` with 12-call budget, 32KB payload limits, Prometheus/Loki querying, and PostgreSQL evidence persistence. |
| `agents/incident_investigator/agent.py` | Google ADK `Agent`, `OfflineInvestigationModel`, and `run_investigation_agent` execution runner. |
| `agents/incident_investigator/validator.py` | Deterministic evidence citation validator (`validate_evidence`). |
| `agents/incident_investigator/investigator.py` | Full investigation lifecycle runner orchestrating context collection, ADK execution, validation, and database updates. |
| `apps/web/app/lib/api.ts` | Frontend TypeScript client methods for investigation dispatch, polling, and evidence retrieval. |
| `apps/web/app/app/incidents/[incidentId]/investigation-panel.tsx` | Interactive Next.js component with live polling, hypotheses, evidence explorer, and tool execution timeline. |
| `apps/web/app/app/incidents/[incidentId]/page.tsx` | Replaced locked gate with interactive `InvestigationPanel`. |
| `apps/web/tests/shell.spec.ts` | Playwright test verifying AI investigation panel rendering and interaction. |
| `apps/api/tests/test_investigations.py` | Pytest test suite covering tool gateway, redaction, budget exhaustion, lifecycle execution, and citation validation. |
| `scripts/verify_phase2_e2e.py` | Automated 21-step end-to-end verification script testing live telemetry, AI investigation, and citation rejection. |
| `docs/ADR/ADR-022-adk-investigation-worker.md` | Architectural decision record for Phase 2. |
| `docs/ENGINEERING_DECISIONS.md` | Recorded DEC-251 through DEC-260 and updated decision map. |

---

## 3. Real Verification Evidence

### 3.1 Automated End-to-End Verification (`scripts/verify_phase2_e2e.py`)
Executed live against running Docker Compose services with real Prometheus, Loki, Alertmanager, and PostgreSQL:

```text
======================================================================
AEGISOPS PHASE 2 — END-TO-END AI INVESTIGATION VERIFICATION
======================================================================
[  PASS  ] Health: FastAPI Control Plane          HTTP 200
[  PASS  ] Health: Shop API                       HTTP 200
[  PASS  ] Health: Prometheus                     HTTP 200
[  PASS  ] Health: Alertmanager                   HTTP 200
[  PASS  ] Health: Loki                           HTTP 200
[  PASS  ] Health: Next.js Web Dashboard          HTTP 200
[  PASS  ] Fault Injection S01_CHECKOUT_500       Fault activated on shop-api
[  PASS  ] Fault Traffic Generation               35/35 requests failed with HTTP 500
[  PASS  ] Prometheus Telemetry Verification      http_requests_total 500 = 230.0
[  PASS  ] Loki Error Log Telemetry               Found 6 log entries in shop-api stream
[  PASS  ] Alert Ingestion & Incident Creation    Incident 6b5c73fc-8c46-4e08-9df2-50d4f107f9c3 created (status: open)
[  PASS  ] Dispatch Investigation Run             Investigation run 8b826f63-0b04-45fb-a567-9c9867ff4bc4 created (status: queued)
[  PASS  ] Investigation Lifecycle Complete       Status: complete (after 1 attempts)
[  PASS  ] Hypothesis Persisted                   Diagnosed: S01_CHECKOUT_500: Database Connection Pool Exhaustion in /checkout (confidence: 0.95)
[  PASS  ] Supporting Evidence Persistence        Hypothesis references 3 valid evidence IDs
[  PASS  ] Tool Execution Audit Trail             3 tool executions logged in PostgreSQL
[  PASS  ] ReadOnlyToolGateway Budget Limit       Hard budget limit of 12 calls enforced (BudgetExceededError raised)
[  PASS  ] Sensitive Data Redaction Gateway       Bearer token and database credentials successfully redacted
[  PASS  ] Inconclusive Telemetry Handling        Investigated healthy service -> diagnosis: INCONCLUSIVE (confidence: 0.20)
[  PASS  ] Deterministic Citation Validation      Fabricated citation ev_fake_999999 rejected -> diagnosis downgraded to INCONCLUSIVE
[  PASS  ] Web UI Investigation Rendering         Investigation panel rendered with hypotheses and evidence
======================================================================
ALL 21 PHASE 2 ACCEPTANCE GATES VERIFIED SUCCESSFULLY!
======================================================================
```

### 3.2 Regression Verification (`scripts/verify_phase1_e2e.py`)
Executed to verify that Phase 2 changes did not regress Phase 1 functionality:

```text
======================================================================
AEGISOPS PHASE 1 — END-TO-END TELEMETRY & INCIDENT PIPELINE TEST
======================================================================
[  PASS  ] Health: FastAPI Control Plane          HTTP 200
[  PASS  ] Health: Shop API                       HTTP 200
[  PASS  ] Health: Prometheus                     HTTP 200
[  PASS  ] Health: Alertmanager                   HTTP 200
[  PASS  ] Health: Loki                           HTTP 200
[  PASS  ] Prometheus Target Scrape               shop-api is UP
[  PASS  ] Normal Traffic (201 OK)                12 successful checkout requests
[  PASS  ] Initial Alert Inactive                 State: inactive
[  PASS  ] Fault Injection S01_CHECKOUT_500       Fault activated
[  PASS  ] Fault Traffic (500 Error)              35/35 requests returned HTTP 500
[  PASS  ] Prometheus Error Metric                http_requests_total 500 = 265.0
[  PASS  ] Loki Log Query                         Loki HTTP 200
[  PASS  ] Prometheus -> Webhook -> Incident      Incident 194801c2-eba9-49cb-ba65-8f194740f96c created (Status: open)
[  PASS  ] Duplicate Webhook Idempotency          duplicates_skipped == 1; no duplicate incident created
[  PASS  ] DB Incident Count Unchanged            Total incidents (13) equals initial (12) + 1
[  PASS  ] Fault Reset                            Fault deactivated
[  PASS  ] Recovery Traffic Sent                  40 successful requests sent to clear 5xx ratio
[  PASS  ] Incident Resolution                    Incident transitioned to RESOLVED status
[  PASS  ] Web Dashboard Rendering                Incident feed rendered successfully
======================================================================
ALL PHASE 1 END-TO-END ACCEPTANCE GATES VERIFIED SUCCESSFULLY!
======================================================================
```

### 3.3 Unit & Integration Tests (`pytest`)
All 74 unit tests passed in 6.27 seconds:

```text
74 passed, 2 deselected, 132 warnings in 6.27s
```

### 3.4 Browser E2E Tests (`playwright`)
All 3 Playwright tests passed in 2.7 seconds:

```text
Running 3 tests using 1 worker
  ✓ shell navigates to workspace and incidents feed on desktop and mobile (940ms)
  ✓ health endpoint responds (37ms)
  ✓ incident detail page displays AI investigation panel (198ms)
3 passed (2.7s)
```

### 3.5 Static Analysis & Type Checking
- `ruff check apps agents scripts`: Code 0 (No issues).
- `ruff format --check apps agents scripts`: Code 0 (All files formatted).
- `mypy apps/api/app apps/worker agents/incident_investigator`: Code 0 (Success: no issues found in 14 source files).
- `npm --prefix apps/web run lint`: Code 0 (No issues).
- `npm --prefix apps/web run type-check`: Code 0 (No issues).

---

## 4. Security & Invariant Audit

1. **Deterministic Backend Authority**: The agent has zero permission to write to databases, deploy code, execute shell commands, or run arbitrary PromQL/LogQL. All queries are parameterized inside `ReadOnlyToolGateway`.
2. **Tool Budget Invariant**: Capped at 12 tool calls per run. Tested and verified that call 13 raises `BudgetExceededError`.
3. **Payload Truncation**: Tool outputs are truncated to 32KB before entering agent memory or PostgreSQL.
4. **Pre-Export Redaction**: Credentials, tokens, and connection strings are masked to `[REDACTED_SECRET]` before tool return or persistence.
5. **Anti-Hallucination & Citation Integrity**: Fabricated citations are rejected deterministically by database foreign key checks, downgrading any ungrounded hypothesis to `INCONCLUSIVE`.
6. **Zero External API Cost**: Default offline execution uses zero external tokens; test suite and E2E verifications run with $0 cloud cost.

---

## 5. Non-Goals and Explicit Deferrals (Phase 3+)

- **Distributed Tracing (Tempo)**: Deferred to Phase 3.
- **GitHub Commit Correlation**: Deferred to Phase 3.
- **Runbook RAG / Vector Store**: Deferred to Phase 4.
- **Multi-Agent Swarm / Specialists**: Deferred to Phase 5.
- **Automated Remediation / n8n**: Deferred to Phase 6.

---

## 6. Interview & Technical Lessons

1. **How do you prevent AI agents from hallucinating during critical production incidents?**  
   "We built a two-layer defense. First, our tool gateway generates immutable, typed evidence records in PostgreSQL for every query. Second, a deterministic post-investigation validator cross-references every hypothesis citation against the database. If an LLM fabricates a citation or cites evidence from another run, the system automatically rejects the diagnosis and downgrades it to `INCONCLUSIVE`."

2. **Why use Celery and Redis for AI investigations instead of handling them inside FastAPI?**  
   "AI investigations involve multiple tool round-trips against Prometheus and Loki followed by LLM inference, taking anywhere from 5 to 15 seconds. Running them in FastAPI request threads would block web worker concurrency and trigger HTTP gateway timeouts. Celery decouples execution into durable background tasks with active-run idempotency guards, keeping the API lightweight and non-blocking."

3. **Why did you avoid a multi-agent swarm for Phase 2?**  
   "Following the ponytail principle of choosing the simplest solution that works, a single Google ADK agent with a bounded read-only gateway solves 100% of our diagnostic requirements with lower latency, lower token consumption, and zero inter-agent communication failures. Adding multi-agent hierarchies before proving the single-agent pipeline would have been premature over-engineering."
