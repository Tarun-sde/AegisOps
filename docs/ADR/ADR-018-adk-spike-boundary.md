# ADR-018 — Separate framework proof from live model proof

- **Date:** 2026-10-10
- **Status:** IMPLEMENTED — UNVERIFIED for live Gemini; offline dispatch verified separately.
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
