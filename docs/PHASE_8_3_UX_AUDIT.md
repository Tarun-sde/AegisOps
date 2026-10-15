# AegisOps — Phase 8.3 UX & Visual Audit

**Date:** 2026-10-14  
**Audit Target:** Real Compose Application at `http://localhost:3000` (Delivered Docker image `aegisops-web-1`)  
**Auditor:** Staff Product Designer, Principal Frontend Engineer, Design Systems Architect  
**Baseline Evidence:** `artifacts/phase8-3/baseline/` (`desktop_homepage.png`, `hero_before.png`, `hero_after.png`, `desktop_platform.png`, `desktop_dashboard.png`, `desktop_services.png`, `mobile_homepage.png`)

---

## 1. Executive Summary

A thorough visual, structural, and behavioral audit of the running AegisOps Docker application reveals that while Phase 8.2 established original vector identity and sample isolation, the product user experience still suffers from three fundamental architectural and visual deficiencies:

1. **The Hero Fails to Communicate the Product Above the Fold:**
   The current landing hero stacks a 620px-tall SVG canvas above the headline and CTAs. On standard 1440×900 screens, the headline ("See the signal...") and call-to-action are pushed below the viewport fold. The desktop drag-to-inspect interaction is technically functional but conceptually opaque, requiring users to drag selection boxes across coordinates before understanding the platform. The button text `CLEAR INSPECTION ↗` exhibits text-wrapping glitching, and the CTA link `EXPLORE ↗` is clipped awkwardly in a narrow bottom right column.

2. **Public and Workspace Navigation are Ambiguous and Redundant:**
   The public header presents multiple differently labeled controls pointing to the exact same destination (`Product + -> Operational workspace` -> `/app`, and `Workspace ↗` -> `/app`). Authenticated application routes (`/app/runbooks`) are exposed directly in public marketing navigation. Anchor links (`/#about`, `/#workflow`) lack clear section correspondence. In the operational sidebar, the primary link `/app` is mislabeled as "Services", while navigating to `/app/services` produces an HTTP 404 error.

3. **The Authenticated Dashboard Lacks Operational Hierarchy:**
   The route `/app` currently renders an inventory page titled "YOUR SERVICES 01", completely missing an operational overview. When an engineer logs in, they cannot immediately answer:
   - Is the overall system healthy or degraded?
   - Which active incidents require immediate triage?
   - What is the status of running or recent AI investigations?
   - Are there pending remediation proposals awaiting human approval?
   Instead, the page presents four generic stat boxes and a single service card with a non-interactive schematic. An oversized promotional card ("AUTHENTICATED WORKSPACE") clutters the operational rail.

---

## 2. Hero Visual & Conceptual Audit

| Inspection Criterion | Current Baseline Observation | Defect Classification | Required Solution |
|---|---|---|---|
| **Composition & Hierarchy** | 620px SVG canvas stacked vertically above headline. Headline is below fold at 1440×900. | Critical Layout Flaw | Side-by-side composition: Left column (eyebrow, strong headline, concise copy, primary/secondary CTAs, proof points); Right column (observability control surface). Visible in full at 1440×900. |
| **Headline & Value Proposition** | "See the signal. Understand the incident. Stay in control." (split across 3 lines below diagram). | Weak Hierarchy | Replace with: **"When systems fail, clarity matters."** Position prominently at top of left column with high-contrast typography. |
| **Supporting Copy** | Multi-sentence paragraph split into separate text blocks. | Fragmented Readability | Single concise paragraph: "AegisOps brings operational signals, incident timelines and evidence-backed AI investigations into one workflow—so engineers can understand failures and make controlled decisions." |
| **Call-to-Action (CTA)** | Single arrow link "EXPLORE ↗" in right column, clipped text. | Ambiguous / Broken Affordance | Two distinct buttons: Primary: **Explore Platform** (`/platform`); Secondary: **Open Workspace** (`/app`). Clear visual button styling with high contrast. |
| **Technical Proof Points** | Small monospace tags `+ SCOPED EVIDENCE`, `+ HUMAN REVIEW`, `+ AUDITABLE ACTIONS` disconnected from copy. | Disconnected | Integrate technical proof chips directly below CTAs: `✓ Scoped Evidence`, `✓ Human-Governed Actions`, `✓ Independent Recovery Verification`. |
| **Artwork & Interaction** | Canvas drag-to-select requires mouse coordinates. When inspected, button text glitches (`CLEAR INSPECTION ↗` wraps). | Usability & Rendering Glitch | Interactive Incident Intelligence Control Surface: clear service topology with dynamic signal indicators, hover/click service node inspection, polished "Inspect Scenario" toggle, responsive compact artwork for mobile without layout shift. |
| **Mobile Presentation (375×812)** | Diagram labels scale down to unreadable sizes; headline pushed 800px down. | Poor Mobile UX | Clean stacked mobile layout: concise headline, prominent CTAs, touch-friendly interactive control surface. |

---

## 3. Information Architecture & Navigation Audit

### 3.1 Public Marketing Navigation

| Current Label | Current URL | Actual Target | UX Issue | Proposed Resolution |
|---|---|---|---|---|
| AegisOps (Logo) | `/` | Homepage | Works correctly. | Retain as primary home link. |
| Product + (Dropdown) | `/app` & `/platform` | `/app` (Workspace) & `/platform` | Conflates workspace with public product tour; nested dropdown adds friction. | Replace with direct **Platform** link to `/platform`. |
| Runbooks | `/app/runbooks` | Authenticated Runbooks | Exposes internal application route in public marketing header. | Remove from public header; keep in workspace navigation. |
| Approach | `/#workflow` | Homepage scroll section | Ambiguous label; anchor name doesn't match label. | Relabel to **How It Works** pointing to `/#how-it-works`. |
| About | `/#about` | Homepage footer | Dead-end anchor; no dedicated About section exists. | Remove dead link; replace with direct link to GitHub repository. |
| Workspace ↗ | `/app` | `/app` | Duplicate link to `/app` (already in Product dropdown). | Replace with contextual button: **Open Workspace** (`/app`) if session active, or **Sign In** (`/login`). |
| Sign in ↗ | `/login` | Authentication page | Plain text link alongside Workspace. | Contextual: **Sign In** (`/login`) when unauthenticated, **Open Workspace** (`/app`) when authenticated. |

### 3.2 Operational Workspace Navigation

| Current Label | Current URL | Actual Target | UX Issue | Proposed Resolution |
|---|---|---|---|---|
| Services (Icon ⊞) | `/app` | `/app` (Your Services) | Mislabeled: `/app` is the workspace root, not a dedicated services list. | Relabel `/app` to **Overview** (Operational Overview). |
| *Missing* | `/app/services` | HTTP 404 | Clicking `/app/services` returns 404; no dedicated services inventory page exists. | Implement **Services** (`/app/services`) using real Services API. |
| Incidents (Icon △) | `/app/incidents` | `/app/incidents` | Works, but feed lacks active incident priority badges. | Retain **Incidents** (`/app/incidents`); link active incidents directly from Overview. |
| Runbooks (Icon ≋) | `/app/runbooks` | `/app/runbooks` | Works correctly. | Retain **Runbooks** (`/app/runbooks`). |
| Proposals & deliveries (Icon ⋈) | `/app/proposals` | `/app/proposals` | Label is overly verbose for operational rail. | Simplify to **Proposals** (`/app/proposals`). |
| Simulation Lab (Icon ⌖) | `/app/simulation-lab` | `/app/simulation-lab` | Works correctly. | Retain **Simulation Lab** (`/app/simulation-lab`). |
| Onboarding (Icon +) | `/onboarding` | `/onboarding` | Mixed into primary operational navigation. | Move to a subtle "+ Register Service" action button rather than cluttering primary operational nav. |

---

## 4. Operational Dashboard (`/app`) Audit

### 4.1 Current Layout Deficiencies
1. **Wrong Page Identity:** The page title is "YOUR SERVICES 01 / One place to oversee every registered service." It behaves like an entity list rather than a command center.
2. **Missing System Status:** There is no high-level system condition banner. The user cannot see whether the platform is operating normally, degraded, or experiencing critical alerts.
3. **Hidden Incidents:** The demo organization has 18 persisted incidents, but **zero incident cards** are rendered on the main dashboard! An SRE must navigate to `/app/incidents` to find any alert information.
4. **No Investigation Visibility:** AegisOps is an AI incident intelligence platform, yet the dashboard displays no active or recent investigation states (queued, investigating, validating, completed).
5. **No Direct Review / Action Affordances:** Pending remediation proposals requiring human authorization are not surfaced on the dashboard.
6. **Marketing Noise in Workspace:** The sidebar contains a dark promotional card ("AUTHENTICATED WORKSPACE / Evidence before action...") which wastes vertical screen space and looks out of place in a serious developer tool.

### 4.2 Proposed Dashboard Information Hierarchy
The restructured `/app` Operational Overview will strictly answer the operator's key questions in sequence:

```
┌────────────────────────────────────────────────────────────────────────┐
│ Operational Page Header:                                               │
│ [Operational Overview]  Org: AegisOps Demo  Env: Staging  Freshness: Now│
├────────────────────────────────────────────────────────────────────────┤
│ 1. System Condition & KPI Strip:                                       │
│ [System: DEGRADED / ATTENTION] [Active Incidents: 2] [Services: 1]     │
│ [Pending Proposals: 1] [Recent Investigations: 3]                      │
├────────────────────────────────────────────────────────────────────────┤
│ 2. Incident Attention Area (High Priority):                           │
│ - INC-DEMO-042: Shop API elevated latency (P1 · Active · 10:42 UTC)    │
│   Action: [Investigate with AI] [View Scoped Evidence ↗]               │
├────────────────────────────────────────────────────────────────────────┤
│ 3. Service Health & Inventory Table:                                   │
│ - Name, Environment, Status, Health Check, Active Incidents, Actions  │
├────────────────────────────────────────────────────────────────────────┤
│ 4. Recent AI Investigation Stream:                                     │
│ - Run ID, Incident, Model, Status (Completed / Validating), Findings   │
├────────────────────────────────────────────────────────────────────────┤
│ 5. Governed Actions & Simulation Lab Quick-Access:                     │
│ - Pending proposals requiring human review, Active simulation controls │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Visual Acceptance Gates & Regression Plan
- Rebuild Next.js frontend with updated layouts and components.
- Verify Docker web container at `http://localhost:3000`.
- Capture full before/after screenshot comparisons across viewports (1920×1080, 1440×900, 1024×768, 390×844, 375×812).
- Execute `make check`, `make test`, and `make browser` to guarantee zero regressions.
- Ensure all automated navigation and accessibility assertions pass with 100% compliance.
