# AegisOps — Repository starter and first actions

This bundle provides the **original implementation plan and original engineering decision journal**, plus a consolidated `AGENTS.md` and honest starter documentation. Directory placeholders are included for future code; **they are not implemented services**.

## Set up the repository

1. Extract the ZIP. Its `AegisOps/` folder is the repository root.
2. Create an empty GitHub repository named `AegisOps` (or choose your own name).
3. Copy the contents of `AegisOps/` into the local repository root. Do **not** nest `AegisOps/AegisOps/`.
4. Read `AGENTS.md`, the master plan, `docs/PROJECT_STATE.md`, and the decision journal.
5. Start at Phase 0; update the journal whenever a choice is made, even a small one.
6. Implement actual code, configuration, lockfiles, tests, CI and deployments incrementally. Do **not** claim the skeleton is executable.

## Suggested initial Git commands

```bash
cd AegisOps
git init
git add .
git commit -m "docs: initialize AegisOps plan and decision journal"
git branch -M main
# After creating your own remote repository:
# git remote add origin <YOUR_GITHUB_REMOTE_URL>
# git push -u origin main
```

Use your existing repository if one is already created; avoid overwriting working code or history. Check `git status` and compare before copying.

## Canonical documents

| Path | Purpose | Initial status |
|---|---|---|
| `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md` | Master architecture, features, 12-week phases, security, acceptance criteria | Supplied design v1.0 |
| `AGENTS.md` | Agent operating rules, phases, safety, decision enforcement | Active upon adoption |
| `docs/ENGINEERING_DECISIONS.md` | 16 architectural decisions, 202 micro decisions, explanations and interview preparation | Design only |
| `docs/AGENTS_DECISION_LOG_RULES.md` | Extended mandatory logging instructions | Active upon adoption |
| `docs/PROJECT_STATE.md` | Phase, implementation/verification status, known blockers | Initial: not started |
| `docs/ARCHITECTURE.md` | Short view of the chosen boundaries | Design only |
| `docs/SECURITY_MODEL.md` | Security baseline and verification plan | Design only |
| `docs/EVALUATION_PLAN.md` | Evaluation protocol and controlled baselines | Design only |
| `docs/TECH_STACK_LOCK.md` | Exact verified versions: initially blank | Versions unselected |
| `docs/PROJECT_STRUCTURE.md` | Full repo tree and component boundaries | Design only |
| `docs/PHASE_0_START_PROMPT.md` | Ready-to-copy kickoff instruction for coding agent | Ready |
| `docs/PHASE_REPORTS/PHASE_00_FOUNDATION.md` | Phase 0 execution checklist | Not started |

## How decisions should accumulate

- The journal starts with planned choices; implementation agents must **append** new decisions and evidence rather than resetting the document.
- Add `DEC-203`, `DEC-204`, etc. for subsequent small new choices; add `ADR-017` onward for major choices. Confirm the highest current IDs before assigning the next IDs.
- On every code task, record: decision, *why this over alternatives*, downsides, code/test evidence, and follow-up interview explanation.
- Use `docs/ADR/` for separate large decision writeups when the journal entry alone is insufficient; link from the canonical journal.

## Important scope reminder

This is an AI/FDE/backend engineering **portfolio product**, not an academic report. All statuses, benchmark targets, privacy and licensing constraints are inherited from the master implementation plan.
