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
| Queue | Redis / Celery | Redis 8.10.2 / Celery 5.5.3 | `redis:8.10.2-alpine@sha256:3811787313eba226a2ef38658c6ccb91cd5e110edc89c37767de373120a0e5a0` | 2026-10-10 | Celery worker verified with Redis broker in Docker Compose for Phase 2 |
| Automation | n8n Community | Design only (v1 internal) | TBD | Deferred to Phase 6 | Operator-authored workflows only; no customer builder |
| Metrics | Prometheus / Alertmanager | Prometheus v3.2.1 / Alertmanager v0.28.1 | `prom/prometheus:v3.2.1@sha256:6927e0919a144aa7616fd0137d4816816d42f6b816de3af269ab065250859a62` / `prom/alertmanager:v0.28.1@sha256:27c475db5fb156cab31d5c18a4251ac7ed567746a2483ff264516437a39b15ba` | 2026-10-10 | Promtool rule tests and authenticated webhook delivery verified in Phase 1 |
| Logs / traces | Loki / OTel Collector / Tempo | Loki 3.4.2 / OTel Collector Contrib 0.120.0 | `grafana/loki:3.4.2@sha256:58a6c186ce78ba04d58bfe2a927eff296ba733a430df09645d56cdc158f3ba08` / `otel/opentelemetry-collector-contrib:0.120.0@sha256:85ac41c2db88d0df9bd6145e608a3cb023f5d8443868adbfbbf66efb51087917` | 2026-10-10 | OTLP HTTP logs -> Loki export verified; Tempo deferred to Phase 3 |
| Node metrics | prom-client | 15.1.3 | npm registry via `package-lock.json` | 2026-10-10 | HTTP RED metrics with bounded label policy in `shop-api` |
| Tests | Pytest / Playwright | pytest 9.1.1 / Playwright 1.64.0 | PyPI / npm | 2026-10-10 | 74 unit + 3 Playwright browser + promtool + Phase 1 & 2 E2E verified live |

Governed by `ADR-017`, `DEC-209`–`DEC-228`. Commit lockfiles after software is installed and tested.

## Phase 0 comparison extension — ADR-020 / DEC-232–236

- LiteLLM **1.104.2** is an isolated secondary-provider bridge through ADK 2.11.0; OpenAI **2.54.0** is transitively locked. Groq model ID **openai/gpt-oss-120b**. All versions/hashes in uv.lock; no proxy extras or routing.
- python-dotenv **1.2.4** (already installed) is explicitly declared for selective, non-interpolating CLI `.env` loading. Gemini **3.8 Flash** remains provisional primary.
- Resolver adds 31 packages and changes filelock **4.1.0 → 3.32.7**, required by LiteLLM's `<4` constraint; other existing versions remain locked.
- Linux LiteLLM wheel SHA-256 **416c3538ea78b08d637ec45564a919232aa2093e73adb9dd7752f7cff2ec585e** matched PyPI metadata; no `.pth`, `sitecustomize.py` or `usercustomize.py`. Pre-install exported-lock audit found no known vulnerabilities. This is scoped evidence, not a complete supply-chain assurance claim.
- Groq combined native tools/schema capability is disabled to follow vendor documentation; ADK's existing structured response tool is used instead. Gemini retains its native ADK adapter. Offline HTTP tests verify the bridge; neither live provider has passed yet.
- Final check commands/outcomes: [comparison report](PHASE_REPORTS/PHASE_00_MODEL_COMPARISON.md).

## Phase 8 frontend integration — DEC-342 / DEC-350 (historical)

- Runtime Next.js 16.4.0 / React 19.3.0 pins unchanged; no runtime package added.
- Development-only `@axe-core/playwright` **4.13.0**, transitive `axe-core` **4.13.0**, exact package-lock records. Installed package README confirms `new AxeBuilder({page}).analyze()` integration. `npm install` reported 0 known vulnerabilities in the resolved 367-package tree on 2026-10-14.
- Local Inter and Geist Mono Latin variable WOFF2 files copied selectively from design source's installed Fontsource packages, with original OFL notices under `apps/web/public/licenses/`. They load from the application origin; no external font service.
- Phase 8 originally avoided GSAP/Lenis; this visual strategy is superseded by Phase 8.1 below. No Python dependency change.


## Phase 8.1 design fidelity — ADR-029 / DEC-351–358

- Next.js **16.4.0** and React **19.3.0** remain unchanged.
- Runtime additions match the reference lock: **gsap 3.15.0**, **@gsap/react 2.1.2**, **lenis 1.3.26**. Exact pins and integrity records are in the main package lock. No design-repository lockfile is imported.
- Installed READMEs/types verified the GSAP context/revert lifecycle and Lenis ticker/CSS/cleanup integration. Their original source choreography is required by the explicit Phase 8.1 correction; a native approximation was rejected. These dependencies enlarge the frontend runtime/test surface; no performance gain is claimed.
- Existing licensed local fonts and axe development dependency remain. No Python/backend/worker dependency changes.
