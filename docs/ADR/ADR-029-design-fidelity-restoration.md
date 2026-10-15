# ADR-029 — Restore approved design fidelity

Date: 2026-10-14. Status: ACCEPTED — VERIFIED LOCALLY. User Phase 8.1 correction explicitly authorizes this reversal of the selective visual interpretation in ADR-028 / DEC-339/342/343. Their functional/security decisions and historical verification evidence remain valid.

## Problem and choice
The real Compose container contains Phase 8 source but omits the reference preloader, drag hero, pinned scenes, sidebar geometry, service drawings and analytics composition. Functional tests did not establish visual fidelity. Restore the actual committed reference presentation and timelines inside apps/web, adapting only real identity/data/routes/content and security boundaries. DEC-351–358 govern implementation.

## Alternatives and trade-offs
Continuing an approximate native-motion rewrite is less code but fails the explicit visual requirement. Replacing the whole frontend with the demo risks authorization/persistence and is rejected. Reusing presentation with real adapters preserves functionality and fidelity, at the cost of more CSS/motion source, runtime dependencies and a larger visual test surface. No performance/cost improvement is claimed. No backend/schema/security contract changes are required.

## Verification and revisit
Read-only design HEAD f46969734ce644be97003f558bd738dd5e76832f verified against GitHub. Compose source hashes match the working tree before correction; web image sha256:8fceceb00b5507b007926c1b1bfc443f22224fc61e63ba5ff0b9eeddc13ca060, build ID kMeZI_ufQBz9P1sELA4wD. The before-correction audit is in PHASE_8_DESIGN_PARITY_AUDIT.md. The completed PHASE_8_1_VISUAL_FIDELITY_REPORT.md records the final Docker identity/source hashes, 284 captures across six viewports, width/interaction checks, nine-route axe result, passing static/unit checks and all 17 browser tests plus scheduler checks. Revisit when reference/product contracts change, or motion causes a measured issue.

## Interview explanation
A functional migration can still fail a design integration. I separated the visual reference from the real backend authority, reproduced the source compositions and motion, and tested matching rendered states from the Docker image. Missing metrics keep their chart layout but show unavailable data. Approval/execution remain backend-controlled.

## Follow-up questions
- Does copying a chart permit synthetic live values? No; only authorized supported data is shown.
- Why GSAP/Lenis? The approved timelines use them; approximate replacements were explicitly rejected.
- Does a build prove fidelity? No; Docker-backed state comparisons and functional gates are separate requirements.
