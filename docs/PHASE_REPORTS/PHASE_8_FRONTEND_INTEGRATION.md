# Phase 8 — Controlled frontend integration

Status: VERIFIED LOCALLY — 2026-10-14. Baseline main ef374d2562a8c05b5f859fc4c812ff9b13c8f5bc; design f46969734ce644be97003f558bd738dd5e76832f. Branch feat/phase8-frontend-integration. No integration commit/push/deployment.

Governing decisions: ADR-028; DEC-339–350, reused ADR-023/027 and DEC-335–338. See [integration audit](../PHASE_8_INTEGRATION_AUDIT.md) for source/destination/API/route mappings and deliberate exclusions.

Baseline: make check, make test and isolated make browser each exit 0. Logs originally /tmp/aegisops-phase8-baseline-{check,test,browser}.log, archived with final evidence under artifacts/phase8-20261014/ (gitignored local verification artifacts).

## Checkpoint evidence

- A: Audit and baseline complete. `make check` exit 0, `make test` exit 0 (158 Python passed, 6 integration tests deselected, 132 warnings; Express 1 passed). Baseline `make browser` exit 0: 8 passed in 7.7s; project aegisops-browser-78ee2d56. Read-only design GitHub HEAD matches local and separate temporary clone.
- B–G: Implemented in apps/web. Static checks/typecheck/lint pass. Runtime dependencies unchanged; @axe-core/playwright 4.13.0 added only for development acceptance checks.
- H attempt 1: `make browser` exit 2; project aegisops-browser-a7478d0d. Production build and all non-root Beat/cleanup assertions passed; 12/15 Playwright passed in 52.7s. Three failures: exact select label, incorrectly assumed loopback denial, and contrast during marketing opacity entrance. All eight existing tests passed. Real lifecycle, immutable proposal review/approve/reject, staging execution, persisted execution read, independent recovery and duplicate-execution response passed. Fixes and reasoning recorded in BUG-20261014-002; rerun pending.
- Post-change regression: `make test` exit 0 (158 Python passed, 6 deselected; Express 1 passed); `make check` exit 0 before browser corrections. Latest frontend `npm run typecheck` and `npm run lint` both exit 0 after corrections.
- H attempt 2: `make browser` exit 2; project aegisops-browser-c82786ac. 14/15 passed in 23.6s. Functional tests passed; lifecycle/search contrast and populated mobile proposal overflow failed the aggregate audit. Targeted repairs are recorded in BUG-20261014-002.
- H final: sequential `make check` then `make browser` both exit 0; project aegisops-browser-aa6dafae. **16/16 Playwright passed in 23.4s**. Production Next.js and shop-api builds passed. Real worker expiry cleanup, idempotent expiry/outbox checks, and non-root Beat scheduler assertions passed. Disposable containers/network/volume were removed by the gate.

## Final validation and review

| Command / review | Actual result | Local evidence |
|---|---|---|
| `make check` | PASS: Ruff, formatting, mypy, ESLint, Prettier, both workspace typechecks | artifacts/phase8-20261014/aegisops-phase8-check-final.log |
| `make test` | PASS: 158 Python tests, 6 integration tests deselected, 132 warnings; 1 Express suite | artifacts/phase8-20261014/aegisops-phase8-test.log |
| `make browser` | PASS: scheduler/cleanup assertions and 16 browser tests, 23.4s | artifacts/phase8-20261014/aegisops-phase8-browser-3.log; artifacts/aegisops-browser-aa6dafae/ |
| Frontend `npm run typecheck`, `npm run lint` | PASS individually and in final static gate | archived frontend logs and final check log |
| Frontend `npm run build` | PASS, executed by root workspace build inside final browser gate, after typecheck | final browser log, Next.js production build section |
| Accessibility/readability | No serious/critical axe WCAG A/AA findings on nine core routes, approval modal and explicit mocked evidence panel; checked visible metadata/control text >=14px | apps/web/tests/integration.spec.ts and final browser log |
| Responsive/keyboard | PASS: 375/768/1440px core layouts have no document overflow; mobile dialog/focus, evidence navigation and reduced-motion interaction | final browser log and 32 PNGs under artifacts/phase8-20261014/browser-captures/ |

Visual review covered desktop landing/workspace/incident, mobile workspace/proposals/simulation and desktop/mobile evidence. Final proposal wrapping, readable lifecycle controls and scoped citation states were inspected after repairs. Screenshots contain disposable browser fixtures; the two evidence captures are explicitly mocked and prove presentation only. Automated accessibility checks are not full WCAG certification or screen-reader testing. The six deselected integration tests were not separately rerun in this phase; the real PostgreSQL browser gate is a distinct check.

Checkpoints A–H are complete for the documented local integration scope. No API/backend/worker/agent/infrastructure/migration changes or Python dependency changes were made. Phase 9 remains not started. Remaining refinements are cross-browser/assistive-technology review, optional cinematic timing, and future approved scoped analytics APIs; none is presented as verified capability.

## Migrated, adapted and retained files

**Selected source:** original AegisMark and Pavilion SVG from design components/workspace/project-visuals.tsx and components/artwork.tsx -> apps/web/app/components/design-artwork.tsx; native focus helper -> dialog-focus.ts; licensed Inter/Geist Mono Latin WOFF2 -> apps/web/public/fonts with OFL notices. Both Fontsource packages are 5.3.0. Artwork branding is AegisOps; no Heron product promises remain.

**Adapted presentation:** hero/home story -> components/landing.tsx and app/page.tsx; workspace shell -> components/app-shell.tsx; service card/collection -> components/service-collection.tsx and app/app/page.tsx; workspace/analytics palette and layouts -> globals.css/integration.css; investigation-console -> components/evidence-explorer.tsx and the existing investigation-panel.tsx; KPI availability presentation -> components/telemetry-availability.tsx. components/status-badge.tsx uses existing Badge. Added /app/services/[serviceId]/page.tsx maps to real Service UUIDs. No design fixture types or localStorage store ship.

**Reused existing operations:** api.ts changes only add supported incident page/severity query arguments. AuthProvider is mounted; failed sign-out now remains a visible failure instead of clearing local state. Existing login/register, onboarding create/verify, incident lifecycle, deployment context, trace viewer, runbook upload/search/delete/reindex, proposal approve/reject, outbox reads/dispatch, and simulation start/reset/execute/recovery calls remain. Proposal native dialog shows the existing immutable_parameters and full parameters_hash. Simulation execution details now reload through the existing read endpoint.

**Replaced:** static public page, hardcoded healthy shop-api overview, incident feed/detail presentation and investigation/evidence markup. Existing URLs, API contracts, backend files, migrations, Python lockfile, Docker builds/commands, Phase 7 browser security/persistence assertions and all backend tests are preserved.

**Excluded intentionally:** design project/workspace demo data and local store, fictional telemetry/hypotheses/citations/actions, synthetic TimeSeries adapter, optional unused chart component, local project creation, Heron branding, global cursor/route curtain/Lenis clock, GSAP runtime, reference media/research screenshots/videos, design lockfile, node_modules/build output and Git history. Native transform entrances retain scroll storytelling without low-opacity text or global navigation interception. This is a deliberate adapted visual integration, not pixel-for-pixel reproduction.

**Dependency changes:** runtime pins unchanged. Development-only @axe-core/playwright 4.13.0 and axe-core 4.13.0 added to the existing workspace/lockfile; no dependency upgrades. Local fonts add no runtime package or third-party browser requests.

## Data semantics, boundaries and limitations

- Applications are registered monitored services; workspace is the authenticated organization. Registration active is not equivalent to telemetry healthy. Connection freshness is not provided by the API. Per-card incident counts explicitly refer to the latest returned page; feed pagination remains server-backed.
- No safe dashboard time-series endpoint exists. Request rate, weighted error rate, p95/p99, SLI and error budget remain unavailable. No fake chart, inferred healthy badge, direct browser telemetry URL or infrastructure credential is used. Trace/deployment/evidence functionality remains available through FastAPI.
- All incident deep links preserve real UUIDs. Times on new incident/service/evidence surfaces are explicitly UTC. Incident duration is labeled as measured at page load, not a live clock.
- Run history supplies persisted mode because the existing run-detail serialization omits it. Offline output is labeled TEST DOUBLE; pending runs show no final diagnosis. Citations must match selected run/org/service records; unresolved references remain visible. Backend validation remains authoritative, and provenance is not labeled proof of causation.
- Approval, execution and recovery remain separate real backend operations. Exact payload, role, staging/development, idempotency and expiry enforcement remain unchanged. No backend security change was necessary or made. The gate's connector policy explicitly allows local demo hosts; metadata addresses remain blocked and are verified separately.
- Native polling remains at two seconds with cleanup and stale-response suppression for selected run requests. No SSE API contract was added.
- Tests using mocked completed evidence are explicitly named and labeled; they establish frontend citation behavior only. Real browser tests establish session, service/incident persistence and staging action behavior against disposable infrastructure. They do not establish live AI quality, hosted CI, full observability-chain accuracy or production deployment.
- Firefox, Safari, physical devices and assistive-technology sessions remain unverified. Full live analytics awaits approved aggregation APIs. Exact original cinematic timing remains a possible frontend refinement; native navigation and readability take priority.

## Decision summary

| ID | Choice and reason | Rejected alternative / accepted trade-off |
|---|---|---|
| ADR-028 / DEC-339 | Selective presentation migration into existing app | Whole-app replacement/history merge loses real behavior |
| DEC-340 | Organization/services are the workspace/app model | New Project entity unjustified; health remains unknown |
| DEC-341 | Existing UUID routes and bounded pagination | No unbounded reads or invented complete service counts |
| DEC-342 | Light semantic palette, readable type, original SVG/local licensed fonts | Wholesale CSS/reference-media copying rejected |
| DEC-343 | Native motion/scroll/navigation, full-opacity text | Simplified cinematic fidelity; no global GSAP/Lenis runtime |
| DEC-344 | Unsupported metrics explicitly unavailable | No fake series or browser infrastructure access |
| DEC-345 | Persisted run history and scoped citation matching | No synthetic evidence or confidence percentage |
| DEC-346 | Existing auth/actions, native review dialog | No local authorization or fake approvals |
| DEC-347 | Extend the isolated gate and retain its assertions | No screenshot-only proof or weakened security tests |
| DEC-348 | Empty onboarding fields and explicit environment | No accidental hardcoded production service registration |
| DEC-349 | Honest simulation state and persisted execution detail | No recovery claim from an empty run list |
| DEC-350 | Exact development-only axe integration | Automated coverage adds packages; manual accessibility remains separate |

Reused ADR-023 (sessions, tenant scope, RBAC), ADR-027 (staging control), DEC-335–338 (CSRF/session forwarding and isolated persistence/scheduler gate). Debugging entries BUG-20261014-001/002 record actual failures and repairs. No unapproved architecture deviation, commit, push, merge or deployment.


## Phase 8.1 correction notice — 2026-10-14
This report preserves Phase 8 functional evidence. Its selective visual integration was rejected by the explicit Phase 8.1 request; ADR-029 supersedes the visual strategy. Current source mapping, Docker diagnosis, rendered comparison and verification live in [Phase 8.1 visual fidelity report](../PHASE_8_1_VISUAL_FIDELITY_REPORT.md). The earlier build/browser pass alone did not establish approved-design fidelity.
