# Phase 8 design parity audit — before correction

Date: 2026-10-14. Reference f46969734ce644be97003f558bd738dd5e76832f, main baseline ef374d2562a8c05b5f859fc4c812ff9b13c8f5bc with uncommitted Phase 8 work on feat/phase8-frontend-integration. User correction is the approved visual baseline; master-plan historical dark direction is superseded for these surfaces by the explicit Phase 8/8.1 instructions.

## Docker diagnosis
Compose has no frontend source bind mount. Running image and tag both sha256:8fceceb00b5507b007926c1b1bfc443f22224fc61e63ba5ff0b9eeddc13ca060; build kMeZI_ufQBz9P1sELA4wD. Container landing and layout SHA256 match working source (11ab9ab0… and b4874cce…). Web-only --no-deps rebuild/recreation succeeded before comparison; database/API/Redis were preserved. Docker was not stale at inspection. The earlier Phase 8 rewrite omitted major source compositions. Functional tests did not prove fidelity.

## Rendered/source comparison
Reference runs at 127.0.0.1:3002; actual Compose at 127.0.0.1:3000. Baseline viewport 1440×900, mobile 390×844. Images live under artifacts/phase8-1/{reference,before}/; each filename below exists in both sets unless noted. QA actual organization/service were created by ordinary authenticated APIs, clearly labeled Visual QA; no existing data changed. Landing is public and illustrative.

| Priority | Reference route/state | Real route/state | Evidence filename | Observed defect / required adaptation |
|---|---|---|---|---|
| P0 | / preloader | / initial | preloader.png | Original dark elevation/progress wipe absent; restore animation and reduced-motion bypass. |
| P1 | / after entrance | / hero | 1440-0.png | Original elevation fills width and ~700px before three-column caption; current split pavilion/text hero entirely different. Warm gray #e0e0da replaced cream, typography/title case differ. |
| P0 | / interactive hero | / | hero-active.png | Drag selection, issue pins, coordinate cursor and inspection toolbar absent. Real hero remains a clearly labeled concept, no fake backend operation. |
| P0 | / drag selection | / | hero-active.png, source hero.tsx | Original SVG coordinate selection/overlap interaction missing; preserve source math and keyboard pins. |
| P0 | / scrolled architecture | / scroll | workflow.png | Pinned drawing/timeline absent; generic native entrance cannot match source. |
| P0 | / Observe–Advise–Act–Learn | / approach | workflow.png | Four sequenced scenes replaced by three small buttons. Preserve original phases and geometry with operational copy. |
| P0 | / product showcase | / | product.png | Layered dashboard/approval preview and tool tabs missing. Public preview must explicitly say illustrative, never live. |
| P0 | / footer lens | / footer | footer.png | Source ink reveal and large pointer lens wordmark replaced by a text strip. |
| P1 | /projects/personal | /app | 1440-1.png | Source 7px outer frame, 240px architectural sidebar, 72px breadcrumb, uppercase heading/summary register not reproduced. |
| P1 | /projects/personal grid | /app cards | 1440-1.png | Source card ID/actions/identity/diagram/status/count/signal divisions missing; real service has no multi-service Project entity. |
| P1 | /projects/personal list | /app list | list.png | Source environment sections and column hierarchy replaced with generic cards. |
| P1 | /projects/personal sidebar | /app | 1440-1.png | Missing selector, find shortcut, favorites, bottom stamp, original alignment; real account controls must remain. |
| P0 | collapsed sidebar | /app | collapsed.png | No collapse interaction or compact rail. |
| P1 | /projects/northstar/payment-gateway | /app/services/{UUID} | 1440-2.png | Project switcher, heading/status/tab strip and detail geometry missing. Real service UUID remains canonical. |
| P0 | same, analytics | service detail | 1440-2.png, source analytics-dashboard.tsx | Six-KPI grid, period toolbar, large chart and table composition replaced by simple unavailable notes. Restore composition without invented values. |
| P1 | same, chart tooltip | service detail | source time-series.tsx | Synthetic data cannot be migrated. Preserve chart frame, selected metric, legend and unavailable explanation; no nonexistent tooltip measurements. |
| P1 | same, incident register | /app/incidents | before/1440-3.png | Source register row geometry/drawer not used; retain server pagination and actual severity/state. |
| P1 | /projects/northstar/payment-gateway/incidents/inc-payment-gw-01 | /app/incidents/{UUID} | source investigation-console.tsx; corrected incident capture follows | Original header, summary/timeline grid and numbered regions not reproduced. Baseline reference 1440-3 used an invalid incident slug and is NOT evidence of console parity. |
| P1 | same, evidence | incident investigation | source investigation-console.tsx; prior Phase8 evidence captures | Source tabs/fullwidth technical panels differ; keep run/org/service scope checks, no fictional hypotheses. |
| P1 | / mobile and workspace mobile | / and /app | mobile-landing.png, mobile-workspace.png | Hero composition and four-action mobile workspace bar differ; restore responsive source breakpoints and dialog structure. |

## Constraints and order
Fix P0/P1 by importing actual reference-owned presentation, GSAP/Lenis timelines and CSS, then adapt data-only boundaries. Marketing has its own shell; real operations retain existing routes and API/auth. Missing analytics do not remove page geometry. Preserve readable Phase3 workspace typography. DEC-351–357 / ADR-029 govern; final evidence, six viewport states and limitations go in PHASE_8_1_VISUAL_FIDELITY_REPORT.md. Source map is maintained there. No source-code match is treated as rendered proof.
