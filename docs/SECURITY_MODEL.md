# Security Model — Pre-implementation Baseline

**Status:** Planned controls; no security test or certification has yet been completed. Source: master plan §§3.3, 4.3–4.7, 8, 14.

## Trust boundaries

| Boundary | Untrusted inputs | Enforcement planned |
|---|---|---|
| External monitoring to FastAPI | Webhook payloads, signatures, timestamps | Authenticate source; validate schema, body limits, replay and rate limits |
| Telemetry to ADK | Logs, traces, document text, GitHub metadata | Redact data; mark untrusted; enforce bounded read-only tools |
| ADK to backend | Tool requests, diagnosis, suggested actions | Explicit service scope, allowlists, budgets, schema and evidence-ID validator |
| User to action executor | Approval request and action params | RBAC, exact immutable hash, expiry, staging allowlist, atomic state changes |
| Tenant separation | Every service/evidence/doc ID | Derive organization from authenticated session; DB-level filtering/tests |
| Public demonstration | Guest interactions and fault controls | Read-only synthetic demo; admin simulation controls isolated |

## Zero-tolerance release blockers

- Cross-tenant data leak in tests.
- An LLM/tool bypass of read-only policy.
- Fabricated evidence citation displayed as valid.
- Unapproved, expired, changed, or replayed remediation executed.
- Credentials or protected production telemetry disclosed in UI, prompts or logs.

## Test plan — not executed

- Negative RBAC and broken-object-authorization tests.
- Prompt-injection logs/runbooks; exfiltration attempts.
- SSRF and internal network access checks for configured URL probes/connectors.
- Webhook signature/replay/duplicate-event tests.
- Secret scanning, dependency scanning, container hardening.
- Concurrent approve/execute race tests and backup/restore drills.

Exact libraries, key storage, session strategy and auth provider are Phase 0–3 decisions requiring their own records and verified integration tests.
