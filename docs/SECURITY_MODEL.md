# Security Model — Pre-implementation Baseline

**Status:** Verified controls in place across Phases 1–5. Source: master plan §§3.3, 4.3–4.7, 8, 14; ADR-001 through ADR-025.

## Trust boundaries

| Boundary | Untrusted inputs | Enforcement implemented | Status |
|---|---|---|---|
| External monitoring to FastAPI | Webhook payloads, signatures, timestamps | Authenticate source; validate schema, body limits, replay and rate limits | VERIFIED |
| Telemetry to ADK | Logs, traces, document text, GitHub metadata | Redact secrets; mark untrusted; enforce bounded read-only tools | VERIFIED |
| Operational runbooks to RAG | Raw uploaded documents | Regex credential scanner redacting private keys, DB URLs, bearer tokens prior to embedding | VERIFIED |
| ADK to backend | Tool requests, diagnosis, suggested actions | Explicit service scope, allowlists, budgets, schema and evidence-ID validator | VERIFIED |
| Tenant separation | Every service/evidence/doc ID | Derive organization from authenticated session; DB-level WHERE pre-filtering on pgvector & SQL | VERIFIED |
| User to action executor | Approval request and action params | RBAC, exact immutable hash, expiry, staging allowlist, atomic state changes | DESIGNED |
| Public demonstration | Guest interactions and fault controls | Read-only synthetic demo; admin simulation controls isolated | VERIFIED |

## Zero-tolerance release blockers

- Cross-tenant data leak in tests (VERIFIED: 0 records leaked across tenants).
- An LLM/tool bypass of read-only policy (VERIFIED: ReadOnlyToolGateway strictly enforced).
- Fabricated evidence citation displayed as valid (VERIFIED: Validator rejects ungrounded citations with `ValueError: Unknown evidence reference`).
- Unapproved, expired, changed, or replayed remediation executed (Enforced in staging executor).
- Credentials or protected production telemetry disclosed in UI, prompts or logs (VERIFIED: deterministic redaction scanner).

## Verified Test Suites

- Negative RBAC and broken-object-authorization tests (`test_tenants_and_auth.py`).
- Cross-tenant runbook isolation and fake citation rejection (`test_rag_subsystem.py`, `scripts/verify_phase5_rag_e2e.py`).
- Webhook signature/replay/duplicate-event tests (`test_webhooks_and_incidents.py`).
- Secret scanning and dependency vulnerability audit (`pip-audit`, `npm audit`).
