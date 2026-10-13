# Security Model — Verified Controls & Defense-in-Depth Baseline

**Status:** Verified controls in place across Phases 1–7. Source: master plan §§3.3, 4.3–4.7, 8, 14; ADR-001 through ADR-027.

## Trust boundaries

| Boundary | Untrusted inputs | Enforcement implemented | Status |
|---|---|---|---|
| External monitoring to FastAPI | Webhook payloads, signatures, timestamps | Authenticate source; validate schema, body limits, replay and rate limits | VERIFIED |
| Telemetry to ADK | Logs, traces, document text, GitHub metadata | Redact secrets; mark untrusted; enforce bounded read-only tools | VERIFIED |
| Operational runbooks to RAG | Raw uploaded documents | Regex credential scanner redacting private keys, DB URLs, bearer tokens prior to embedding | VERIFIED |
| ADK to backend | Tool requests, diagnosis, suggested actions | Explicit service scope, allowlists, budgets, schema and evidence-ID validator | VERIFIED |
| Tenant separation | Every service/evidence/doc ID | Derive organization from authenticated session; DB-level WHERE pre-filtering on pgvector & SQL | VERIFIED |
| Outbox to n8n Webhook | Event envelopes and delivery attempts | HMAC-SHA256 envelope signing, 300s clock skew window, 64KB payload bounds, tenant isolation | VERIFIED |
| User to action proposal | Approval requests and action parameters | Strict catalog schema, canonical SHA-256 hash lock, lazy + periodic expiry, RBAC (admin/owner only), append-only audit | VERIFIED |
| Proposal to execution (Phase 6 baseline) | Remediation execution attempts | ZERO EXECUTION IN PHASE 6: `execute_action` raised `NotImplementedError` | SUPERSEDED by Phase 7 |
| Proposal to execution (Phase 7 Remediation Executor) | Action execution requests and target service scopes | Staging-only enforcement (`staging` or `development` only; production targets strictly rejected before network dispatch), service allowlist (`shop-api`, `demo-service`, `cart-service`), allowlisted actions (`restart_demo_service`, `rollback_demo_release`, `request_staging_rollback`), two-phase row lock claim (`SELECT FOR UPDATE`), database unique constraint `uq_execution_proposal_id`, exact SHA-256 parameter hash re-validation against approval record | VERIFIED |
| Operator to Simulation Lab | Fault injection scenario requests | Predefined catalog of 6 bounded scenarios (S01–S06), `admin`/`owner` RBAC requirement, staging-only environment target, single active simulation per service concurrency guard with row lock, bounded TTL (default 300s) with lazy and scheduled Celery Beat watchdog cleanup | VERIFIED |
| Recovery verification | Service operational health assertions | Decoupled from command execution; independent HTTP `/healthz` probe verification, outbox event emission (`service.recovery_observed`), audit logging | VERIFIED |
| Public demonstration | Guest interactions and fault controls | Read-only synthetic demo; admin simulation controls isolated | VERIFIED |

## Zero-tolerance release blockers

- Cross-tenant data leak in tests (VERIFIED: 0 records leaked across tenants).
- An LLM/tool bypass of read-only policy (VERIFIED: ReadOnlyToolGateway strictly enforced).
- Fabricated evidence citation displayed as valid (VERIFIED: Validator rejects ungrounded citations with `ValueError: Unknown evidence reference`).
- Unapproved, expired, changed, replayed, or production remediation executed (VERIFIED: Exact SHA-256 parameter hash matching, status guard, staging-only allowlist boundary, PostgreSQL row-level locks and database unique constraint on `action_executions(proposal_id)` preventing execution races).
- Forged or replayed outbox webhooks accepted (VERIFIED: Constant-time HMAC-SHA256 validation + 300s replay window).
- Credentials or protected production telemetry disclosed in UI, prompts or logs (VERIFIED: deterministic redaction scanner).

## Verified Test Suites

- Negative RBAC and broken-object-authorization tests (`test_tenants_and_auth.py`, `test_phase6_outbox_and_proposals.py`).
- Cross-tenant runbook isolation and fake citation rejection (`test_rag_subsystem.py`, `scripts/verify_phase5_rag_e2e.py`).
- Outbox transactional publication, lease claiming, retry backoff, HMAC signature verification, and proposal lifecycle (`test_phase6_outbox_and_proposals.py`, `scripts/verify_phase6_outbox_n8n_e2e.py`).
- Webhook signature/replay/duplicate-event tests (`test_webhooks_and_incidents.py`).
- Phase 7 simulation lifecycle, watchdog cleanup, staging executor boundary, and exact hash verification (`test_phase7_simulation_and_remediation.py`, `test_simulation_expiry_scheduler.py`, `scripts/verify_phase7_simulation_remediation_e2e.py`).
- PostgreSQL multi-worker concurrency verification: remediation claim race, watchdog expiry reconciliation, outbox delivery leasing (`test_integration.py` via `docker-compose.verify.yml`).
- End-to-end browser release gate: isolated Playwright tests, Beat non-root UID 10001 scheduler, unattended fault reset (`make browser`).
- Secret scanning and dependency vulnerability audit (`pip-audit`, `npm audit`).
