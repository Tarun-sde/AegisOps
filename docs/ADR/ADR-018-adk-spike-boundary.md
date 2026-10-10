# ADR-018 — Separate framework proof from live model proof

- **Date:** 2026-10-10
- **Status:** Foundation/offline dispatch VERIFIED; live Gemini and Groq model verification VERIFIED on Free tier (DEC-237–240); Phase 1 LOCKED pending authorization.
- **Owner:** Developer; expands ADR-001/003/012/015 without granting new capabilities.
- **Master-plan references:** §§4.3–4.8, 17 P0, 18 Day 2.
- **Problem and constraints:** Prove ADK can call a read-only tool and produce a validated typed result. No Gemini key or authorized spend was initially available. Logs and model responses are untrusted.
- **Decision:** One agent, one argument-free synthetic log tool with backend-fixed scope, two fixtures (supported and conflicting), in-memory ADK sessions, external evidence-reference validation. A deterministic fake model drives the actual ADK Runner and its structured response tool offline. The same path has an opt-in real Gemini candidate and bounded request/token/cost checks. No synthetic model response is labeled a live result.
- **Alternatives:** Handwritten tool-loop mocks would not exercise ADK; a live-only test is expensive and unavailable without credentials; multiple agents or two-stage formatting add coordination before any measured need. Native tools-plus-schema capability is not forced over ADK's own detection.
- **Why this fits:** Makes offline wiring deterministic and inspectable, while reserving provider availability and behavior for a separate live gate. Independent validation checks both supporting and contradicting IDs, their returned ledger membership and exact org/service/run scope. Suggested actions have an empty allowlist in the spike.
- **Costs / failure modes:** Offline tests do not establish Gemini reliability, cost or diagnosis quality. ADK 2.11.0 uses its `set_model_response` fallback for the Developer API, with an experimental JSON schema feature warning. Count-token configuration and provider billing reservations remain live-unverified. A valid citation is not causal proof. Sessions/artifacts are not the later durable run ledger.
- **Actual evidence:** Real ADK runner: two fake model calls, one synthetic retrieval, structured result; negative citation/scope/action/budget tests. Live API evidence remains blocked pending credentials/budget; no latency or token claims about Gemini.
- **Revisit:** Live model rejects the fallback or count-token configuration; pricing expiry; real telemetry in Phase 2; durable workers introduced.
- **Interview explanation:** “The spike distinguishes three facts: ADK dispatched a tool, the output passed a schema, and every cited ID came from authorized tool results. Those are testable without claiming that a fake model proved Gemini's quality. A separate live experiment must validate the provider, and later held-out cases must measure diagnosis accuracy.”
- **Follow-ups:** Can a real citation support a wrong claim? Yes. Does the model choose the tenant? No; the tool accepts no scope arguments. Are approvals implemented? No, only a typed envelope; no executor exists. Can local tests unlock Phase 1? Only when all gates, including live model and hosted CI evidence, pass.
- **Related decisions:** DEC-215–219, DEC-224; ADR-001/002/003/012/015.

## Developer clarification — 2026-10-10 (DEC-231)

Foundation implementation and local verification are complete, with hosted CI verified for b0014ab9. Live-model verification is a **separate mandatory outstanding gate before Phase 1 is formally unlocked**. Phase 1 remains LOCKED and unauthorized. This resolves the previous report wording without restarting foundation work or deleting history.

Both keys are now present. The prior absence/budget description above is historical. Live smoke tests are free-tier-only after verification of each exact key-owning account; paid requests are prohibited. ADR-020 and DEC-232–236 extend the same single-agent synthetic spike for Groq. No automatic provider fallback or real telemetry is introduced. See the comparison report for actual verification evidence and blockers.

## Live model verification complete — 2026-10-10 (DEC-237–240)

Direct API and live ADK synthetic scenario verification completed successfully on operator-confirmed Free tier accounts:
- Direct API generation: Gemini (`gemini-3.5-flash`, 1.75s, 61 tokens) PASSED; Groq (`openai/gpt-oss-120b`, 0.86s, 93 tokens) PASSED.
- Live ADK tool dispatch: Gemini (`gemini-3.5-flash`, supported=complete in 11.52s, conflicting=inconclusive in 9.79s) PASSED; Groq (`openai/gpt-oss-120b`, supported=complete in 4.17s, conflicting=inconclusive in 2.96s) PASSED.
- All evidence citations validated deterministically against tool ledgers. Billed spend: $0. Phase 1 remains LOCKED until authorized.
