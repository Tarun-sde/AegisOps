# ADR-028 — Controlled frontend integration

Date: 2026-10-14. Status: VERIFIED LOCALLY; explicitly authorized by the Phase 8 user brief. Decisions: DEC-339–350. Originally accepted as DESIGN ONLY before implementation; local verification completed on 2026-10-14.

## Problem and boundaries

The approved design is a separate Next.js prototype with fictional workspaces, telemetry and local action reviews. The real application already has session/CSRF, tenant-scoped FastAPI resources and staging-only execution. Migrate presentation into apps/web; preserve backend, schema, authentication, routes, package pins and existing security checks.

## Options and choice

1. Replace the web app with the prototype: visually direct, but loses real persistence, authentication and operational controls. Rejected.
2. Merge repositories or introduce a Project entity: adds schema/history and routing complexity without an approved product requirement. Rejected.
3. Adapt selected original SVGs, typography, semantic palette, workspace/incident/evidence presentation onto existing API workflows: selected. This has integration effort but limits security and maintenance risk; performance improvement is not claimed.

No new backend boundary, credentials, API endpoint or production action is introduced. Dashboard metrics without a scoped API stay unavailable. Native scrolling/navigation and reduced-motion-aware browser animations avoid global interference. Fonts ship locally with OFL notices. Research media stays outside the product.

## Consequences and revisit

Design fidelity is adapted to service UUIDs and genuine data availability. Full live analytics waits for a separately approved aggregation contract. Revisit resource modeling only when a real multi-service Project requirement is approved; revisit motion if concrete interactions need a library. Verification requires actual static/unit/browser gates and visual/contrast review, not screenshots alone.

## Evidence

Main baseline ef374d2562a8c05b5f859fc4c812ff9b13c8f5bc. GitHub design HEAD f46969734ce644be97003f558bd738dd5e76832f verified via git ls-remote. See ../PHASE_8_INTEGRATION_AUDIT.md and ../PHASE_REPORTS/PHASE_8_FRONTEND_INTEGRATION.md for implementation and gate evidence.

Final evidence: make check and make test exit 0 (158 Python passed, 6 deselected; Express 1 passed). make browser exit 0 on aegisops-browser-aa6dafae: production build, scheduler/expiry assertions and 16 browser tests passed. Core axe/readability and responsive assertions passed; desktop/mobile captures reviewed. Logs and captures are locally archived under artifacts/phase8-20261014/. Live model quality, hosted CI, full observability analytics and cross-browser/assistive-technology coverage remain unverified. No performance comparison is claimed.

## Interview explanation

I treated the design as presentation source and the backend as operational authority. Service cards use real organization-scoped service IDs, while incident links preserve existing UUIDs. Synthetic analytics and local approvals never enter authenticated workflows. The trade-off is honest missing-data states until the backend exposes the required contracts.

## Follow-up questions

- Does the UI enforce tenancy? No; existing deterministic backend checks remain authoritative.
- Why no new Project model? Current services already represent the selectable applications; schema changes are unjustified for styling.
- Does a passing browser gate prove live AI correctness? No. It verifies deterministic local persistence and controls; live model evaluation remains separate.

## Phase 8.1 correction

The selective visual rewrite/native approximation is SUPERSEDED by [ADR-029](ADR-029-design-fidelity-restoration.md), explicitly requested by the user after Docker inspection. Prior local functional verification remains historical evidence; it did not prove visual fidelity. Backend/security/data semantics remain governing.
