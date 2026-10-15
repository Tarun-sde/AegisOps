# AegisOps — Phase 8.3 Navigation Matrix & Audit

**Date:** 2026-10-14  
**Audit Target:** Public and Authenticated routes in `apps/web`  
**Purpose:** Eliminate ambiguous, redundant, dead, or misrouted links across marketing and workspace surfaces.

---

## 1. Public Marketing Navigation Inventory

| Display Label | Source Component | Target URL | Intended Purpose | Actual Target Page | Exists? | Duplicate? | Decision & Action |
|---|---|---|---|---|---|---|---|
| **AegisOps** (Logo) | `Header` / `site-shell.tsx` | `/` | Navigate to home | `apps/web/app/page.tsx` | Yes | No | **Retain**: Primary brand anchor. |
| **Product +** (Dropdown) | `Header` / `site-shell.tsx` | `/app` & `/platform` | Product tour & workspace | Mixed targets | Yes | Yes (duplicates Workspace) | **Remove dropdown**: Replace with clean, direct link to `/platform`. |
| ↳ *Operational workspace* | `Header` (inside Product) | `/app` | Authenticated app | `/app` | Yes | Yes (duplicates Workspace ↗) | **Merged** into primary header action. |
| ↳ *Inside the workflow* | `Header` (inside Product) | `/platform` | Platform capability showcase | `/platform` | Yes | No | **Elevated** to primary **Platform** link (`/platform`). |
| **Runbooks** | `Header` / `site-shell.tsx` | `/app/runbooks` | Knowledge base | Authenticated app route | Yes | N/A | **Remove from public header**: Internal application route should not be exposed on public marketing nav. |
| **Approach** | `Header` / `site-shell.tsx` | `/#workflow` | Workflow explanation | Homepage anchor `id="workflow"` | Partial | No | **Relabel & Fix Anchor**: Change label to **How It Works**, target `/#how-it-works`, ensure anchor exists on homepage. |
| **About** | `Header` / `site-shell.tsx` | `/#about` | About the platform | Nonexistent anchor | No | No | **Remove dead link**: Replace with direct link to GitHub repository (`https://github.com/Tarun-sde/AegisOps`). |
| **GitHub** *(New)* | `Header` / `site-shell.tsx` | `https://github.com/Tarun-sde/AegisOps` | Source repository | External GitHub repo | Yes | No | **Add**: Standard open-source developer platform pattern. |
| **Workspace ↗** | `Header` / `site-shell.tsx` | `/app` | Open authenticated app | `/app` | Yes | Yes | **Refactor**: Contextual CTA. When unauthenticated, show **Sign In** (`/login`); when authenticated, show **Open Workspace** (`/app`). |
| **Sign in ↗** | `Header` / `site-shell.tsx` | `/login` | User login | `/login` | Yes | No | **Refactor**: Integrated into contextual action block. |
| **Explore the platform ↗** | `Hero` / `hero.tsx` | `/platform` | Primary Hero CTA | `/platform` | Yes | No | **Refactor & Style**: Prominent Primary Button **Explore Platform** (`/platform`). |
| **Open Workspace** *(New)* | `Hero` / `hero.tsx` | `/app` | Secondary Hero CTA | `/app` | Yes | No | **Add**: Secondary button **Open Workspace** (`/app`) for direct access. |

---

## 2. Operational Workspace Navigation Inventory

| Display Label | Source Component | Target URL | Intended Purpose | Actual Target Page | Exists? | Duplicate? | Decision & Action |
|---|---|---|---|---|---|---|---|
| **AegisOps** (Sidebar Logo) | `WorkspaceShell` / `app-shell.tsx` | `/` | Return to homepage | Homepage `/` | Yes | No | **Retain**: Breadcrumb back to root. |
| **Services 01** | `WorkspaceShell` / `app-shell.tsx` | `/app` | Access services list | `/app` (currently generic services view) | Yes | Confusing | **Relabel to Overview**: Point `/app` to **Overview** (Operational Overview dashboard). |
| **Services** *(New dedicated)* | `WorkspaceShell` / `app-shell.tsx` | `/app/services` | Dedicated monitored services list | Previously returned 404! | **FIXED** | No | **Implement Route**: Add `apps/web/app/app/services/page.tsx` using real Services API. |
| **Incidents** | `WorkspaceShell` / `app-shell.tsx` | `/app/incidents` | Incident feed and details | `apps/web/app/app/incidents/page.tsx` | Yes | No | **Retain**: Links to persisted incident feed. |
| **Runbooks** | `WorkspaceShell` / `app-shell.tsx` | `/app/runbooks` | Knowledge base runbooks | `apps/web/app/app/runbooks/page.tsx` | Yes | No | **Retain**: Links to RAG runbook catalog. |
| **Proposals & deliveries** | `WorkspaceShell` / `app-shell.tsx` | `/app/proposals` | Governed action reviews | `apps/web/app/app/proposals/page.tsx` | Yes | No | **Relabel to Proposals**: Concise, clear operational label. |
| **Simulation Lab** | `WorkspaceShell` / `app-shell.tsx` | `/app/simulation-lab` | Controlled fault injection | `apps/web/app/app/simulation-lab/page.tsx` | Yes | No | **Retain**: Controlled staging fault lab. |
| **Onboarding** | `WorkspaceShell` / `app-shell.tsx` | `/onboarding` | Service registration flow | `apps/web/app/onboarding/page.tsx` | Yes | No | **Demote from primary nav**: Move to secondary action ("+ Register service" button in header/services). |
| **Find services (F)** | `WorkspaceShell` / `app-shell.tsx` | `#project-search` | In-page filter shortcut | Anchor on services page | Fragile | No | **Improve**: Global search input with clear keyboard shortcut and accessible dialog. |
| **Sign out** | `WorkspaceShell` / `app-shell.tsx` | Action (`POST /api/v1/auth/logout`) | Terminate session | Redirect to `/login` | Yes | No | **Retain**: Clean session termination. |

---

## 3. Corrected Public & Operational Route Map

### 3.1 Corrected Public Navigation Structure
```
Header:
[ AegisOps Logo (/) ] ───────── [ Platform (/platform) ] ─── [ How It Works (/#how-it-works) ] ─── [ GitHub (repo URL) ] ─── [ Sign In (/login) | Open Workspace (/app) ]
```

### 3.2 Corrected Operational Navigation Structure
```
Sidebar:
[ AegisOps Logo (/) ]
[ Organization Selector (AegisOps Demo) ]
[ Navigation Group: Core Operations ]
  ├── ⊞ Overview (/app)
  ├── ⎘ Services (/app/services)
  ├── △ Incidents (/app/incidents)
  ├── ≋ Runbooks (/app/runbooks)
  ├── ⋈ Proposals (/app/proposals)
  └── ⌖ Simulation Lab (/app/simulation-lab)
[ Sidebar Footer ]
  ├── User Profile (demo@aegisops.local · Owner)
  └── [ Sign Out ]
```

---

## 4. Automated Verification Requirements
1. Every public navigation link clicks through to a page with matching `h1` and validated content.
2. No two public navigation links share the same URL under different names.
3. Every operational rail item resolves to an existing HTTP 200 route with active tab styling (`aria-current="page"`).
4. `/app/services` must return HTTP 200 and render registered services from `getServices()`.
5. Anchor links (`/#how-it-works`) must target existing DOM IDs and scroll properly.
