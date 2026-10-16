# Phase 8.4 — Professional workspace and application analytics

Status: IMPLEMENTED — VERIFICATION IN PROGRESS. User-requested authenticated redesign; landing and sign-in remain frozen. This follows the final source-parity migration; it does not reopen public design or Phase 9 deployment.

## Scope and source mapping

Approved source: sibling `AegisOps Design`, revision `f46969734ce644be97003f558bd738dd5e76832f`. Existing adapted components are the starting point, not a separate frontend. Typography, original linework, source sidebar/card/row/selector and analytic panel structures are retained. New CSS is prefixed `.workspace` in `apps/web/app/workspace-redesign.css`; existing global styles, root layout, fonts, marketing and sign-in files remain untouched.

| Approved source | Real destination / adaptation |
|---|---|
| `components/workspace/workspace-shell.tsx` | `components/app-shell.tsx`: one Applications destination, organization/account, collapsible rail/mobile drawer, user+org scoped favorite IDs |
| `project-collection.tsx` | `components/service-collection.tsx`, `/app`: exact registered names/UUIDs, search, environment/favorites, name/activity sort, grid/list |
| `project-card.tsx` | Existing source card/row markup plus `application-actions.tsx`: whole-card primary link and independent favorite/context menu |
| `project-visuals.tsx`, `selector.tsx` | Existing source-derived vector inventory, unknown health, accessible selector retained |
| `project-detail.tsx` | `/app/services/[serviceId]`: compact identity, source badges/tabs, real activity |
| `analytics/analytics-dashboard.tsx`, `time-series.tsx` | `service-analytics.tsx`: source KPI/toolbar/chart/legend frame; no demo generator, fake curves or unavailable retention options |
| `analytics/investigation-console.tsx`, `detail-dialog.tsx` | Existing `InvestigationPanel`, `EvidenceExplorer`, `DetailDialog` adaptations retained with real incident/run/evidence IDs; application views reuse the secured console |
| `app/projects/workspace.css`, `analytics.css` | Existing source-derived styles frozen; authenticated refinements in a separate stylesheet |

## Routes and data contracts

- `/app`: Your Applications. `/app/services` redirects compatibly to `/app`.
- `/app/services/[serviceId]?view=overview|analytics|incidents|investigations|evidence|activity`: distinct server-rendered views, refresh/back preserve query context. `incident`, `run` and `page` preserve selected records/pagination where applicable.
- `/onboarding`: visible name/environment/description form, backend creation, collection/detail links, optional original connector probe. Repository omitted because existing create implementation does not persist that input.
- Existing `/app/incidents/[incidentId]` lifecycle/investigation/trace and global governed proposal/remediation routes remain supported.

| UI value | Authorized API / truth boundary |
|---|---|
| Workspace | `/api/v1/me` active organization |
| Application identity | `/api/v1/services`, exact Service name and UUID; no Projects table |
| Active incident count | New nullable ServiceRead aggregate field `active_incident_count`, filled by list_services using one organization-scoped grouped query; excludes resolved/closed |
| Recent activity sort | Service updated_at and `last_incident_at` (latest persisted incident updated_at); no invented telemetry timestamp |
| Application incidents | Existing `/api/v1/incidents?service_id=UUID&page=N`, ownership checked; count and rows scoped before pagination |
| Investigations | Existing incident investigation list/detail, selected incident verified against org/service; canonical console preserves start/cancel and tool audit |
| Evidence | Existing persisted run detail, additional org/service/incident checks; evidence explorer retains provenance/missing/contradictory evidence |
| Activity | Registration plus explicitly selected incident’s persisted events; existing scoped deployment context |
| Performance chart | Unavailable: no authorized service time-series API exists; no synthetic percentages/uptime/curves |

## Decisions and security

DEC-384 freezes public surfaces; DEC-385 corrects server filtering/aggregate counts; DEC-386 defines source-derived collection/navigation and scoped UI preferences; DEC-387 defines truthful analytics and bounded incident-context history; DEC-388 fixes onboarding at its class collision; DEC-389 governs evidence. No new ADR required: existing entities, authentication, permissions, SSRF, evidence and approval/execution boundaries remain unchanged. ADR-023/027/028 and ADR-029/030 remain governing. The user's new authenticated redesign supersedes earlier presentation requirements only within that scope.

Frontend selection is not the authorization boundary. The existing backend tenant context governs every read; foreign/missing service filters return 404, invalid UUID 422, anonymous requests 401. No new arbitrary query/URL/tool execution is introduced. LocalStorage contains UI view preference/favorite IDs only, namespaced by user+organization; no application/incident/evidence database.

## Evidence in progress

Ignored local artifacts: `artifacts/workspace-analytics/`. `baseline.patch` preserves pre-existing working-tree edits. `protected-hashes.json` records approved source/dependencies. `before/` contains landing/sign-in and prior authenticated views at 1920×1080, 1440×900, 1024×768, 390×844, 375×812. Captures use explicit synthetic QA account records, never presented as production evidence.

Targeted API regression: 5 passed, 2 warnings (`api-targeted.log`). Full static, unit/browser, Docker, frozen-pixel, accessibility and visual-review gates pending. No completion or visual-acceptance claim yet.

Unsupported: performance time series and historical comparisons; monitoring health/freshness; automatic telemetry provisioning; exhaustive service-wide proposal/execution timeline. Existing incident-context and global operational tools remain available. Offline run outputs retain explicit labels; no live-model accuracy claim.

## Verification observed before overlapping Phase 8.5 changes — 2026-10-16 reconciliation

The following results belong to the completed Phase 8.4 implementation captured before the subsequently observed Phase 8.5 working-tree changes. They do **not** verify the current combined tree. External commit `36ad2d1` and all newer edits were preserved; this agent did not commit, push, merge or deploy.

| Check | Observed result | Local evidence |
|---|---|---|
| `UV_NO_SYNC=1 make check` | Passed Ruff, mypy, ESLint, formatting and both TypeScript checks after final Phase 8.4 refinement | `artifacts/workspace-analytics/check-final.log` |
| `UV_NO_SYNC=1 make test` | 159 Python passed, 6 deselected, 132 warnings; Express 1 passed | `test.log` |
| First `UV_NO_SYNC=1 make browser` | 25 passed, 2 failed on ambiguous environment select label | `browser.log` |
| Corrected `UV_NO_SYNC=1 make browser` | 27 passed (1.1m); isolated scheduler/expiry/idempotency checks passed | `browser-final.log`, `artifacts/aegisops-browser-c9397589/` |
| Docker builds | API/web build passed; refined web build passed; only changed API/web recreated without removing main database volumes | `docker-build.log`, `docker-build-refined.log`, `docker-refined-up.log` |
| Actual localhost registration journey | Empty → visible form → real backend creation → collection → exact service UUID details passed | `collection-journey.log`, `collection-journey.json` |
| Five-size rendered audit | 45 screen/viewport records; zero page errors, zero horizontal overflow, zero serious/critical axe findings | `after-results.json` |
| Visual gallery | 80 page/viewport sections with before/after where available; approved-source comparison images included | `index.html`, locally served at http://localhost:3004 |
| Frozen landing | All five full-page screenshots pixel-identical | `frozen-comparison.json` |
| Frozen sign-in | Identical geometry/source; final captures differ at 10–21 rounded-input edge pixels, maximum channel delta 2/255. Same-build repeated captures also vary in that region. Strict byte/pixel equality is not claimed | `frozen-comparison.json`, `login-repeat-*.png` |

Reviewed source comparison: retained 240px desktop rail, source grid/card/row linework, typography families and spacing hierarchy. Deliberate differences are exact backend identities, real incident aggregates, sentence-case application headings, supported actions, six URL-backed tabs, compact details and unavailable telemetry. QA fixtures are explicitly synthetic. Desktop collection and evidence plus narrow-phone registration/overview were visually inspected; automated viewport/axe checks cover the full 45-screen set.

Current-state conflict: `PROJECT_STATE.md` still identifies Phase 8.4 verification in progress while its appended Phase 8.5 sections and `docs/PHASE_8_5_COMPLETION.md` claim Phase 8.5 completion. Those later changes overlap authentication, monitoring, metrics, schema, workspace and analytics. The mandatory AGENTS.md instruction to stop/report document conflicts applies; scope clarification was requested before further product edits or certification. Current protected hashes show an additional Phase 8.5 modification to `workspace.css`; no claim is made that the current runtime matches these captures.

Decisions governing this evidence: DEC-384–389; existing ADR-023/027/028 and ADR-029/030. No new ADR or product decision added during reconciliation. Remaining gate: resolve current verification target, then validate that target and its public freeze. Historical verified lesson: service scope must be applied before pagination; marketing class names can hide operational forms; exact accessible names need real browser journeys.
