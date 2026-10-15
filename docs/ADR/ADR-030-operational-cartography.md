# ADR-030 — Original Operational Cartography identity

Date: 2026-10-14. Status: ACCEPTED — VERIFIED locally.

## Problem and boundaries
Phase 8.1 verified the requested reference layout and motion, but retained architectural subjects. The explicit Phase 8.2 request authorizes an original AegisOps identity while preserving those interactions and all real application contracts. Replace the presentation inside apps/web with original service, telemetry, evidence and approval SVGs. Public samples are explicitly illustrative and never import account APIs. Backend authentication, tenancy, approvals, execution and recovery remain authoritative and unchanged. DEC-359–365 govern the granular choices.

## Alternatives and rationale
Renaming building labels leaves the wrong product meaning and is explicitly rejected. Replacing the frontend with an unrelated template discards verified composition and motion. A second visualization library adds dependencies without a requirement. Repo-native SVG supports accessible descriptions, exact pointer geometry and the existing GSAP clocks, with no added runtime dependency. Reuse motion structure, replace all subjects and targets. Add the requested public /platform showcase without a demo application store.

## Costs and revisit
SVG illustrations require responsive and motion-state review. Public samples demonstrate a workflow, not live diagnosis, accuracy or recovery. Revisit for measured performance/legibility problems, an approved brand revision or a new real data contract. No performance or business benefit is asserted without evidence.

## Evidence
Before captures are preserved under artifacts/phase8-2/before. Source audit: docs/PHASE_8_2_CONTENT_AND_VISUAL_AUDIT.md. Original design commit f46969734ce644be97003f558bd738dd5e76832f was inspected read-only outside the repository. Implementation and actual gate results are recorded in docs/PHASE_REPORTS/PHASE_8_2_AEGISOPS_BRANDING.md. Phase 8/8.1 evidence is historical and preserved.

## Interview explanation
The integration worked, but its illustrations described architecture rather than operations. We kept the verified interaction system and replaced its content with one coherent, explicitly fictional incident. Vector graphics expose the request path, evidence links and human approval boundary. Real workspace screens continue using authorized data; marketing cannot perform account actions.

## Follow-up questions
- Is the topology automatically discovered? No, it is a labeled illustrative scenario.
- Does approving a preview execute anything? No, it changes local demonstration state only.
- How is fidelity established? Source scans, motion assertions and rendered Docker screenshots complement functional/security gates; a successful build alone is insufficient.

Verification update: all release checks passed, 22 isolated browser tests and the scheduler gate passed, all five branding tests passed against the delivered Docker image, and six viewport runs produced 232 captures without overflow/page errors/console warnings. Six axe surfaces report zero serious/critical violations. See the phase report for gate sequencing, final image hashes and limits.
