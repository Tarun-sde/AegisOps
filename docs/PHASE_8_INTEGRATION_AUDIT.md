# Phase 8 integration audit

Audit date: 2026-10-14. Main HEAD: `ef374d2562a8c05b5f859fc4c812ff9b13c8f5bc`; clean main at task start. Branch: `feat/phase8-frontend-integration`. Design GitHub HEAD and local HEAD: `f46969734ce644be97003f558bd738dd5e76832f`, verified with `git ls-remote`. Local source: sibling `../AegisOps Design`; its uncommitted next-env.d.ts is excluded. Source is read only. A preliminary remote clone completed at the same verified HEAD; it was started under `/tmp/aegisops-design-phase8-20261014` before the sibling checkout was discovered; no design files were written in the application by that clone.

## Current architecture and conflicts

Next.js 16.4.0 / React 19.3.0 App Router under apps/web; api.ts centralizes server cookies and browser CSRF. Server incident reads and client mutations already exist. AuthProvider exists but was not mounted. FastAPI owns organizations/services/incidents/runs/evidence/actions; no persistent Project model. Design /projects routes and localStorage identity cannot become real authorization. Preserve /app routes and incident UUIDs. Existing docs include historical Phase 6/failed-gate snapshots; current Phase 7 state explicitly supersedes them. No architecture conflict requires changing backend.

## Integration matrix

| Design source | Destination / adaptation | Data and restrictions |
|---|---|---|
| artwork.tsx, hero.tsx, home-page.tsx | marketing hero, original architectural SVG, interactive inspection and scroll story | Product illustration only, no operational readings |
| project-visuals.tsx | AegisMark and adapted service schematic | Service UUID/name; no synthetic health |
| workspace-shell.tsx, dialog.ts | shared app navigation, mobile native dialog, focus wrapping | getMe active organization; existing routes |
| project-card.tsx, project-collection.tsx | real service grid/list/search/filter/sort | GET services; no demo store or Project creation |
| workspace.css, analytics.css | scoped presentation tokens, layout and readable panels | 16px body, >=14px metadata, semantic labels |
| analytics-dashboard.tsx | KPI availability panels, incident register | No public time-series API; metrics unavailable |
| investigation-console.tsx | persisted hypothesis/evidence explorer | Authorized run/org/service matches only |
| time-series.tsx | excluded until a real time-series contract exists | tightly coupled to synthetic Bucket/aggregate; no fake chart |
| fonts | local Inter / Geist Mono with bundled OFL | no external font request |

## Route and API mappings

| Route | Existing backend / behavior |
|---|---|
| / | public marketing, links to real login/workspace |
| /login, /onboarding | auth/login, auth/register, services, services/{id}/verify-connection |
| /app | me, services, paginated incidents; selected service cards map to /app/services/{UUID} |
| /app/services/{UUID} | authorized services list resolved by UUID, deployments; analytics unavailable; incident feed remains paginated |
| /app/incidents | paginated incidents with status/severity |
| /app/incidents/{UUID} | incident, events, lifecycle status, deployments, trace viewer, investigations |
| investigation within incident | list/start runs; run detail/events/cancel; evidence embedded in authorized run |
| /app/runbooks | list/upload/delete/reindex/search runbooks |
| /app/proposals | proposals approve/reject with immutable hash; outbox delivery/dispatch |
| /app/simulation-lab | S01–S06 catalog/runs/start/reset/events; execute, execution history, verify-recovery |

No new backend API or Python dependency is planned. Detail run serialization currently omits execution_mode/provider whereas history returns persisted fields; UI should obtain mode from the matching history record, never infer live status. Services.status is registration state, not telemetry health. Incident list defaults to 20 records and lacks service filtering: do not advertise complete per-service counts from a page. There is no dashboard series, SLO, error-budget, or connection-freshness endpoint. Existing trace/deployment evidence remains available through the API, not direct infrastructure access.

## Assets, dependencies, tests

Only original SVG source and licensed fonts are selected. No reference screenshot/video/logo, research directory, demo store, package-lock, build output or Git history is migrated. Native motion avoids extra runtime dependencies. Development-only @axe-core/playwright 4.13.0 is added for the acceptance gate; the root lockfile changes only for this dependency and axe-core. Existing application pins and Docker commands remain. Design tests use fixtures/local browser state; application gate provisions real isolated PostgreSQL/Redis/API/worker/scheduler/shop-api. Keep its UUID persistence and independent denial assertions, extending for integrated UI. Official installed Next docs reviewed for CSS scope, server/client boundaries and pathname navigation.

## Checkpoints and rollback

A audit/baseline -> B shared tokens -> C landing/auth -> D real services -> E incidents -> F evidence -> G safe controls/data gaps -> H regression/visual verification. No commit/push/deploy authorized or performed. Rollback is a reviewed reversal of only integration branch changes; no database migration exists to reverse. Preserve the design working tree. Never reset unrelated user work.

Baseline and final actual gate outcomes are maintained in the Phase 8 report; historical design report results are source evidence, not rerun results.
