# Exact Technology Versions and API Compatibility

**Status:** Phase 0 stack locked and verified (2026-10-10). Do not guess or use floating `latest` images in deployments.

| Component | Planned technology | Pinned tested version | Package/image digest | Verified on | Compatibility notes |
|---|---|---|---|---|---|
| Python | CPython | 3.14.7 | Native runtime / `.tools/bin/uv` 0.13.0 | 2026-10-10 | Pinned in `pyproject.toml` and `.python-version` |
| API | FastAPI / Pydantic | FastAPI 0.141.0 / Pydantic 2.14.0 | PyPI wheel via `uv.lock` | 2026-10-10 | Compatible with ADK OTel constraints (`opentelemetry-api <= 1.42.1`) |
| Agent | google-adk | 2.11.0 / google-genai 2.29.0 | PyPI wheel via `uv.lock` | 2026-10-10 | Real ADK dispatch verified offline; JSON schema for function declaration |
| AI model | Gemini API model | `gemini-3.8-flash` (candidate) | N/A | 2026-10-10 (Offline double only) | Provisional primary; key present, actual account tier unverified. Live NOT RUN; free-only guard, paid spend $0 |
| Node.js | LTS | 22.23.1 / npm 10.9.8 | Native runtime / `package-lock.json` | 2026-10-10 | Pinned in `package.json` engines and `.node-version` |
| Frontend | Next.js / React | Next.js 16.4.0 / React 19.3.0 | npm registry via `package-lock.json` | 2026-10-10 | ESLint 9.39.5, TypeScript 6.0.3, Tailwind 4.3.3, cpus: 1 webpack build verified |
| Database | PostgreSQL / pgvector | PostgreSQL 18 / pgvector 0.8.7 | `pgvector/pgvector:0.8.7-pg18-bookworm@sha256:2358fcba361ed2233a5ed81b5fe4ca779ccb304120ce531a3bf51c0ed7e2bc11` | 2026-10-10 | Healthcheck and Alembic migration round-trip verified in Compose |
| Queue | Redis / Celery | Redis 8.10.2 | `redis:8.10.2-alpine@sha256:3811787313eba226a2ef38658c6ccb91cd5e110edc89c37767de373120a0e5a0` | 2026-10-10 | 64MB noeviction probe verified; Celery deferred to Phase 2 |
| Automation | n8n Community | Design only (v1 internal) | TBD | Deferred to Phase 6 | Operator-authored workflows only; no customer builder |
| Metrics | Prometheus / Alertmanager | Design only | TBD | Deferred to Phase 1 | Sample app red metrics and Alertmanager webhook in Phase 1 |
| Logs / traces | Loki / Tempo / OTel Collector | Design only | TBD | Deferred to Phase 1–2 | Exporter compatibility check in Phase 1 |
| Tests | Pytest / Playwright | pytest 9.1.1 / Playwright 1.64.0 | PyPI / npm | 2026-10-10 | 36 unit + 2 Compose integration + 2 Playwright browser tests passing |

Governed by `ADR-017`, `DEC-209`–`DEC-228`. Commit lockfiles after software is installed and tested.

## Phase 0 comparison extension — ADR-020 / DEC-232–236

- LiteLLM **1.104.2** is an isolated secondary-provider bridge through ADK 2.11.0; OpenAI **2.54.0** is transitively locked. Groq model ID **openai/gpt-oss-120b**. All versions/hashes in uv.lock; no proxy extras or routing.
- python-dotenv **1.2.4** (already installed) is explicitly declared for selective, non-interpolating CLI `.env` loading. Gemini **3.8 Flash** remains provisional primary.
- Resolver adds 31 packages and changes filelock **4.1.0 → 3.32.7**, required by LiteLLM's `<4` constraint; other existing versions remain locked.
- Linux LiteLLM wheel SHA-256 **416c3538ea78b08d637ec45564a919232aa2093e73adb9dd7752f7cff2ec585e** matched PyPI metadata; no `.pth`, `sitecustomize.py` or `usercustomize.py`. Pre-install exported-lock audit found no known vulnerabilities. This is scoped evidence, not a complete supply-chain assurance claim.
- Groq combined native tools/schema capability is disabled to follow vendor documentation; ADK's existing structured response tool is used instead. Gemini retains its native ADK adapter. Offline HTTP tests verify the bridge; neither live provider has passed yet.
- Final check commands/outcomes: [comparison report](PHASE_REPORTS/PHASE_00_MODEL_COMPARISON.md).
