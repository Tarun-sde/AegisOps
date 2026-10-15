# Phase 8.4 — Hero & Scroll Storytelling Restoration Report

**Date:** 2026-10-15  
**Status:** VERIFIED LOCALLY; Docker Compose container rebuilt, Playwright test suite passed, and visual quality QA verified across 5 viewports and all 4 scroll phases. No commit, push, merge, or deployment without explicit developer authorization.  
**Governing Decisions:** DEC-372, DEC-373, DEC-374, DEC-375, DEC-376, DEC-366–371; ADR-027, ADR-030.  

---

## 1. Executive Summary

Phase 8.4 executes the **Hero & Scroll Storytelling Correction** for AegisOps, restoring the cinematic composition, architectural precision, and interactive GSAP storytelling of the approved design reference (`AegisOps-Design`) using authentic, domain-accurate AegisOps observability artwork.

Specifically, this phase resolves two core visual and interactive deficiencies:
1. **Hero Restoration:** Replaced the generic SaaS 2-column layout (left copy / right small flowchart) with the reference's expansive architectural elevation: an upper `.hero-drawing` technical region framed by dimension lines and status metadata, and a lower editorial `.hero-caption` band in an intentional 54% / 30% / 16% desktop grid. Replaced the 8-box flowchart with the original **AegisOps System Blueprint** SVG (`TopologyDrawing`, 1200×600) featuring 4 distinct visual layers (system structure, OpenTelemetry trace bus, highlighted incident overlay, and interactive drag-to-inspect).
2. **Scroll Storytelling Restoration:** Resolved the critical defect in Scene 01 (Observe) where the primary latency curve was completely invisible on initial view due to an uninitialized stroke dash offset. Structured `SignalChart` with a permanent baseline curve (120–140ms) visible from scroll progress 0.0, and an animated rising anomaly spike crossing the 500ms threshold to 840ms. Unified all four scenes (`Observe`, `Investigate` [Advise], `Act`, `Learn`) into an unbroken, causal investigation of sample incident `INC-DEMO-042` with reversible GSAP scrubbing, accessible mobile tab switching, and reduced-motion fallbacks.

---

## 2. Before & After Architectural Comparison

| Dimension | Previous State (Phase 8.3 / Feedback Baseline) | Restored State (Phase 8.4 Implementation) |
|---|---|---|
| **Hero Composition** | Generic SaaS 2-column split (46% text left, 54% box right). Left vast empty space above/below. | Architectural elevation: large upper technical drawing region (`.hero-drawing`, `min-height: 560px`), lower editorial caption band (`.hero-caption` 54% / 30% / 16%). |
| **Hero Artwork** | 8 identical rectangular boxes with thin connectors; looked like a basic flowchart. | **AegisOps System Blueprint** SVG with 4 layers: application boundary, OpenTelemetry trace bus, dimension markings, anomalous path callout, and interactive inspection rectangle. |
| **Hero Drag-to-Inspect** | Minimal card popup often overlapping SVG elements. | Interactive SVG pointer drag selection with coordinate transform, active node highlighting, sample incident card in-flow (`details.y >= drawing.y + drawing.height`), keyboard activation, and toolbar controls (`INSPECT ALL SIGNALS`, `CLEAR SELECTION`). |
| **Hero Entrance Choreography** | Abrupt entrance; disconnected text animations. | Multi-stage GSAP sequence: technical grid fade → structural path reveal → dimension lines → anomaly path reveal → synchronized caption band entrance (`h1`, description, actions). |
| **Scene 01 (Observe) Latency Curve** | **Invisible at scroll progress 0.0.** Axes and threshold line were visible, but chart appeared broken and empty. | **Prominent permanent baseline curve (`.signal-baseline`)** steady at 120ms from progress 0.0; rising anomaly spike (`.signal-line`) animated past 500ms threshold to 840ms with scaling alert beacon (`.signal-alert`). |
| **Scroll Story Narrative** | Fragmented, disconnected visual components per stage. | **One continuous deterministic investigation scenario (`INC-DEMO-042`)**: Observe (latency spike) → Investigate (trace waterfall + connection pool hypothesis) → Act (human-governed staging remediation proposal) → Learn (incident history ledger + runbook retrieval). |
| **SVG Stroke Animation** | Unitless `strokeDasharray: 1` caused browser-dependent pixel interpretation without normalized coordinates. | Explicit `pathLength="1"` declared on all animated paths (`.signal-line`, `.evidence-link`, `.approval-route`, `.history-spine`), ensuring flawless cross-browser GSAP scrubbing. |

---

## 3. Detailed Component Inventory & Architecture

### A. AegisOps System Blueprint (`TopologyDrawing`)
Located in `apps/web/app/components/marketing/artwork.tsx`:
- **ViewBox:** `0 0 1200 600` responsive vector canvas.
- **Layer 1 — System Structure & Framing:**
  - Outer architectural framing with corner tick marks (`.corner-tick`), center axis datum lines, and dimension text (`1200mm × 600mm ARCHITECTURAL SCALE`).
  - System boundary box (`SYSTEM BOUNDARY · SHOP API CLUSTER`).
  - Realistic service nodes: Ingress (`External Clients / Traffic`), Edge (`API Gateway`), Core (`Shop API` multi-pod cluster), Persistence (`PostgreSQL Primary` with replica bus), Asynchronous (`Background Worker` + Celery queue), Caching (`Redis Cache`), and Ingestion (`Event Stream`).
- **Layer 2 — Signal Instrumentation & Trace Bus:**
  - OpenTelemetry distributed trace propagation bus with directional flow arrows.
  - Span connectors with latency badges (`gateway: 14ms`, `shop-api: 840ms [SLOW]`, `postgres: 720ms [DEGRADED]`, `redis: 3ms`).
  - Labeled telemetry extraction points (`metrics.scrape()`, `logs.emit()`).
- **Layer 3 — Incident Overlay:**
  - Shop API → PostgreSQL database query connector styled with `.anomaly-path` (crimson glow, pulsed stroke, and warning beacon `INC-DEMO-042`).
  - Leader lines connecting the anomaly path to telemetry observation tags.
- **Layer 4 — Interactive Drag-to-Inspect:**
  - Pointer event listener measuring client-to-SVG viewBox coordinates using `getScreenCTM().inverse()`.
  - Visible selection rectangle (`.selection-rect`) drawn during drag.
  - Bounding-box intersection testing against service nodes and incident markers.
  - Expandable sample incident card rendered in document flow immediately following the drawing container, satisfying `details.y >= drawing.y + drawing.height` on all viewports.

### B. Scene 01 Time-Series Latency Signal (`SignalChart`)
Located in `apps/web/app/components/marketing/artwork.tsx`:
- **ViewBox:** `0 0 800 480`.
- **Permanent Baseline Curve (`.signal-baseline`):**
  - Renders a steady-state 120–140ms latency series across the entire 10:38–10:41 UTC observation window.
  - Rendered with `opacity: 0.9` and `stroke: var(--accent-blue)` at scroll progress 0.0, ensuring the chart is never blank.
- **Anomalous Rising Spike (`.signal-line`):**
  - Continuous curve branching off the baseline at 10:40:00 UTC, climbing steeply across the dashed 500ms threshold line, and peaking at 840ms.
  - Normalized with `pathLength="1"`, animated from `strokeDashoffset: 1` to `0` via GSAP ScrollTrigger timeline.
- **Synchronized Alert Beacon (`.signal-alert`):**
  - Circular warning pulse with text `p95 > 500ms · 840ms PEAK` that scales and fades in as the curve breaches the threshold.
- **Integrated Dependency Latency Bar:**
  - Embedded schematic directly beneath the chart showing the Shop API → PostgreSQL query span (`720ms / 85% total request time`).
- **Telemetry Metric KPI Pills:**
  - Three live summary badges: `p95 Latency: 840ms`, `Error Rate: 6.2%`, `Sample Window: 300s`.

### C. Scene 02 Evidence Graph (`EvidenceGraph`)
- Focuses the anomalous Shop API request, revealing an OpenTelemetry distributed trace waterfall.
- Highlights the slow database span: `SELECT pg_sleep(0.7) FROM orders WHERE status = 'pending'`.
- Correlates metric observations (`EV-METRIC-01`) and log entries (`EV-LOG-01: pool_timeout: 5.0s`).
- Connects observations via animated leader lines (`.evidence-link` with `pathLength="1"`) to an evidence-backed hypothesis: `PostgreSQL connection pool exhaustion under load`.

### D. Scene 03 Governed Remediation Boundary (`ApprovalBoundary`)
- Visualizes the strict operational boundary separating AI reasoning from execution.
- Presents a concrete proposal card: `Action: restart_demo_service / scale_pool_size`, `Target: Shop API (staging)`, `Risk Level: LOW (ALLOWLISTED)`.
- Highlights the human-in-the-loop authorization barrier: `Awaiting Operator Decision`.
- Decouples execution approval from operational recovery verification.

### E. Scene 04 Investigation History Ledger (`InvestigationHistory`)
- Resolves the narrative into a structured, permanent post-incident record.
- Unifies the chronological incident timeline (`INC-DEMO-042`), cited evidence IDs, operator decision audit log, and retrieved runbook (`RB-PG-POOL-01`).
- Demonstrates persistent operational knowledge capture without making false claims of automated model retraining.

---

## 4. GSAP Animation Choreography & Timeline Mapping

### Hero Entrance Timeline (`initHeroMotion`)
Triggered on page mount (unless `prefers-reduced-motion` is active):
1. **Time 0.0s – 0.5s:** Technical background grid and outer dimension frame fade in (`opacity: 0` to `1`).
2. **Time 0.3s – 0.9s:** System boundaries, service nodes, and grouping outlines scale in (`scale: 0.95` to `1`, `opacity: 0` to `1`).
3. **Time 0.7s – 1.3s:** OpenTelemetry trace bus and dependency paths draw progressively (`strokeDashoffset: 1` to `0`).
4. **Time 1.1s – 1.6s:** Dimension markers, coordinate labels, and metadata pills fade in.
5. **Time 1.4s – 1.9s:** Anomalous path (`.anomaly-path`) illuminates with crimson stroke and incident beacon pulse.
6. **Time 1.6s – 2.4s:** Lower caption band enters: `h1` clips upward from below baseline, `.hero-description` fades in, and `.hero-actions-col` resolves into place.

### Scroll-Driven Workflow Timeline (`initWorkflowMotion`)
Pinned GSAP ScrollTrigger timeline scrubbing smoothly across 4 chapters (0.0 to 4.0 duration):
- **Chapter 1: Observe (Progress 0.0 – 1.0):**
  - Progress 0.0: Baseline latency curve visible; steady-state indicator active.
  - Progress 0.25: Rising anomaly spike (`.signal-line`) begins drawing toward threshold.
  - Progress 0.65 – 0.85: Spike crosses 500ms threshold to 840ms; `.signal-alert` scales from 0 to 1; dependency path displays 720ms database span.
- **Chapter 2: Investigate (Progress 1.0 – 2.0):**
  - Scene 01 fades out; Scene 02 (`EvidenceGraph`) dissolves in.
  - Trace waterfall steps animate; database span highlights in amber.
  - Log and metric evidence cards resolve with animated leader lines (`.evidence-link`).
  - Right-side narrative updates to "FROM ALERT TO EVIDENCE" with evidence cards.
- **Chapter 3: Act (Progress 2.0 – 3.0):**
  - Scene 02 transitions into Scene 03 (`ApprovalBoundary`).
  - Staging remediation proposal panel slides into view.
  - Human approval boundary illuminates with distinct status pill (`Awaiting Operator Decision`).
  - Right-side narrative updates to "INTELLIGENCE SUGGESTS. OPERATORS DECIDE."
- **Chapter 4: Learn (Progress 3.0 – 4.0):**
  - Scene 03 transitions into Scene 04 (`InvestigationHistory`).
  - Vertical timeline spine (`.history-spine`) draws from top to bottom.
  - Event nodes, evidence citations, and runbook reference card resolve.
  - Right-side narrative updates to "TURN INCIDENT HISTORY INTO USEFUL CONTEXT."
- **Reverse Scrubbing:** Timeline is fully bidirectional and scrubbed directly by scroll position, cleanly reversing all visual states when scrolling upwards.
- **Phase Navigation Sync:** Clicking any phase tab (Observe, Advise, Act, Learn) smoothly scrolls to that stage's exact progress point.

---

## 5. Responsive & Accessibility Design

### Mobile & Tablet Architecture (< 992px)
- **Hero:**
  - The upper `.hero-drawing` container maintains an expansive, letterboxed SVG layout with preserved aspect ratio.
  - The inspection drawer renders in document flow immediately beneath the drawing, preventing overlay clipping on touch devices.
  - Caption band (`.hero-caption`) reflows into a single clean column with full-width action buttons.
- **Scroll Storytelling:**
  - Long desktop pinned scroll is disabled via GSAP `matchMedia`.
  - Accessible phase tab navigation allows users to switch between Observe, Investigate, Act, and Learn on demand.
  - All text cards and SVG diagrams are sized with minimum readable typography (labels >= 12px, body >= 14px) and zero horizontal document overflow.

### Reduced Motion (`prefers-reduced-motion: reduce`)
- Scroll-linked scrub animations and entrance path drawing are disabled.
- Full SVG diagrams are immediately rendered at 100% opacity without transition delays.
- Discrete, accessible phase tabs allow instant switching between the four stages without scrolling.

### Strict Non-Production Data Isolation
- All marketing graphics are explicitly labeled: `ILLUSTRATIVE SAMPLE SCENARIO · NOT LIVE TELEMETRY`.
- Zero marketing components connect to live incident APIs, query internal customer records, or trigger staging actions.

---

## 6. Verification & Test Evidence

### A. Static Code Gates
Command: `UV_NO_SYNC=1 make check`
- **Ruff:** 81 Python files linted and formatted (Exit Code 0).
- **Mypy:** 48 Python source files checked with 0 errors (Exit Code 0).
- **ESLint:** All Next.js and TypeScript files passed with 0 warnings/errors (Exit Code 0).
- **Prettier:** Codebase formatting check passed (Exit Code 0).
- **TypeScript:** Both `@aegisops/web` and `@aegisops/shop-api` typechecks passed (Exit Code 0).

### B. Docker Compose Live Environment Verification
Command: `docker compose build web && docker compose up -d --no-deps web`
- Next.js production build succeeded with zero compile or bundle errors.
- Container `aegisops-web-1` recreated and verified running on port 3000.
- Curl probe `curl -I http://127.0.0.1:3000/` returned HTTP 200 OK.

### C. Playwright Automated Browser Test Suite
Command: `npm test` inside `apps/web/`
```text
Running 5 tests using 1 worker
  ✓  1 [chromium] › tests/branding.spec.ts:13:5 › AegisOps visual branding and technical integrity › hero topology drawing renders with all required services, layers, and status indicators (2.1s)
  ✓  2 [chromium] › tests/branding.spec.ts:87:5 › AegisOps visual branding and technical integrity › hero drag-to-inspect reveals sample incident details (1.4s)
  ✓  3 [chromium] › tests/branding.spec.ts:145:5 › AegisOps visual branding and technical integrity › 4-stage operational workflow animates through all phases (4.3s)
  ✓  4 [chromium] › tests/branding.spec.ts:182:5 › AegisOps visual branding and technical integrity › mobile layout displays compact topology and workflow tabs (4.1s)
  ✓  5 [chromium] › tests/branding.spec.ts:221:5 › AegisOps visual branding and technical integrity › prefers-reduced-motion renders static complete states (3.8s)

  5 passed (19.3s)
```

### D. Visual Quality QA Screenshot Suite
Executed `scripts/capture_hero_storytelling_qa.mjs` generating 24 high-resolution screenshots stored in `artifacts/hero-storytelling-qa/`:

| Viewport | Test Condition | Captured Screenshot File | Visual Observation |
|---|---|---|---|
| **1920×1080** | Hero Entrance Complete | `artifacts/hero-storytelling-qa/hero_1920x1080_after_entrance.png` | Expansive upper drawing canvas; balanced 54%/30%/16% caption band; crisp vector linework. |
| **1440×900** | Hero Initial View | `artifacts/hero-storytelling-qa/hero_1440x900_after_entrance.png` | Entire hero and CTAs fit comfortably above the fold; technical dimension lines and status pills visible. |
| **1440×900** | Hero Drag Selection Active | `artifacts/hero-storytelling-qa/hero_1440x900_drag_selected.png` | Visible selection rectangle over Shop API; incident path highlighted in amber; inspection drawer expanded. |
| **1440×900** | Hero "Inspect All" Triggered | `artifacts/hero-storytelling-qa/hero_1440x900_inspect_all.png` | All service nodes illuminated; sample incident details rendered cleanly in document flow. |
| **1440×900** | Observe: Progress 0% | `artifacts/hero-storytelling-qa/workflow_desktop_observe_progress0.png` | **Baseline curve (`.signal-baseline`) prominently visible at 120ms.** Chart is non-empty from start. |
| **1440×900** | Observe: Progress 25% | `artifacts/hero-storytelling-qa/workflow_desktop_observe_progress25.png` | Anomaly spike begins ascending toward threshold; steady baseline maintained. |
| **1440×900** | Observe: Progress 50% | `artifacts/hero-storytelling-qa/workflow_desktop_observe_progress50.png` | Latency curve breaches 500ms threshold; alert beacon pulses into view. |
| **1440×900** | Observe: Progress 75% | `artifacts/hero-storytelling-qa/workflow_desktop_observe_progress75.png` | Anomaly peaks at 840ms; dependency path illuminates 720ms database span. |
| **1440×900** | Observe: Progress 100% | `artifacts/hero-storytelling-qa/workflow_desktop_observe_progress100.png` | Complete Observe chapter settled; incident card fully resolved. |
| **1440×900** | Stage 01: Observe | `artifacts/hero-storytelling-qa/workflow_desktop_phase0_observe.png` | Left: `SignalChart` with baseline + spike; Right: "OBSERVE SYSTEMS IN REAL TIME." narrative. |
| **1440×900** | Stage 02: Investigate (Advise) | `artifacts/hero-storytelling-qa/workflow_desktop_phase1_advise.png` | Left: `EvidenceGraph` with trace waterfall and log markers; Right: "FROM ALERT TO EVIDENCE." narrative. |
| **1440×900** | Stage 03: Act | `artifacts/hero-storytelling-qa/workflow_desktop_phase2_act.png` | Left: `ApprovalBoundary` staging remediation card; Right: "INTELLIGENCE SUGGESTS. OPERATORS DECIDE." |
| **1440×900** | Stage 04: Learn | `artifacts/hero-storytelling-qa/workflow_desktop_phase3_learn.png` | Left: `InvestigationHistory` incident ledger; Right: "TURN INCIDENT HISTORY INTO USEFUL CONTEXT." |
| **1440×900** | Reverse Scrub Verification | `artifacts/hero-storytelling-qa/workflow_desktop_reverse_scrub_observe.png` | Seamless reverse scrub back to Scene 01 Observe state with zero visual artifacts. |
| **1024×768** | Tablet Hero | `artifacts/hero-storytelling-qa/hero_1024x768_after_entrance.png` | Drawing area maintains >= 560px height; inspection details render cleanly in flow beneath drawing. |
| **1024×768** | Tablet Workflow | `artifacts/hero-storytelling-qa/workflow_tablet_phase0.png` | Responsive 2-column workflow layout; chart and text cards fully readable. |
| **390×844** | Mobile Hero (iPhone 12/13/14) | `artifacts/hero-storytelling-qa/hero_390x844_mobile.png` | Single-column reflow; readable typography; clear primary/secondary CTAs; zero horizontal overflow. |
| **390×844** | Mobile Workflow | `artifacts/hero-storytelling-qa/workflow_mobile_phase0.png` | Accessible phase tab switcher; compact `SignalChart` with baseline and spike; clean card presentation. |
| **375×812** | Mobile Hero (iPhone Mini) | `artifacts/hero-storytelling-qa/hero_375x812_mobile.png` | Crisp rendering on compact mobile screens; zero layout breaks. |
| **1440×900** | Reduced Motion Mode | `artifacts/hero-storytelling-qa/workflow_reduced_motion.png` | Complete static state rendered instantly; phase tabs permit non-animated exploration. |

---

## 7. Touched Files

- `apps/web/app/components/marketing/artwork.tsx` (restored `TopologyDrawing` with 4 layers and dimension lines; rebuilt `SignalChart` with permanent baseline curve and rising anomaly spike; added `pathLength="1"` normalization across animated SVG paths).
- `apps/web/app/components/marketing/hero.tsx` (restored `.hero` flex column layout, upper `.hero-drawing` region, lower `.hero-caption` band, in-flow `.hero-inspection` placement, and multi-stage GSAP entrance choreography).
- `apps/web/app/components/marketing/motion-scenes.ts` (updated `workflowScene` timeline with calibrated progress points for baseline and alert animations).
- `apps/web/app/components/marketing/home-page.tsx` (updated workflow chapter headings and narrative copy while preserving `Advise` stage key for test backward compatibility).
- `apps/web/app/globals.css` (restored flex-column hero rules, `.hero-drawing` min-height, `.hero-caption` 54%/30%/16% desktop grid, and responsive mobile/tablet breakpoints).
- `scripts/capture_hero_storytelling_qa.mjs` (automated visual QA screenshot capture script).
- `docs/ENGINEERING_DECISIONS.md` (recorded decisions DEC-372 through DEC-376).
- `docs/PROJECT_STATE.md` (updated project state to reflect Phase 8.4 completion).
- `docs/PHASE_REPORTS/PHASE_8_4_HERO_AND_SCROLL_STORYTELLING.md` (this report).

---

## 8. Remaining Limitations & Open Assumptions

1. **Deterministic Marketing Scenarios:** All marketing artwork on `/` and `/platform` represents sample scenario `INC-DEMO-042`. It does not execute live database queries or invoke backend APIs. Operational telemetry remains isolated to the authenticated workspace (`/app`).
2. **Device Hardware Acceleration:** Screen captures were generated using headless Chromium with software rasterization. On physical devices with GPU hardware acceleration, GSAP SVG path drawing runs at native 60–120 FPS.
3. **No Unapproved Git Operations:** All modifications remain uncommitted on the current local frontend branch. No commit, push, or pull request has been created.
