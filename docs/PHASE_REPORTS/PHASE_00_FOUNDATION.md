# Phase 0 — Foundation, Contracts and ADK Spike

**Current status:** `FOUNDATION COMPLETE — LOCAL + HOSTED CI VERIFIED; LIVE-MODEL GATE OUTSTANDING; PHASE 1 LOCKED` (DEC-231). **Date:** 2026-10-10.
**Master-plan source:** §§17 (Week 1), 18 (first 72 hours), 24.

## Delivered deliverables

- [x] Repository conventions, Makefile, Python/Node toolchains (`uv.lock`, `package-lock.json`), branch setup.
- [x] Engineering decision journal updated: `ADR-017`–`ADR-019`, `DEC-209`–`DEC-228` in `docs/ENGINEERING_DECISIONS.md`.
- [x] Pinned tested dependency versions in `docs/TECH_STACK_LOCK.md`.
- [x] Basic Docker stack: PostgreSQL 18 + pgvector 0.8.7, Redis 8.10.2, FastAPI, Next.js, shop-api.
- [x] `/healthz` endpoints across all three HTTP services and `/readyz` deep probe on API.
- [x] Typed incident, alert, evidence, investigation, approval contracts in `apps/api/app/schemas.py`.
- [x] Minimal Google ADK 2.11.0 agent invoking a mocked read-only log tool and returning typed `InvestigationResult`.
- [x] Deterministic citation validator rejects IDs never returned by tool, cross-scope citations, and unauthorized actions.
- [x] CI workflow in `.github/workflows/ci.yml`.

## Exit-gate evidence observed

| Check | Command/evidence | Result |
|---|---|---|
| API starts and health check responds | `curl -f http://127.0.0.1:8000/healthz` | `PASSED` (HTTP 200, `{"status":"ok","service":"api"}`) |
| Next.js development UI loads | `PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright npm run test:web` | `PASSED` (2/2 Playwright tests: desktop/mobile shell + `/healthz`) |
| PostgreSQL and Redis reachable from services | `curl -f http://127.0.0.1:8000/readyz` | `PASSED` (HTTP 200, `{"status":"ready","checks":{"postgres":"ok","redis":"ok"}}`) |
| ADK mocked-tool smoke test | `python -m agents.incident_investigator.spike --output artifacts/spike-supported.json` | `PASSED` (2 model calls, 1 tool call, complete status, artifact generated) |
| Structured output & conflicting scenario | `python -m agents.incident_investigator.spike --scenario conflicting --output artifacts/spike-conflicting.json` | `PASSED` (status: `inconclusive`, contradicting evidence cited) |
| Nonexistent citation negative tests | `pytest apps/api/tests/test_foundation.py` | `PASSED` (tests reject fabricated IDs, cross-scope IDs, alien catalog actions) |
| Versions and costs/quotas documented | `docs/TECH_STACK_LOCK.md`, `DEC-224` | `VERIFIED` (all versions locked; live ceiling cap enforced at <=$0.10, default $0) |
| Isolated Compose migration round-trip | `docker compose -p aegisops-verify -f docker-compose.yml -f docker-compose.verify.yml --profile verify run --rm verify` | `PASSED` (upgrade head -> constraint checks -> downgrade base -> upgrade head) |
| CI configuration | `.github/workflows/ci.yml` | `VERIFIED` (ready for hosted run upon git push) |

## Historical foundation boundary report (before DEC-231 clarification)

1. **Google ADK vs Live Gemini:**
   - Real Google ADK 2.11.0 framework dispatch, runner, session service, and tool calling verified offline with deterministic test double.
   - Live Gemini API call is `NOT RUN / BLOCKED BY CREDENTIALS` (no `GOOGLE_API_KEY` provided; authorized paid budget is $0).
2. **Monitoring & Alerts:**
   - Deferred to Phase 1 per explicit user instruction ("CRITICAL: DO NOT START PHASE 1"). No fake telemetry or synthetic Alertmanager pipeline claimed.
3. **Authentication:**
   - Authlib 1.8.0 offline PKCE S256 spike verified (ADR-019 / DEC-227). No live issuer, sessions, or product RBAC implemented in Phase 0.
4. **Remediation:**
   - Proposal contracts forbid execution; production environment rejected by contract validator. Staging execution deferred to Phase 7.

**Historical conclusion, superseded by DEC-231:** Phase 0 was recorded complete with Phase 1 unlocked pending authorization. Current interpretation: foundation complete, live-model gate mandatory and outstanding, Phase 1 LOCKED.

## Subsequent model-comparison preflight — 2026-10-10

DEC-230 records updated facts in [PHASE_00_MODEL_COMPARISON.md](PHASE_00_MODEL_COMPARISON.md): both keys are configured without disclosure; commit `b0014ab9ad39e4657f20c4f771d71c259067653e` is on remote main and its hosted CI passed; all 36 offline unit tests passed again outside the sandbox. Live inference remains NOT RUN pending actual account free-tier confirmation. ADR-018's stricter phase-unlock statement conflicts with the completion statement above; the conflict was reported and implementation paused pending clarification. Historical gate claims are preserved, not silently reconciled. Phase 1 remains unauthorized and untouched.

## Developer clarification — DEC-231

The developer resolved the earlier conflict: foundation implementation and local verification are complete; hosted CI for commit b0014ab9 is confirmed green. Live-model verification is a separate outstanding mandatory gate before Phase 1 is formally unlocked. The historical boundary report above is retained for provenance. Current keys are present, but actual provider account tiers are unverified; no live inference was authorized to proceed. See the [current comparison report](PHASE_00_MODEL_COMPARISON.md). No Phase 1 work was started.
