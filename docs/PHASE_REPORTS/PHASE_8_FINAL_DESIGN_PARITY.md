# Phase 8 — Final source-first design parity

Status: VERIFIED LOCALLY — implementation and final comparison reviewed; awaiting user visual acceptance. No numerical 99% claim. Phase 9 is not unlocked by this report.

## Baseline and scope

Reference `Tarun-sde/AegisOps-Design` at `f46969734ce644be97003f558bd738dd5e76832f`, verified against remote HEAD. Main branch `feat/phase8-frontend-integration`, baseline HEAD `ef374d2562a8c05b5f859fc4c812ff9b13c8f5bc`. The baseline included substantial uncommitted Phase 8 work. Preserved checkpoint, binary patch and status live under `artifacts/final-design-parity/`. The agent made no commit, reset, push, merge or deployment. During the task an externally created local commit `7e8b41cb84c5bb4ca8ae9828b1bea0bd567f524b` appeared (author/committer Tarun-sde); it was preserved. Final report/capture refinements are subsequent working-tree changes.

[Source migration matrix](../DESIGN_PARITY_SOURCE_MATRIX.md) maps all 20 requested source files, dependencies and API boundaries. [Animation matrix](../DESIGN_PARITY_ANIMATION_MATRIX.md) records source reuse and intentional differences. DEC-377–383 govern this correction; DEC-365 governs completed-scene navigation. ADR-023/027/028 security and ADR-029/030 presentation remain applicable. No backend architecture deviation.

## Implemented changes

- Source `globals.css`, hero hierarchy/geometry, drag selection, entrance timeline and caption composition restored. Original operational vector artwork occupies the reference envelopes; building subjects are removed. Mobile selected state keeps the source drawing height and adds an in-flow sample explanation.
- Complete source landing sequence, one continuous workflow drawing, exact original workflow/feature timeline placements, seven-window product preview, five feature layers, preloader, section entrances, ink reveal and footer lens restored. New operational paths replace only domain-specific targets. Local sample approval cannot execute an action.
- Source workspace collection heading/summary and distinct grouped-list/grid-card structures restored around real service and incident APIs. Service analytics/investigation/evidence interfaces retain source-derived structures and real authorized data. Missing time series remain explicitly unavailable.
- Exact localhost browser API fallback fixes login-cookie continuity between browser requests and server-rendered pages. Explicit API settings remain authoritative; no cookie/CSRF/RBAC weakening.

Principal paths: `apps/web/app/components/marketing/`, `globals.css`, `brand.css`, `components/service-collection.tsx`, `app/page.tsx`, `lib/api.ts`, relevant browser tests, and `scripts/final-parity.mjs`. Earlier uncommitted operational integrations are retained.

## Evidence and checks

Artifacts are local and ignored by Git:

| Gate | Actual result | Evidence |
|---|---|---|
| `UV_NO_SYNC=1 make check` | Exit 0: Ruff, format, mypy, ESLint, TypeScript | `artifacts/final-design-parity/check-final.log` |
| `UV_NO_SYNC=1 make test` | 158 Python passed, 6 deselected, 132 warnings; Express 1 passed | `test.log` |
| First full browser gate | 23 passed, 2 motion endpoint failures; fixed under DEC-365 without loosening assertions | `browser.log` |
| Corrected full browser gate | 25 passed; real unattended expiry, idempotency and non-root Beat dispatch passed | `browser-final.log` |
| Origin/mobile browser gate | 25 passed (1.3m), scheduler/expiry/idempotency passed | `browser-final-origin.log` |
| Delivered list/target browser gate | 25 passed (1.2m), scheduler/expiry/idempotency passed | `browser-delivered.log` |
| `docker compose build web` | Exit 0; only existing web recreated | `docker-build-final.log` |
| Docker/source hash comparison | 62 app/package/public asset files, zero mismatches | `docker-source-verification.json` |
| Actual localhost login + full reload | Authorized synthetic service visible after SSR reload | `localhost-login.log` |
| Five viewport comparison | 435 PNGs, 10 complete source/actual result sets; all dimensions validated | `gallery/index.html`, `gallery/results-*.json` |

Delivered image: `sha256:8d3b117c5d6a47d1cbc539f687a08bc39a307084e65dae3627429bfc8fe63436`. Existing main database volumes preserved. Existing stopped core containers were restarted after an environment interruption. Only the synthetic QA user's credentials were regenerated; private credentials/storage state are excluded from artifacts and Git.

## Visual review and deliberate differences

Review compares exact viewport sizes, source and Docker, hero entrance event checkpoints, settled drawing, drag/selection, four phases and reversals, five feature layers, sample approval/hover, workspace grid/list/hover, service analytics, incident register, investigation and evidence selection. Browser frame scheduling can vary by tens of milliseconds; measured entrance offsets are retained in JSON rather than claiming frame-perfect timing.

Before image: `artifacts/final-design-parity/before-hero.png`. Side-by-side gallery: `artifacts/final-design-parity/gallery/index.html`, served locally at `http://localhost:3003`. Reference is `http://localhost:3002`; delivered application is `http://localhost:3000`.

Intentional differences: AegisOps identity/copy and original software artwork; five meaningful public navigation destinations; readable essential controls/contrast; keyboard/touch and native dialog focus; selected incident summary; `.85` completed-scene click destination under DEC-365 (reference `.5`), preserving scroll durations/easing; real authenticated data and UUID routes; unavailable charts where API series do not exist. Gallery account/data is synthetic and explicitly labeled, not live infrastructure or an AI-quality claim.

Resolved during review: alternate hero/workflow compositions, independent scene charts, reduced preview stacks, unrelated use-case graphic, desktop click endpoints, mobile headline wrapping, selected-mobile drawing expansion, sample payload wrapping, and localhost/127.0.0.1 session split. Final five-viewport review is complete, including 375px narrow-phone states. No unresolved P0/P1 defects were observed in the reviewed captures. The repaired six-cell service list now uses the source desktop/mobile grid; missing collection tween targets are guarded. The real incident page includes lifecycle controls and persisted-run selection before the source-derived hypothesis/evidence region; these functional controls intentionally add vertical space.

## Security, limits and lessons

Direct source-motion/CSS diff is preserved as `artifacts/final-design-parity/source-motion-css.diff`.

No backend permissions or action catalog changed. Marketing remains local and makes no account API calls. Browser tests cover tenant-scoped evidence, real persisted lifecycle, immutable proposal review, staging execution and independent recovery, session invalidation, denied roles and CSRF rejection. One evidence test uses explicit mocks; synthetic persisted gallery data is not a live-model investigation. No real remediation invoked by gallery interactions.

Verified engineering lessons: preserving source structure and timelines is distinct from matching colors; final child animation states require explicit assertions; browser and SSR must share the advertised local hostname; test success is separate from visual acceptance. No hosted CI, deployment, production telemetry, cross-browser, performance or numeric similarity claim.


## Final visual evidence and remaining differences

All five actual viewport result files report zero page errors, zero console warnings and zero horizontal overflow. The unmodified reference emits 20–22 existing GSAP missing-target warnings per full route run; these are recorded separately. Actual home and incident axe audits at 1440px report zero serious/critical violations; the 25-test browser gate additionally audits core screens and responsive controls. This is not a claim that every accessibility criterion or browser engine was tested.

| Viewport | Hero envelope | Drawing/caption split | Review |
|---|---|---|---|
| 1920×1080 | Exact measured match | Exact to rounding | Reviewed |
| 1440×900 | Exact measured match | Exact to rounding | Reviewed |
| 1024×768 | Exact measured match | Drawing 18.94px shorter; caption taller | P2 text/control wrapping difference |
| 390×844 | Exact measured match | Exact to rounding | Reviewed |
| 375×812 | Exact measured match | Drawing 16.89px shorter; caption taller | P2 narrow-copy wrapping difference |

The original and actual sidebar widths are equal (240px at 1440px); first-card width is also equal (362.66px). Contents, record counts, text wrapping and resulting heights differ. A single real QA service does not reproduce a three-card fictional reference dataset. The selected hero summary adds space, operational review controls add rows, and readable mobile navigation may wrap; these deliberate differences remain visible rather than being hidden to improve screenshots.

Screenshots include source/Docker default and mid-entrance, drag/selected, four phases plus reverse/initial stage, all five preview compositions, mobile completed scenes, approval/hover, menu/footer lens, grid/list/card hover, service/analytics/incidents, investigation and selected evidence. Supplemental list captures normalize page scroll to the top so different record counts do not create misleading vertical alignment. Gallery PNG dimensions were independently checked against all five requested viewports.

Reproduction: `PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/ms-playwright" node apps/web/scripts/final-parity.mjs` and `... node apps/web/scripts/parity-interactions.mjs`. The primary capture requires the ignored private synthetic QA metadata/storage-state files, not committed credentials. Both reference and Docker must be running; local gallery service is a convenience and may need restarting after the machine/session stops.

Decision evidence: DEC-377–383 VERIFIED locally with stated visual/data limitations; DEC-365 reused for finished click states. No architectural/security deviation approval is requested. Final aesthetic acceptance belongs to the user reviewing the original, Docker app and gallery side by side.
