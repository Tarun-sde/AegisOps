# AegisOps — Repository Structure

**Status:** Design-stage scaffold. Empty directories contain `.gitkeep`, not working application code. The master implementation plan §15 defines the planned architecture.

```text
AegisOps/
├── AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md   # project source of truth
├── AGENTS.md                                # coding-agent rules
├── START_HERE.md                            # repository setup
├── README.md
├── apps/
│   ├── web/                                 # Next.js/TypeScript
│   ├── api/                                 # FastAPI control plane
│   └── worker/                              # Celery background tasks
├── agents/incident_investigator/            # Google ADK agent and tools
├── examples/shop-api/                       # instrumented demo app
├── infra/
│   ├── otel-collector/
│   ├── prometheus/{config,rules}/
│   ├── alertmanager/
│   ├── loki/
│   ├── tempo/
│   ├── grafana/{dashboards,provisioning}/
│   ├── reverse-proxy/
│   └── deployment/
├── automations/n8n/                         # operator-authored workflows
├── simulation/{scenarios,faults,replay}/
├── evaluations/{datasets,rubrics,baselines,reports}/
├── docs/
│   ├── ENGINEERING_DECISIONS.md             # canonical ADR/DEC journal
│   ├── AGENTS_DECISION_LOG_RULES.md
│   ├── PROJECT_STATE.md
│   ├── ARCHITECTURE.md
│   ├── PROJECT_STRUCTURE.md
│   ├── PHASE_0_START_PROMPT.md
│   ├── SECURITY_MODEL.md
│   ├── EVALUATION_PLAN.md
│   ├── INTERVIEW_PREP.md
│   ├── TECH_STACK_LOCK.md
│   ├── ADR/{README.md,ADR_TEMPLATE.md}
│   └── PHASE_REPORTS/{README.md,PHASE_00_FOUNDATION.md}
└── .github/workflows/                      # CI created when implemented
```

## Component boundaries

| Folder | Responsibility |
|---|---|
| `apps/api` | Authentication, alert ingestion, incidents, approvals, audit, authoritative state |
| `apps/worker` | Durable asynchronous investigation jobs and retries |
| `agents/incident_investigator` | Scoped read-only Google ADK tools and evidence-grounded hypotheses |
| `infra` | Standard monitoring/collection systems; not another custom observability platform |
| `automations/n8n` | Internal notifications and third-party integrations; not incident state |
| `simulation` | Safe controlled failures for demo and evaluation |
| `evaluations` | Ground-truth scenarios, scoring, baselines and reproducible result artifacts |
| `docs` | Current state, trade-offs, tested facts and interview defense |

Add implementation files, lockfiles, Compose definitions, tests and CI workflows in the corresponding phases. Document every behavior-bearing decision in the canonical journal, even small ones. Do not claim skeleton paths are implemented services.
