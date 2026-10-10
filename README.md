# AegisOps

**AI-powered incident intelligence and response platform — design-stage repository starter.**

AegisOps aims to detect application incidents using standard observability infrastructure, investigate them through scoped **Google ADK** tools, cite real telemetry and runbook evidence, and coordinate safe, approved responses. The target is a reproducible, deployable, resume-first AI engineering portfolio project.

> **Status:** Planning and repository bootstrap only. This repository starter does not contain a running backend, frontend, AI agent, or demo. The master plan and decision records are proposals, not measured results.

## Start here

1. Read [`START_HERE.md`](START_HERE.md) for repository layout and how to begin.
2. Read [`AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md`](AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md) for product goals, architecture, phase gates and schedule.
3. Read [`AGENTS.md`](AGENTS.md) before assigning work to a coding assistant.
4. Read [`docs/ENGINEERING_DECISIONS.md`](docs/ENGINEERING_DECISIONS.md) for initial design rationale and granular decisions.
5. Track progress in [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md).

## Planned architecture

- **Frontend:** Next.js + TypeScript
- **Control plane:** FastAPI / PostgreSQL
- **Investigation:** Google ADK + Gemini API, auditable read-only tool gateway, typed evidence-grounded outputs
- **Background tasks:** Celery + Redis
- **Telemetry:** OpenTelemetry, Prometheus, Alertmanager, Loki, Tempo
- **Knowledge retrieval:** PostgreSQL + pgvector and lexical retrieval
- **Automation:** Internally operator-authored n8n workflows
- **Evaluation:** Injected-fault lab, real end-to-end telemetry, held-out scenarios

These are design choices subject to verification and documented revision. **No performance or reliability claim is earned until measured.**

## Development priority

Build one verified path first: **controlled sample-app failure → actual alert → persisted incident → scoped ADK investigation → validated evidence-linked diagnosis**. Add polish and extensions only after passing the appropriate phase gates.

## License

Not yet selected. Do not assume this repository is licensed for redistribution just because its source is visible; choose a license explicitly before publishing or distributing source. Review third-party licenses separately, especially n8n usage restrictions.
