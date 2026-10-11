# Architecture — Implementation Baseline

**Status:** `IMPLEMENTED & VERIFIED (Phases 0–5)`  
**Canonical source:** Master implementation plan §§3–5, 7–9, 14.  
**Related decisions:** ADR-001 through ADR-025 in `ENGINEERING_DECISIONS.md`.

```mermaid
flowchart TD
    WEB[Next.js dashboard] --> API[FastAPI control plane]
    APP[Instrumented service] --> OTEL[OpenTelemetry Collector]
    APP --> PROM[Prometheus]
    PROM --> AM[Alertmanager]
    AM --> API
    OTEL --> LOKI[Loki logs]
    OTEL --> TEMPO[Tempo traces]
    API --> DB[(PostgreSQL + pgvector)]
    API --> CELERY[Redis / Celery queue]
    CELERY --> ADK[Google ADK investigation worker]
    ADK --> TG[Scoped read-only tool gateway]
    TG --> PROM
    TG --> LOKI
    TG --> TEMPO
    TG --> DB
    ADK --> VALID[Evidence validator]
    VALID --> DB
    API --> N8N[n8n operator workflows]
    API --> APPROVAL[Deterministic approval service]
    APPROVAL --> STAGE[Allowlisted staging executor]
```

## Responsibility boundaries

- **Data plane:** sample app and third-party telemetry components. No LLM on the ingestion hot path.
- **Control plane:** auth/authorization, services, alerts, incidents, approvals, audit, API contracts.
- **AI plane:** asynchronous bounded Google ADK tool calls, RAG, evidence ledger, schema validation and evaluations.
- **Automation plane:** n8n notifications/integrations; PostgreSQL remains source of truth for state and approvals.
- **Presentation:** Next.js UI for incident timeline, evidence, action proposals and run history.

## Architectural invariants

1. Access control is server-owned, never delegated to the model.
2. Logs/runbooks are untrusted input; redact sensitive data and resist prompt injection.
3. Diagnosis citations resolve to authorized evidence IDs or the answer is not presented as verified.
4. Model outages cannot stop basic incident ingestion.
5. No production action execution in portfolio v1; staging execution requires explicit policy-checked approvals.
6. Start with one bounded agent; expand only after benchmarks justify complexity.

## Change control

Add/extend an ADR before changing a major boundary. Record all behavior-affecting defaults and smaller decisions using `DEC-XXX` entries. Update this file only after developer-authorized design changes, and update statuses after implementation evidence exists.
