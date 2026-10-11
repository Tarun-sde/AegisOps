# ADR-024: Incident Lifecycle State Machine, Deterministic Multi-Alert Correlation, and Scoped Read-Only GitHub Integration

- **Date:** 2026-10-11
- **Status:** IMPLEMENTED — UNVERIFIED
- **Owner:** Backend & AI Platform Engineer
- **Scope:** `apps/api`, `agents/incident_investigator`, `examples/shop-api`, `apps/web`
- **Governing Phase:** Phase 4 of `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md`

---

## 1. Context and Problem Statement

AegisOps Phase 1 and 2 established basic Alertmanager webhook ingestion, single-alert incident creation, and autonomous AI investigations. However, three critical operational gaps existed:
1. **Rudimentary Incident Lifecycle:** Incidents were restricted to binary `open` / `resolved` statuses with unvalidated mutations, no role-guarded transition matrix, and no concurrency protection against race conditions.
2. **Alert Fragmentation:** Multiple firing alerts from the same service and environment during an incident episode (e.g. HTTP 500 error spike followed by P95 latency degradation) generated independent, fragmented incidents instead of correlating into a single actionable incident record.
3. **Absence of Release Context:** The investigation agent possessed zero knowledge of recent software deployments or Git commits, leaving it blind to code changes as potential causal factors, or risking naive hallucinations where commit timing is conflated with proven root cause.

---

## 2. Decision and Architecture

### 2.1 Auditable Incident State Machine
We implement an explicit 6-state finite state machine with server-enforced transitions:
- States: `OPEN`, `ACKNOWLEDGED`, `MITIGATING`, `RESOLVED`, `CLOSED`, `REOPENED` (stored as canonical lowercase in PostgreSQL).
- Permitted Transitions:
  - `OPEN` -> `ACKNOWLEDGED`, `MITIGATING`, `RESOLVED`
  - `ACKNOWLEDGED` -> `MITIGATING`, `RESOLVED`
  - `MITIGATING` -> `RESOLVED`
  - `RESOLVED` -> `CLOSED`, `REOPENED`
  - `CLOSED` -> `REOPENED`
  - `REOPENED` -> `ACKNOWLEDGED`, `MITIGATING`, `RESOLVED`
- Guardrails:
  - Non-permitted transitions return HTTP 400 Bad Request with an explicit error detailing from and to states.
  - Role-Based Access Control: Mutating incident status requires at least `member` role (`TenantContext.can("member")`). Viewers receive HTTP 403 Forbidden.
  - Concurrency: Optimistic concurrency control via an integer `version` column on `incidents`. Updates verify matching version or return HTTP 409 Conflict.
  - Audit Trail: Every transition synchronously creates an `IncidentEvent` (`incident_status_changed`) recording actor, timestamp, previous status, new status, and optional reason, as well as an immutable `AuditEvent`.

### 2.2 Deterministic Multi-Alert Correlation Engine
We reject LLM-based alert clustering at the ingestion gateway. Instead, a deterministic, rule-based correlation engine groups incoming Alertmanager alerts:
- **Tenant & Environment Isolation:** Alerts from different organizations or different environments (`production` vs `staging`) can NEVER merge under any condition.
- **Correlation Window:** Configurable 30-minute episode window.
- **Active Episode Merging:** When an alert fires for a service and environment that already has an active incident (`open`, `acknowledged`, `mitigating`, `reopened`) within the correlation window:
  - Identical fingerprint: Deduplicated; records `alert_firing_duplicate`, updates `updated_at`.
  - Distinct fingerprint (e.g., latency alert following 5xx error alert): Correlated into the existing incident; records `alert_correlated` with structured reason `same_service_and_environment_within_active_episode`; increments `correlated_alert_count`; escalates incident severity if the new alert is more severe.
- **Negative Invariants:** Outside the time window, or if previous incidents are `resolved`/`closed`, a new incident is created. Resolution events update the specific alert episode without prematurely closing multi-alert incidents.

### 2.3 Scoped Read-Only GitHub Integration
Contextual code and release evidence is retrieved through a least-privilege GitHub adapter:
- **Zero Write Permissions:** Read-only access restricted to `contents:read` and `deployments:read`. No token write scope, PR creation, or workflow dispatch.
- **Credential Isolation:** GitHub tokens (`GITHUB_TOKEN`) reside strictly in server environment variables. Tokens are never passed to the client bundle, never serialized in API responses, and never exposed to LLM prompts.
- **Repository Scoping:** Services configure authorized repository references (e.g. `owner/repo`). The tool gateway rejects any attempt to query repositories not bound to the tenant's service.
- **Downtime Resilience:** Network timeouts, HTTP 401/403/404, or rate limits gracefully return structured limitation payloads without blocking alert ingestion or local telemetry queries.
- **Commit vs. Deployment Distinction:** Commit metadata is explicitly labeled as `commit_history_only` when formal GitHub Deployment records are absent.

### 2.4 Deployment-Aware Investigation & Claim Support Validation
The Google ADK investigator is equipped with `get_recent_deployments`:
- Bounded payload: Returns top recent deployments/commits within a 60-minute window, persisted as `ev_deploy_...` in `evidence_items`.
- Anti-Hallucination Claim Validation: The evidence validator enforces that:
  1. A deployment preceding an incident is NOT accepted as proven root cause based on timing alone.
  2. High-confidence deployment failure claims require matching runtime error telemetry (exceptions or error traces).
  3. Where telemetry indicates an independent cause (such as third-party payment gateway timeout), hypotheses attributing failure to a deployment without acknowledging contradictions are rejected.

---

## 3. Alternatives Considered and Rejected

1. **LLM-Based Alert Correlation:**
   - *Rejected:* Calling an LLM on every incoming webhook adds 1–3s latency, introduces token costs, is susceptible to non-deterministic grouping, and fails when the model provider is unavailable. Alert ingestion must remain deterministic and highly available.
2. **Unrestricted String Incident Statuses:**
   - *Rejected:* Allowing arbitrary status strings destroys SLA reporting, causes frontend rendering bugs, and prevents reliable webhook automations.
3. **Full-Privilege GitHub Personal Access Tokens (PAT) with Mutation:**
   - *Rejected:* Grants excessive blast radius. Incident investigation requires read-only observation. Remediation actions (Phase 7) must remain strictly decoupled and human-approved.

---

## 4. Consequences and Verification Plan

- **Consequences:** Provides reliable incident lifecycle management, prevents alert notification floods by grouping symptoms into single incidents, and gives the AI investigator access to software change context.
- **Verification:**
  1. Unit tests for transition matrix, invalid transitions, and RBAC enforcement.
  2. Integration tests for multi-alert correlation, duplicate handling, and cross-tenant isolation.
  3. Agent evaluation with controlled fixtures: broken release (T1), unrelated commit (T2), missing deployments (T3), contradictory telemetry (T4), and fake evidence rejection (T5).
  4. End-to-end broken release scenario in `shop-api` demonstrating alert -> correlation -> investigation -> timeline visualization.
