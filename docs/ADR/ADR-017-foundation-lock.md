# ADR-017 — Lock a tested foundation, not unrelated latest releases

- **Date:** 2026-10-10
- **Status:** IMPLEMENTED — UNVERIFIED as a whole; individual checks in the Phase 0 report.
- **Owner:** Developer; implements the approved plan without changing its architecture.
- **Master-plan references:** §§3.5, 15, 17 P0, 19.2.
- **Problem and constraints:** A 7.1 GiB workstation must reproduce a Python/Node/PostgreSQL/Redis foundation. Package names alone do not establish API or dependency compatibility.
- **Decision:** uv and npm locks, exact direct pins, digest-pinned base/database images, one Python environment with optional agent group, small local Compose profiles, serial builds. Keep installed stable runtime versions initially and document patch limitations. Use the compatible FastAPI 0.141.0 and TypeScript 6.0.3 releases rather than forcing latest versions.
- **Alternatives:** Floating installs are easy but drift; independent Python services avoid one conflict but add deployment complexity; bypassed dependency constraints conceal incompatibility. Poetry/pnpm offer capable alternatives but add tools absent from the workstation without a foundation requirement.
- **Why this fits:** Reuses approved frameworks and existing Node tooling; locks constrain transitive changes. Smaller profiles preserve hardware capacity. No measured performance advantage over other package managers is claimed.
- **Costs / failure modes:** Download availability, platform-specific wheels, patch maintenance; development image includes test tools and is not a production image. ESLint 9 is deprecated while the accessibility plugin's peers exclude 10. No production hardening claim.
- **Actual evidence:** uv initially rejected ADK 2.11.0 + FastAPI 0.143.0 because of OTel constraints; 0.141.0 resolved and installed. Next 16.4.0 built. PostgreSQL container reports 18.6 with pgvector 0.8.7 available. Further evidence is linked from `PHASE_00_FOUNDATION.md`.
- **Revisit:** Upstream compatibility/security changes, build failures, OOM, or first deployment.
- **Interview explanation:** “I tested the complete dependency set rather than assuming stable releases worked together. The resolver caught an ADK/FastAPI conflict, so I used a compatible API version and documented the reversal. Locks and image digests make that choice reproducible. I also removed an unnecessary lint bundle that pulled an unpatched parser, while retaining TypeScript and accessibility checks.”
- **Follow-ups:** Does a lock prove safety? No, audits and runtime tests remain necessary. Why not Kubernetes? It adds no value to the current single-machine gate. Is memory sizing proven? Only measured snapshots can support that claim; limits alone cannot.
- **Related decisions:** DEC-204–214, DEC-221–226; ADR-004/005/008/013 remain governing design records.
