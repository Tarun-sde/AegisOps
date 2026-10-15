# Phase 8.1 — Visual fidelity restoration

Status: VERIFIED LOCALLY — Phase 8.1 implementation, rendered comparison and functional/security regression gates completed on 2026-10-14. Branch feat/phase8-frontend-integration, main baseline ef374d2562a8c05b5f859fc4c812ff9b13c8f5bc; changes uncommitted. Reference GitHub HEAD f46969734ce644be97003f558bd738dd5e76832f, confirmed 2026-10-14. No push, merge or hosted deployment.

## Root cause and delivery
The initial Compose container contained the Phase 8 source: landing/layout hashes matched and image/tag agreed. A web-only rebuild preserved the mismatch. Phase 8 had reinterpreted the approved design and omitted entire scenes/interactions; functional tests were insufficient evidence of visual fidelity. See [parity audit](PHASE_8_DESIGN_PARITY_AUDIT.md) and BUG-20261014-003.

Reference ran from the untouched committed clone at /tmp/aegisops-design-phase8-20261014 on port 3002. Actual application used the existing Compose environment at port 3000. Rebuild command: `docker compose --profile core up -d --build --no-deps --force-recreate web`. No existing stateful service was recreated and no existing application volume was deleted. The isolated browser gate creates and cleans up its own disposable Compose project/volume. Dedicated Visual QA organization/service created through ordinary authenticated registration/service APIs; only its incident/run/evidence fixture records were seeded for presentation review. They are marked explicit QA/offline/inconclusive, never actual telemetry or a live model result. Private auth files stay outside Git under /tmp with mode 0600.

## Source-to-destination map

| Committed reference source | Integrated path under apps/web/app | Adaptation |
|---|---|---|
| components/home-page.tsx | components/marketing/home-page.tsx | Original section order, model workflow, platform/why/use-case scenes; operational AegisOps copy |
| components/hero.tsx; lib/geometry.ts | components/marketing/hero.tsx; geometry.ts | Original drag overlap/coordinates/issue selection and entrance; illustrative signal labels |
| components/artwork.tsx | components/marketing/artwork.tsx | Original elevation, floor plan, pavilion, terrain and drafting marks |
| components/scene-entrances.ts; lib/motion-scenes.ts | components/marketing/scene-entrances.ts; motion-scenes.ts | Original GSAP scene choreography and cleanup |
| components/site-shell.tsx | components/marketing/site-shell.tsx | Preloader, header, route curtain, cursor and shared clock; real routes, marketing-only Lenis/cursor/preloader |
| components/footer.tsx | components/marketing/footer.tsx | Original ink reveal and pointer lens wordmark; AegisOps content/links |
| components/product-preview.tsx | components/marketing/product-preview.tsx | Layered public illustrative preview; no authenticated data/actions, explicit preview label |
| components/workspace/workspace-shell.tsx | components/app-shell.tsx | Original sidebar/frame/breadcrumb/collapsed rail/mobile structure; real AuthProvider, service count, signout, full module links |
| components/workspace/selector.tsx | components/selector.tsx | Original keyboard/popover mechanics; current authenticated organization only |
| components/workspace/project-card.tsx, project-collection.tsx | components/service-collection.tsx; app/page.tsx | Original card divisions, service drawings, filter/list/grid toolbar; API service UUIDs and bounded incident-page counts |
| components/workspace/project-visuals.tsx | components/project-visuals.tsx | Original mark/schematic; one registered resource per card, unknown health |
| components/workspace/project-detail.tsx | app/services/[serviceId]/page.tsx | Original detail heading/status/tab hierarchy; real deployment context |
| components/workspace/analytics/analytics-dashboard.tsx | components/service-analytics.tsx | Six KPIs, period/service toolbar, selected metric/chart frame, service table, incident register; unsupported values unavailable |
| components/workspace/analytics/detail-dialog.tsx | components/detail-dialog.tsx | Native read-only service details drawer with focus restoration |
| components/workspace/analytics/investigation-console.tsx | app/incidents/[incidentId]/page.tsx, investigation-panel.tsx; components/evidence-explorer.tsx | Structured incident header, hypothesis/timeline grid, full-width evidence tabs and governed next steps; real persisted runs/citations |
| app/globals.css, app/projects/workspace.css, analytics.css | globals.css, workspace.css, analytics.css | Reference base and Phase3 readable operational styles, licensed existing local fonts |
| No direct reference: existing real modules | login, onboarding, runbooks, proposals, simulation-lab; integration.css | Shared design geometry/forms/dialogs/status tokens, existing API operations retained |

Removed the superseded simplified landing/artwork/telemetry components after verifying no remaining callers. No demo store, synthetic telemetry adapter, fictional project schema, reference media, design lockfile or Git history is imported. No backend, agent, worker, infrastructure, migrations or Python dependency changes.

## Motion, CSS and dependency decisions
ADR-029 and DEC-351–358 supersede the selective visual rewrite. Exact reference-lock runtime dependencies restored: gsap 3.15.0, @gsap/react 2.1.2, lenis 1.3.26. Installed package README/types reviewed; reduced-motion matchMedia, GSAP contexts, ticker/event cleanup retained. Native operational scrolling avoids interference with forms and modal focus. Shared transition curtain remains. No performance improvement is claimed.

Replaced the old global header/main/footer and typography with reference base CSS. Root imports reference base → workspace → analytics → scoped compatibility. Real pages own main; shell owns breadcrumb/sidebar; no duplicate marketing header in workspace. Reference Phase3 16px body/14px metadata remains; essential marketing controls are raised to 14px and low-contrast muted/orange text darkened. Decorative drafting annotations keep reference scale. These accessibility differences preserve composition and are intentional (DEC-358).

## Intentional product differences
- Workspace means authenticated organization; card means registered service. UUID routes and existing authorization remain canonical. Current API does not provide an approved active-organization switching operation; selector truthfully identifies the active organization. Favorites are session presentation only.
- Live series, percentiles, SLI and budgets are unavailable. Full chart composition remains, metric selection works, and empty panels explain the absent API. No invented tooltip values or synthetic series. Original synthetic time-series adapter is excluded deliberately.
- Extra real module navigation, signout, lifecycle, execution/recovery, deployment/traces and full immutable approval details remain. Variable real content affects density and wrapping.
- Marketing illustrations are conceptual. Public preview is labeled, operational records come through the existing API, and QA data is confined to its named organization. No public dangerous simulation controls.
- Original architectural drawings and composition retained; industry claims and external Heron destinations replaced by accurate AegisOps terminology/routes.

## Evidence and verification checkpoints
Baseline images: artifacts/phase8-1/{reference,before}/. Corrected intermediate captures: artifacts/phase8-1/after/. Matched-state six-viewport matrix: artifacts/phase8-1/parity/{viewport}/{reference,actual}/. Exact screenshot filenames and geometry/console results are generated by apps/web/scripts/design-parity.mjs, run with private PHASE81_AUTH_STATE and PHASE81_QA_FILE inputs. Reference data is fictional; actual QA records are persisted explicitly labeled fixtures.

- Initial corrected Docker image built and rendered without page errors.
- `make check` passed after imported TypeScript/lint corrections; repeated static gate passed.
- `make test`: 158 Python passed, 6 integration tests deselected, 132 warnings; Express 1 passed. Log /tmp/aegisops-81-test.log. No separate full PostgreSQL concurrency rerun claimed.
- First `make browser`: 9 passed / 8 failed in 1.3m, project aegisops-browser-d540a510. All eight original tests and the new motion test passed. Eight expanded tests failed at shared login helper’s removed .ws-org selector, before their workflows; repaired against the actual authenticated breadcrumb.
- Second gate: 15 passed / 2 failed. Onboarding’s exact title assertion replaces an ambiguous link regex; actual footer contrast findings fixed without disabling axe.
- Third gate: 16 passed / 1 failed. All accessibility checks passed; populated proposals overflowed at 768px. Restored ws-content sizing and wrapping, retaining full immutable IDs/hashes. The next gate found the loaded Simulation Lab hash wrapping issue described below.
- Matched mobile review caught the missing reference ws-summary-note responsive class and incorrect search wrapper. Restored both and removed intermediate overrides. Added actual card captures and direct reference-versus-actual hero/sidebar/card width assertions, so a generic grid override cannot silently pass as parity.
- Docker axe findings and repairs are recorded in BUG-20261014-003; the final nine-route scan has zero serious/critical findings. Automated audits do not certify all WCAG criteria.
- Final image/build identity and final gate results are recorded below.

## Remaining verification
Cross-browser Safari/Firefox, physical devices, assistive-technology sessions, hosted CI and live-model quality are not established. No measured performance benchmark, live analytics capability or production readiness claim. Phase 9 remains not started.


## Final Docker identity
The delivered web container uses image `sha256:175cc0163b5d9ec2632cac1c5f1ad001e4e0eaf34c61de7630fc4a7416305b71`, Next build `fHtE5t1qf8t8KXjNtc4nA`. All 49 app-source/package files compared by SHA-256 match the working tree; manifest: `artifacts/phase8-1/container-source-manifest.json`. Runtime URL is `http://127.0.0.1:3000`. The image build ran the production Next compiler/type checker successfully. Main repository backend/worker/package/infrastructure diff is empty. The reference clone still has a clean Git status.

## Reproducing the rendered comparison
With a private normal-session storage state and a JSON file containing the authorized QA service/incident IDs, run from the main repository:

```sh
PHASE81_AUTH_STATE=/path/to/private-auth.json PHASE81_QA_FILE=/path/to/private-qa.json node apps/web/scripts/design-parity.mjs
```

Start the untouched design production server on port 3002 and the real Compose web on port 3000 first. The script captures initial preloader, hero/drag/inspection, all four workflow phases, platform tabs, layered preview, ink/footer lens, workspace grid/card/list/collapse or mobile drawer, service/selected metric/chart/table/register, investigation/hypotheses/timeline/evidence. It asserts rendered interaction changes, absence of the old header, selected KPI state, explicit absent-series explanation, no page errors/incident overflow, and reference-matching hero/sidebar/card widths. A screenshot is not an assertion of live metrics or diagnoses.

### Representative visual evidence
The full matrix is under `artifacts/phase8-1/parity/`; `index.html` provides a local side-by-side review. Individual matched examples:

| Surface | Reference | Real Docker application |
|---|---|---|
| Hero | [1440×900](../artifacts/phase8-1/parity/1440x900/reference/hero.png) | [1440×900](../artifacts/phase8-1/parity/1440x900/actual/hero.png) |
| Pinned Advise scene | [1920×1080](../artifacts/phase8-1/parity/1920x1080/reference/workflow-advise.png) | [1920×1080](../artifacts/phase8-1/parity/1920x1080/actual/workflow-advise.png) |
| Workspace card | [1920×1080](../artifacts/phase8-1/parity/1920x1080/reference/workspace-card.png) | [1920×1080](../artifacts/phase8-1/parity/1920x1080/actual/workspace-card.png) |
| Analytics | [1920×1080](../artifacts/phase8-1/parity/1920x1080/reference/analytics-chart.png) | [1920×1080](../artifacts/phase8-1/parity/1920x1080/actual/analytics-chart.png) |
| Investigation | [1440×900](../artifacts/phase8-1/parity/1440x900/reference/hypotheses-timeline.png) | [1440×900](../artifacts/phase8-1/parity/1440x900/actual/hypotheses-timeline.png) |
| Footer lens | [1440×900](../artifacts/phase8-1/parity/1440x900/reference/footer-lens.png) | [1440×900](../artifacts/phase8-1/parity/1440x900/actual/footer-lens.png) |
| Mobile workspace | [390×844](../artifacts/phase8-1/parity/390x844/reference/workspace-grid.png) | [390×844](../artifacts/phase8-1/parity/390x844/actual/workspace-grid.png) |

These are local ignored artifacts, not committed screenshots or hosted CI evidence. Baseline/intermediate images remain labeled separately. No pixel-percentage parity score is claimed: real records, operational copy, additional module navigation and accessible control contrast intentionally differ.


## Final acceptance results — 2026-10-14

| Gate | Actual result | Evidence under artifacts/phase8-1/ |
|---|---|---|
| `make check` | PASS, exit 0: Ruff/lint/format, mypy, ESLint, Prettier and workspace TypeScript checks | logs/aegisops-81-check-complete.log |
| `make test` | PASS, exit 0: 158 Python tests, 6 deselected, 132 warnings; Express 1 passed | logs/aegisops-81-test.log |
| `make browser` | PASS, exit 0: 17 Playwright tests in 41.3s; isolated project aegisops-browser-83700dc4 | logs/aegisops-81-browser-complete.log |
| Scheduler/expiry | PASS: real fault active before TTL, worker resets it without a request, repeated cleanup idempotent, one expiry/outbox record, one non-root Beat scheduler | Same browser log and ../aegisops-browser-83700dc4/watchdog.txt |
| Production Docker build | PASS, only main web rebuilt/recreated; final source manifest matches 49 runtime source/package files | logs/aegisops-81-docker-complete.log; container-source-manifest.json |
| Paired visual states | PASS at 1920×1080, 1440×900, 1440×700, 1024×768, 390×844, 375×812; 284 images across reference/actual | parity/ and logs/aegisops-81-parity-final.log |
| Delivered-image refresh | PASS: actual states recaptured after the final scoped Simulation Lab CSS fix; all six sets have zero page errors/incident overflow; hero/sidebar/card width differences exactly 0px against unchanged reference | logs/aegisops-81-parity-delivery.log; parity/measurements-actual.json; parity/delivery-comparison.json |
| Docker accessibility | PASS: nine routes, zero serious/critical WCAG-tagged axe findings | axe-final.json; logs/aegisops-81-axe-complete.log |
| Diff/source hygiene | PASS: git diff --check; design clone clean; no backend/agent/worker/infrastructure/migration changes | Main/reference Git status inspected locally |

Browser coverage includes real service registration and refresh, filters/list/detail, denied metadata connector target, persisted lifecycle and offline investigation, 401 and CSRF/403 boundaries, scoped citation behavior (explicit mocked evidence), approve/reject immutable payloads, separate staging execution, duplicate execution response, independent recovery, mobile logout, reduced motion, hero drag/phase selection, route motion cleanup, mobile drawer focus and approval dialog wrapping/focus at 375/768px. The final tablet layout test waits for six catalog controls and the persisted execution result, fixing the earlier API-arrival race. No live model inference was claimed.

The fourth attempt exposed a loaded Simulation Lab plain-text hash overflow (16 passed / 1 failed). Scoping wrapping to that page fixed it; the final fifth gate above passed all 17. Failed attempts are retained in the journal/logs. No assertion was removed to get a pass.

Rendered review confirmed full-width elevation and drag state, the original pinned drawing scenes, layered previews and footer lens, architectural sidebar/grid/list/card geometry, full six-KPI analytics composition with honest unavailable series, hypothesis/timeline/evidence structure, and mobile workspace/drawer/evidence layouts. Long real names and full payload details wrap; sample counts/content and unsupported live charts intentionally differ. Screenshots plus geometry/interaction assertions support local fidelity, not pixel identity or universal accessibility certification.

## Decision completion and deviations
ADR-029 and DEC-351–358 are VERIFIED LOCALLY for this implementation:

| ID | Choice and reason | Rejected option / cost |
|---|---|---|
| DEC-351 | Restore actual committed compositions to meet the explicit correction | Selective visual rewrite failed fidelity; source reuse increases presentation code |
| DEC-352 | Exact original GSAP/React/Lenis pins reproduce choreography and cleanup | Native approximation rejected; added runtime dependencies |
| DEC-353 | Reference CSS/shell geometry with marketing-only clock/preloader/cursor | Global generic styling and duplicate headers rejected; scoped compatibility remains |
| DEC-354 | Original workspace/card/search structure backed by real organizations/services | Demo store/new Project model rejected; current-org-only selector and session favorites |
| DEC-355 | Keep full analytics composition and explicit missing data | Fabricated live series and removing the chart frame rejected; live plots remain unavailable |
| DEC-356 | Real Compose delivery plus matched viewport states and isolated regression | Build-only/screenshot-only acceptance rejected; local QA fixtures and test runtime required |
| DEC-357 | Original investigation composition over persisted scoped evidence | Fictional diagnoses/actions rejected; variable real content changes density |
| DEC-358 | Preserve composition while making essential controls readable and correcting contrast | Tiny essential controls or wholesale illustration enlargement rejected; intentional typography/color differences |

Reused ADR-023/027 and DEC-335–338 retain session, bounded execution/recovery and scheduler boundaries. ADR-028 / DEC-339–350 retain functional integration, API mapping, evidence semantics, unavailable-data honesty and regression tooling; only the selective visual/native-motion portions are superseded by ADR-029. Specific retained decisions: DEC-340/341 organization/service/route mapping; DEC-344 unavailable metrics; DEC-345 persisted investigation/evidence; DEC-346/348/349 auth/approval/execution safeguards; DEC-347/350 verification/axe. No new architectural/security deviation requires approval: the visual reversal was explicitly requested by the user. Phase 9 remains NOT STARTED. No commit, push, merge or deployment performed.

Verified interview lesson: source-matching widths and rendered state review caught omissions that passing builds and functional tests missed; waiting for loaded data exposed a real tablet hash-wrapping bug. Functional, visual, delivery and data-truthfulness checks are separate evidence obligations.
