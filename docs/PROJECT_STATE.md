# AegisOps — Current Project State

**Updated:** 2026-10-10
**Current phase:** Phase 0 (Foundation, Contracts, and ADK Spike)
**Overall state:** `PHASE 0 FOUNDATION COMPLETE — LOCAL + HOSTED CI VERIFIED; LIVE-MODEL GATE OUTSTANDING; PHASE 1 LOCKED`
**Source:** `../AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md` sections 16–18 and 24; `docs/PHASE_REPORTS/PHASE_00_FOUNDATION.md`.

## Implemented and verified in Phase 0

- [x] **Repository toolchain and dependency locks:**
  - Python 3.14.7 via `.venv` and `uv.lock` (`.tools/bin/uv` 0.13.0).
  - Node.js 22.23.1 and npm 10.9.8 with npm workspaces (`apps/web`, `examples/shop-api`) via `package-lock.json`.
  - Static linters & formatters passing: `ruff check` (0 errors), `ruff format --check` (16 files formatted), `mypy --strict` (0 errors in 5 files), `npm run lint` (0 errors), `prettier --check` (all files formatted), `tsc --noEmit` (workspaces clean).
  - Security audits passing: `pip-audit` (0 vulnerabilities), `npm audit --audit-level=high` (0 vulnerabilities).
- [x] **Core domain contracts and validation:**
  - `apps/api/app/schemas.py`: Pydantic v2 frozen contracts for `Scope`, `Alert`, `Incident`, `Evidence`, `EvidenceRef`, `Hypothesis`, `InvestigationResult`, `Approval`.
  - Deterministic `validate_evidence` engine: rejects cross-tenant/cross-service/cross-run citations, rejects fabricated evidence IDs, enforces permitted action catalog, blocks naive timestamps and numeric pseudo-confidence.
- [x] **FastAPI control plane baseline:**
  - `apps/api/app/main.py`: `/healthz` (HTTP 200 `{"status":"ok","service":"api"}`) and `/readyz` (HTTP 200 with async PostgreSQL and Redis probes, fails closed with 503 on error without secret leakage).
  - Docker image `aegisops-api:phase0` built and tested.
- [x] **Database & queue foundation:**
  - PostgreSQL 18 with `pgvector` 0.8.7 (`pgvector/pgvector:0.8.7-pg18-bookworm@sha256:...`).
  - Redis 8.10.2-alpine (`redis:8.10.2-alpine@sha256:...`) with 64MB memory limit and `noeviction` policy.
  - Alembic migrations: `0001_foundation.py` creating `organizations` and `services` tables with foreign keys and unique constraints.
  - Migration round-trip verified in isolated verification container (`aegisops_phase0_verify` DB): upgrade head -> insert & constraints -> vector extension 0.8.7 verified -> downgrade base -> upgrade head.
- [x] **Frontend dashboard shell:**
  - Next.js 16.4.0 / React 19.3.0 / Tailwind CSS 4.3.3: accessible dark console theme, skip-to-content navigation, truthful empty states.
  - `/healthz` route (HTTP 200 `{"status":"ok","service":"web"}`).
  - Production build (`next build --webpack`, single CPU bounded) passes.
  - Playwright browser tests pass (2/2): shell responsive navigation on desktop and mobile (viewport 375x812), `/healthz` HTTP 200.
  - Docker image `aegisops-web:phase0` built and tested.
- [x] **Demo service stub:**
  - `examples/shop-api`: Express 5.3.0 / TypeScript service with `/healthz` (HTTP 200 `{"status":"ok","service":"shop-api","phase":0}`).
  - Node test passing (`tests/health.test.mjs`).
  - Docker image `aegisops-shop-api:phase0` built and tested.
- [x] **Google ADK integration spike:**
  - `agents/incident_investigator/spike.py`: Real Google ADK 2.11.0 `LlmAgent`, `Runner`, `InMemorySessionService`, structured `InvestigationResult` schema.
  - Scoped read-only `SyntheticTool.get_log_snippets` returning `UNTRUSTED_SOURCE` records with audit ledger.
  - Offline deterministic test double `OfflineModel`: exercises 2 model turns, 1 tool invocation, structured output parsing, citation validation.
  - Two scenarios tested: `supported` (status: `complete`) and `conflicting` (status: `inconclusive`).
  - Budget guard: enforces max 4 model calls, max 12 tool calls, token reservations, timeout bounds.
- [x] **Offline auth spike:**
  - `apps/api/tests/test_auth_spike.py`: Authlib 1.8.0 offline PKCE S256 and independent state generation verified against `example.invalid` without network access (governed by ADR-019 / DEC-227).

## Untested / Blocked / Deferred

**Developer clarification (DEC-231):** Foundation implementation/local verification are complete and hosted CI is verified for the original Phase 0 commit. Live-model verification is a separate mandatory gate before Phase 1 can formally unlock. Earlier credential-absence/unlocked statements are preserved in the journal and dated report history; they are not current status.

- [ ] **Live Gemini/Groq model verification:** `BLOCKED — ACCOUNT TIER UNVERIFIED / NOT RUN`.
  - Both keys exist locally and `.env` is ignored; values were not displayed.
  - No authenticated provider browser, gcloud executable, or Google ADC file is available. Key ownership and account Free tier cannot be verified from public pricing or key presence.
  - Paid spend remains $0; the CLI now rejects nonzero ceilings and requires fresh key-bound operator tier evidence. No evidence record has been created for either real key.
  - Gemini is provisional primary; Groq is secondary. The same ADK spike has an isolated pinned LiteLLM bridge with offline HTTP tests. No automatic switching.
  - [Comparison report](PHASE_REPORTS/PHASE_00_MODEL_COMPARISON.md) records exact tests, provider blockers, dependency audit and GitHub evidence.
- [ ] **Real telemetry and alert ingestion:** `DEFERRED TO PHASE 1`.
  - Per developer instruction ("CRITICAL: DO NOT START PHASE 1"), Prometheus, Loki, Tempo, Alertmanager webhooks, and sample app instrumentation are deferred to Phase 1.
- [ ] **Celery worker and persistent agent queue:** `DEFERRED TO PHASE 2`.
- [ ] **Full product auth/RBAC and multi-tenant sessions:** `DEFERRED TO PHASE 3`.
- [ ] **Runbook RAG with pgvector:** `DEFERRED TO PHASE 5`.
- [ ] **n8n internal automations and remediation approvals:** `DEFERRED TO PHASES 6–7`.

## Phase 0 exit-gate verification summary

| Verification item | Command | Exit code | Result |
|---|---|---|---|
| Python static checks | `ruff check apps agents && ruff format --check apps agents && mypy apps/api/app agents/incident_investigator/spike.py` | 0 | PASSED (0 errors, 16 formatted, 5 types checked) |
| Python unit tests | `pytest -v -m 'not integration'` | 0 | PASSED (36 passed, 2 deselected) |
| Python security audit | `pip-audit --progress-spinner off` | 0 | PASSED (0 known vulnerabilities) |
| Web lint & format | `npm run lint && npm run format:check && npm run typecheck` | 0 | PASSED (ESLint, Prettier, TypeScript workspaces clean) |
| Web unit tests | `npm test` | 0 | PASSED (shop-api health test passed) |
| Web security audit | `npm audit --audit-level=high` | 0 | PASSED (0 vulnerabilities) |
| Web browser smoke | `PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright npm run test:web` | 0 | PASSED (2/2 Playwright tests passed) |
| Web production build | `npm run build` | 0 | PASSED (Next.js webpack build clean) |
| ADK spike generation | `python -m agents.incident_investigator.spike --output ...` (supported & conflicting) | 0 | PASSED (2 artifacts generated) |
| Docker image builds | `docker compose build api && docker compose build web && docker compose build shop-api` | 0 | PASSED (all 3 images built) |
| Compose integration | `docker compose -p aegisops-verify -f docker-compose.yml -f docker-compose.verify.yml --profile verify run --rm verify` | 0 | PASSED (migration round-trip & DB readiness verified) |
| Service health checks | `curl -f http://127.0.0.1:{8000,3000,3001}/healthz && curl -f http://127.0.0.1:8000/readyz` | 0 | PASSED (all endpoints 200 OK) |
| Hosted foundation CI | [run 38043157853](https://github.com/Tarun-sde/AegisOps/actions/runs/38043157853) | success | VERIFIED for b0014ab9; subsequent comparison work tracked separately |
