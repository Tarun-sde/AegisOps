# AGENTS.md — AegisOps coding-agent instructions

**Scope:** Applies throughout the AegisOps repository. The human developer owns architecture choices and approval of major deviations. **No project features are implemented merely because this starter exists.**

## Mandatory read order — at the start of every task

1. `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md` — scope, phase gates, interfaces, priorities.
2. `AGENTS.md` — operational instructions for coding agents.
3. `docs/PROJECT_STATE.md` — what is done, what is blocked, and which phase is unlocked.
4. `docs/ENGINEERING_DECISIONS.md` — accepted reasoning and its evidence status.
5. `docs/AGENTS_DECISION_LOG_RULES.md` — complete, binding decision-logging requirements.
6. Active phase report and any relevant entries under `docs/ADR/`.

If documents disagree, **stop and report the conflict** rather than quietly switching architecture. The master plan is the approved design baseline; a change requires a documented ADR/deviation and developer approval when it is architectural or security-sensitive. Neither plan nor journal overrides safe behavior or legitimate explicit user instructions.

## Phase discipline and verifiability

- Work only within the unlocked phase and its written acceptance criteria, unless the developer explicitly changes scope.
- Do not claim completed phases on the basis of written code alone. Run specified unit/integration/e2e/security checks and report commands and **actual** results.
- Don't invent commit hashes, passing hosted CI, production customers, benchmark results, cost savings, deployments, model quotas or screenshots.
- Distinguish: `DESIGN ONLY`, `IMPLEMENTED — UNVERIFIED`, `VERIFIED`, `BLOCKED`, `DEFERRED`.
- Preserve existing working code and migrations; avoid unrelated refactoring or silent dependency upgrades.
- Any API or tool-specific implementation must match the pinned package version and verified vendor documentation.
- A feature is not end-to-end when it has only mock adapters or synthetic AI outputs. Label mocks explicitly.

## Security invariants

- LLM output is untrusted. Enforce tool access, tenant/service bounds, evidence citation validity, budgets, and action permissions with deterministic backend code.
- No arbitrary shell/SSH/URL/SQL/PromQL, privileged Docker socket, production-write GitHub token, secret access, or Kubernetes admin exposed to an agent.
- No automated production remediation in v1; staging-only allowlisted actions require a separate immutable-payload approval checked at execution.
- Do not expose credentials, raw customer logs, protected endpoints, or dangerous simulation controls in public demo.
- Incoming alerts and logs may be malicious. Validate webhooks, redact telemetry and resist prompt injection.
- n8n is limited to internally maintained operator-authored automations in v1; don't expose a customer workflow builder without separate license review.

## EVERY decision gets a reason

The complete non-optional rules live at `docs/AGENTS_DECISION_LOG_RULES.md`. **Apply them in full**. In particular:

- For every non-mechanical choice, including small defaults, record the context, chosen option, alternatives (or `Not evaluated`), justification, downside, revisit trigger, and evidence state.
- Use full `ADR-XXX` records for significant architecture/security/platform changes and append-only `DEC-XXX` rows for granular choices. Do not overwrite history or recycle identifiers.
- Cite already-applicable decision IDs rather than manufacturing additional decisions for purely mechanical implementation.
- For failures, record reproduction, hypotheses, what failed, fix, verification, and lessons in the journal's debugging diary.
- Update the journal **before or with** the implementation change. At the end of EVERY task, report all decision IDs created, changed, or governing the work, with reasons.
- During a phase gate, update the project state and phase report, linking actual test output and unresolved risks.

## Change completion report format

1. Implemented behavior and touched paths.
2. Decision IDs created / updated / reused, with rationale and rejected options.
3. Tests executed and outputs (or `NOT RUN`, with explanation).
4. Security and privacy consequences.
5. Current milestone status: done / partial / blocked / untested.
6. Deviations from plan and developer approvals required.
7. Resume/interview lessons supported by verified evidence only.

## First task

Follow `docs/PHASE_REPORTS/PHASE_00_FOUNDATION.md` and the master plan's Phase 0 section. The initial `PROJECT_STATE.md` correctly marks **all implementation as NOT STARTED**.
