# Final source migration matrix

Reference: `Tarun-sde/AegisOps-Design`, `f46969734ce644be97003f558bd738dd5e76832f`, checked against remote HEAD 2026-10-15. Local reference generated files (next-env.d.ts and Next.js AGENTS.md) are preserved; reference implementation is unchanged. Main branch `feat/phase8-frontend-integration`, baseline HEAD `ef374d2562a8c05b5f859fc4c812ff9b13c8f5bc`; substantial pre-existing uncommitted work preserved in `artifacts/final-design-parity/working-tree-checkpoint.tar.gz` and baseline.patch. No commits or resets.

Decisions: DEC-377–383; ADR-029/030 presentation, ADR-023/027/028 security. Status: IMPLEMENTED; source comparison and functional gates verified locally, final five-viewport visual review complete; user acceptance pending.

| Original source | Destination | Structure / styles / animation / interaction | Content and API adaptation |
|---|---|---|---|
| `components/hero.tsx` | `apps/web/app/components/marketing/hero.tsx` | Source hierarchy, classes and motion ported; domain text/SVG targets adapted | Public illustrative content only; no API calls |
| `components/home-page.tsx` | `apps/web/app/components/marketing/home-page.tsx` | Source hierarchy, classes and motion ported; domain text/SVG targets adapted | Public illustrative content only; no API calls |
| `components/artwork.tsx` | `apps/web/app/components/marketing/system-artwork.tsx` | Source hierarchy, classes and motion ported; domain text/SVG targets adapted | Public illustrative content only; no API calls |
| `components/scene-entrances.ts` | `apps/web/app/components/marketing/scene-entrances.ts` | Source hierarchy, classes and motion ported; domain text/SVG targets adapted | Public illustrative content only; no API calls |
| `components/site-shell.tsx` | `apps/web/app/components/marketing/site-shell.tsx` | Source hierarchy, classes and motion ported; domain text/SVG targets adapted | Public illustrative content only; no API calls |
| `components/product-preview.tsx` | `apps/web/app/components/marketing/product-preview.tsx` | Source hierarchy, classes and motion ported; domain text/SVG targets adapted | Public illustrative content only; no API calls |
| `components/dashboard-page.tsx` | `apps/web/app/components/marketing/platform-page.tsx` | Source hierarchy, classes and motion ported; domain text/SVG targets adapted | Public illustrative content only; no API calls |
| `components/footer.tsx` | `apps/web/app/components/marketing/footer.tsx` | Source hierarchy, classes and motion ported; domain text/SVG targets adapted | Public illustrative content only; no API calls |
| `lib/motion-scenes.ts` | `apps/web/app/components/marketing/motion-scenes.ts` | Source hierarchy, classes and motion ported; domain text/SVG targets adapted | Public illustrative content only; no API calls |
| `lib/geometry.ts` | `apps/web/app/components/marketing/geometry.ts` | Source hierarchy, classes and motion ported; domain text/SVG targets adapted | Public illustrative content only; no API calls |
| `app/globals.css` | `apps/web/app/globals.css` | Source hierarchy, classes and motion ported; domain text/SVG targets adapted | Public illustrative content only; no API calls |
| `components/workspace/workspace-shell.tsx` | `apps/web/app/components/app-shell.tsx` | Existing source-derived shell/style/interaction port retained around real adapters | Real authorized service/incident/run adapters; no demo store |
| `components/workspace/project-card.tsx` | `apps/web/app/components/service-collection.tsx` | Existing source-derived shell/style/interaction port retained around real adapters | Real authorized service/incident/run adapters; no demo store |
| `components/workspace/project-collection.tsx` | `apps/web/app/components/service-collection.tsx` | Existing source-derived shell/style/interaction port retained around real adapters | Real authorized service/incident/run adapters; no demo store |
| `components/workspace/project-detail.tsx` | `apps/web/app/app/services/[serviceId]/page.tsx` | Existing source-derived shell/style/interaction port retained around real adapters | Real authorized service/incident/run adapters; no demo store |
| `components/workspace/analytics/analytics-dashboard.tsx` | `apps/web/app/components/service-analytics.tsx` | Existing source-derived shell/style/interaction port retained around real adapters | Real authorized service/incident/run adapters; no demo store |
| `components/workspace/analytics/time-series.tsx` | `apps/web/app/components/service-analytics.tsx` | Chart frame retained; synthetic series intentionally omitted | No scoped aggregation endpoint; explicit unavailable state under DEC-344/355 |
| `components/workspace/analytics/investigation-console.tsx` | `apps/web/app/app/incidents/[incidentId]/investigation-panel.tsx` | Existing source-derived shell/style/interaction port retained around real adapters | Real authorized service/incident/run adapters; no demo store |
| `app/projects/workspace.css` | `apps/web/app/workspace.css` | Existing source-derived shell/style/interaction port retained around real adapters | Real authorized service/incident/run adapters; no demo store |
| `app/projects/analytics.css` | `apps/web/app/analytics.css` | Existing source-derived shell/style/interaction port retained around real adapters | Real authorized service/incident/run adapters; no demo store |

Dependencies: original Selector, project-visuals, DetailDialog and dialog focus helpers map to existing components of the same names. Original lib/demo/store, projects and telemetry fixtures are excluded from authenticated code. Existing app/lib/api.ts and auth-context.tsx remain authoritative adapters. No Project entity or backend schema change.

CSS: globals.css starts again from the committed original (font names and entrance session namespace adapted). workspace.css/analytics.css retain source-derived application styles; integration.css retains essential readable controls/contrast and operational compatibility. brand.css is reduced to explicit brand/accessibility differences. No new dependency or token-system rewrite.

SVG: system-artwork.tsx has original operational paths within original drawing envelopes, structural groups, dimension lines, annotations, markers and continuous incident composition. No building artwork reused. Mark and service schematic identity remain AegisOps. The original preview layer relationships and seven-window stack are restored. Footer wordmark lens and ink reveal use original timing.

Real API mapping: organization/session→getMe; collection→getServices/getIncidents; detail→getService; analytics→persisted incidents plus explicitly unavailable time series; investigation→listIncidentInvestigations/getInvestigation/evidence reads; review/execution/recovery→existing backend operations unchanged. Service UUID routes, CSRF and authorization remain intact.

Deliberate differences: five meaningful public navigation destinations replace six prototype destinations; readable essential controls and contrast; brand/copy; original operational artwork; selected-hero detail summary; real data availability, authorized controls and UUID routes. Comparison evidence and remaining defects belong in the phase report.


Detailed reuse boundaries:

- Hero: original DOM, 1000×620 envelope, clip/stroke/annotation timeline and drag calculations. Original SystemDrawing replaces building paths; keyboard markers and in-flow incident summary are accessibility/content additions. Mobile summary preserves original drawing height.
- Home: original ordered section tree and pinned ModelWorkflow; one 700×640 IncidentPlan replaces FloorPlan. ServiceFabric uses the original 800×800 perspective envelope. Technology strip retains actual product icons. Content is concise and illustrative.
- Motion scenes: direct source diff is limited to two route-path morph coordinates and one renamed SVG guide selector; all ease/duration/stagger/placement statements remain. Scene entrances differ only in entrance-event/session namespace.
- ProductPreview: original seven-window composition and five scene branches; incident plan, topology and telemetry art replace model/elevation/terrain subjects. Approval card changes local sample state only. Full immutable sample keys wrap without clipping.
- Workspace shell: real organization membership, session and service navigation replace demo workspace store; native focus-trapped dialogs and sidebar remain. Collections now use distinct source grid-card and environment-grouped list DOM rather than cards styled as rows.
- Analytics: source KPI/chart/incident panels retained; missing series are unavailable. The real backend has no populated chart series to justify source demo chart hover/data sliders.
- Investigation: source console hierarchy, timeline and evidence tabs around actual run/evidence APIs; citation validity and organization/service/run bounds remain deterministic. Explicit-mock browser evidence test is labeled; persisted synthetic QA gallery is separate.
- Local origin: DEC-383 uses the exact localhost API fallback on localhost pages, retaining explicit environment settings and 127.0.0.1 elsewhere. This fixes server cookie forwarding after real login; no auth/security policy change.
