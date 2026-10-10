# Phase 0 — Copy-ready coding-agent prompt

Paste the following instruction into Codex, Gemini or another coding agent after opening the extracted AegisOps repository.

---

Read `AGENTS.md` completely. Then read `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md`, `docs/PROJECT_STATE.md`, `docs/ENGINEERING_DECISIONS.md`, `docs/AGENTS_DECISION_LOG_RULES.md`, `docs/TECH_STACK_LOCK.md`, and `docs/PHASE_REPORTS/PHASE_00_FOUNDATION.md`.

Implement **Phase 0 ONLY** using the master plan sections 17, 18 and 24. Build the foundation, pin and test exact versions, establish basic typed contracts and a minimal Google ADK agent using a **mocked, read-only tool**. Do not start Phase 1 or pretend the project has real incident telemetry yet.

Before any behavior-affecting choice—large or small—consult the existing ADR/DEC entries and document any new trade-off in `docs/ENGINEERING_DECISIONS.md`. Record exactly what you selected, why, honest alternatives (or `Not evaluated`), downside, revisit trigger and evidence. This includes package versions, configurations, defaults, timeouts, fields, interfaces, error handling, test strategies and UI decisions. Link decisions already captured rather than duplicating entries. Preserve old decisions when they change; never fabricate a retrospective justification. Request developer approval for changes to significant architecture or security assumptions.

Use official documentation relevant to installed pinned versions for Google ADK and Gemini. Don't commit secrets or claim consumer AI subscriptions cover API billing. Implement source-code tests and execute them, reporting the exact commands and outcomes. Don't invent successful tests, hosted CI results, metrics, deployments or completed agent capabilities.

At the end, update `docs/ENGINEERING_DECISIONS.md`, `docs/PROJECT_STATE.md`, `docs/TECH_STACK_LOCK.md`, and `docs/PHASE_REPORTS/PHASE_00_FOUNDATION.md`. Report decisions added/updated/reused (and why), files changed, tests actually executed, blockers, safety consequences, and which Phase 0 acceptance gates were **verified**. No automatic transition to Phase 1 until gates truly pass.

---

The project is resume-first. Document real engineering reasoning, failures and measurements, not impressive-sounding unverified claims.
