# ADR-027: Incident Simulation Lab, Atomic Remediation Execution, and Verifiable Recovery

- **Status:** ACCEPTED — IMPLEMENTED & VERIFIED
- **Date:** 2026-10-12
- **Author:** AegisOps Engineering (Staff SRE / Distributed Systems)
- **Decisions Governed:** DEC-316 through DEC-330 in `docs/ENGINEERING_DECISIONS.md`
- **Related ADRs:** ADR-001, ADR-003, ADR-006, ADR-011, ADR-015, ADR-022, ADR-023, ADR-026

---

## 1. Context and Problem Statement

AegisOps monitors application telemetry, detects operational failures, and drives AI-assisted investigations using Google ADK. In Phase 6 (ADR-026), we introduced the transactional outbox pattern, internal n8n automation, and deterministic action proposals with exact-hash approvals. However, Phase 6 strictly enforced a **zero-execution barrier** (`DEC-312`), meaning remediation actions stopped at `APPROVED` with no execution capability.

Furthermore, demonstrating and benchmarking the incident lifecycle previously required manual triggers or synthetic static fixtures. To make AegisOps production-grade, demonstrable, and evaluatable (Phase 9 benchmark prerequisite), we require:
1. An **Incident Simulation Lab** capable of injecting real, bounded failures into isolated demonstration services (`shop-api`), generating authentic metrics, logs, traces, and alert events.
2. A deterministic **Simulation Controller** with automatic time-to-live (TTL) expiration and cleanup to prevent lingering broken states without requiring human intervention.
3. A **Sandboxed Remediation Execution Engine** that transforms approved proposals into safe, idempotent staging-only actions (`restart_demo_service`, `rollback_demo_release`).
4. Strict **Security Invariants**: the LLM must never have execution authority; approvals must be validated for exact payload integrity before execution; production environments must be unconditionally rejected; and duplicate or racing execution claims must be safely prevented.
5. Independent **Recovery Verification** distinguishing external command success from verified operational telemetry recovery.

---

## 2. Decision Drivers

- **Security & Blast Radius:** Zero automated production remediation. Staging/demo allowlisted actions only. No arbitrary shell, SSH, host Docker socket, or Kubernetes cluster admin credentials exposed to the agent or API.
- **Transactional Integrity & Concurrency:** Absolute prevention of double-execution or race-condition replay when two approvers or workers trigger actions simultaneously.
- **Fail-Closed Principle:** If permissions, cryptographic payload hashes, target state, or environment cannot be verified, execution is refused.
- **Real Evidence vs. Fabricated Results:** Simulations must produce actual HTTP failures, Prometheus counter increments, Loki structured error logs, and W3C trace spans.
- **Automatic Failure Recovery:** Simulations must have bounded lifespans (default 300s) and reliably reset themselves upon expiration or worker restarts.
- **Developer Interview Defense:** Every architectural choice must be defendable in a senior engineering interview with clear trade-offs, rejection rationale, and concrete evidence.

---

## 3. Considered Alternatives

### 3.1 Simulation Architecture
- **Option A (Rejected): Unrestricted Chaos Engineering Tools (Chaos Mesh / Pumba / LitmusChaos / Arbitrary Docker Commands)**
  - *Why rejected:* Requires root host privileges or Docker daemon socket access (`/var/run/docker.sock`). Exposing the host Docker socket into application containers is a severe privilege escalation vector. Overkill for local development workstations.
- **Option B (Selected — DEC-316): Predefined Scenario Catalog with In-Application Fault Handlers and Shared Secret Protection**
  - *Why selected:* Faults (S01–S06) are implemented directly in the demo service (`shop-api`) with bounded parameters, authenticated via `x-demo-fault-secret`. Operates completely in-process or via HTTP within Docker/Compose. Zero host privilege requirement. 100% reproducible and safe.

### 3.2 Remediation Execution Engine
- **Option A (Rejected): Autonomous Model-Driven Execution**
  - *Why rejected:* Allowing an LLM to directly invoke remediation tools or execute shell commands is fundamentally unsafe. Models hallucinate, are vulnerable to indirect prompt injection in log telemetry, and cannot be trusted with infrastructure mutation.
- **Option B (Rejected): Single-Step Approve-and-Execute API Endpoint**
  - *Why rejected:* Merging approval and execution into a single synchronous HTTP call holds database transactions open across network operations and conflates the distinct roles of the human policy approver and the backend execution runner.
- **Option C (Selected — DEC-320, DEC-321): Two-Phase Atomic Claiming with Row-Level Locking and Idempotent Execution**
  - *Why selected:* Approving a proposal (`POST /approve`) transitions state to `APPROVED` and records an immutable approval hash. Executing a proposal (`POST /execute`) acquires a row-level lock (`FOR UPDATE`), re-verifies exact payload integrity, environment allowlist, and user authorization, atomically claims the proposal into `EXECUTING` via a unique constraint in `action_executions`, commits the database transaction, and then dispatches the isolated executor.

---

## 4. Architectural Specifications

### 4.1 Six Canonical Failure Scenarios (DEC-316, DEC-319)
| ID | Name | Target | Fault Injection | Signals & Observability | Allowed Remediation |
|---|---|---|---|---|---|
| **S01** | Checkout 500 Errors | `shop-api` | Feature flag on `/checkout` throwing payment gateway timeout | HTTP 500 spike, `http_requests_total{status_code="500"}` > 20%, Loki error logs | `restart_demo_service`, `reset_demo_fault` |
| **S02** | Slow DB Queries | `shop-api` | Injected 800ms query delay on product catalog | p95 latency spike, DB span latency in Tempo, slow query warnings | `restart_demo_service`, `reset_demo_fault` |
| **S03** | DB Pool Exhaustion | `shop-api` | Simulated pool contention exhausting all 5 connections | HTTP 503 errors, pool waiting connection gauge, timeout logs | `restart_demo_service`, `reset_demo_fault` |
| **S04** | Broken Release | `shop-api` | Switched build metadata to `v0.1.1-buggy` + commit regression | Build info gauge change, Git commit SHA correlation, 500 errors | `rollback_demo_release`, `restart_demo_service` |
| **S05** | Service Unavailable | `shop-api` | Probe failure mode disabling `/healthz` and rejecting HTTP | `/healthz` 503, probe failures, Prometheus `up == 0` | `restart_demo_service`, `reset_demo_fault` |
| **S06** | Slow Downstream | `shop-api` | Injected 1200ms latency on downstream inventory stub | Distributed trace hierarchy, downstream span latency, timeout logs | `restart_demo_service`, `reset_demo_fault` |

### 4.2 Simulation Lifecycle & Automatic Cleanup (DEC-317, DEC-318)
```text
[Operator / API]
       |
       v
POST /api/v1/simulation/scenarios/{id}/start
       |
       +---> Check no active run for service (Unique lock)
       +---> Create SimulationRun (status=ACTIVE, expires_at = now + 300s)
       +---> Dispatch Fault Activation to shop-api
       +---> Record SimulationEvent (simulation.started, simulation.fault_activated)
       |
       +---> [TTL Watchdog / On-Access Expiry Check]
             If expires_at <= now and status == ACTIVE:
                 Reset fault on shop-api
                 Transition run to EXPIRED (cleanup_status=CLEANED)
                 Record SimulationEvent (simulation.expired)
```

### 4.3 Atomic Execution Invariant & Idempotency (DEC-320, DEC-321)
Execution is permitted **ONLY IF**:
```text
actor_authenticated == TRUE
AND actor_role IN ('admin', 'owner')
AND proposal_exists == TRUE
AND proposal.status == 'APPROVED'
AND proposal.expires_at > now()
AND proposal.environment IN ('staging', 'development')
AND proposal.parameters_hash == approval.parameters_hash
AND target_service.organization_id == actor.organization_id
AND NOT EXISTS (action_executions WHERE proposal_id = proposal.id)
```

Transactional claiming steps:
1. `SELECT * FROM action_proposals WHERE id = :id FOR UPDATE`
2. Assert all conditions above.
3. `UPDATE action_proposals SET status = 'EXECUTING' WHERE id = :id`
4. `INSERT INTO action_executions (proposal_id, status='CLAIMED', ...)` (Unique constraint on `proposal_id`).
5. `COMMIT` claim transaction.
6. Dispatch `RemediationExecutor.execute()`.
7. `UPDATE action_executions SET status = 'SUCCEEDED' / 'FAILED'` and update proposal status.
8. Emit atomic outbox event (`action.execution_succeeded` / `action.execution_failed`).

### 4.4 Operational Recovery Verification (DEC-323)
Executor success does **NOT** equal operational recovery. A restart command may succeed while the service remains failing.
AegisOps executes a distinct recovery verification:
- Query `/healthz` ensuring `status == "ok"` and `fault_active == false`.
- Query `/version` ensuring active release matches expected target release.
- Sample requests ensuring error rate drops below 5%.
- Emit `service.recovery_observed` outbox event only when verified.

---

## 5. Security & Isolation Analysis

1. **Zero Production Execution:** Handlers explicitly reject any target whose environment is `"production"`.
2. **Untrusted Agent Boundary:** ADK investigator tool `create_remediation_proposal` is strictly proposal-only; it inserts a database proposal in `PROPOSED` status and returns metadata. It has zero capability to invoke executors.
3. **Prompt Injection Immunity:** Instructions embedded in log messages or runbooks cannot trigger actions or bypass approval gates. Deterministic backend code owns the execution decision.
4. **Tenant Isolation:** Foreign tenant proposals, simulations, and executions return 404/403. Cross-tenant execution claims fail closed.
5. **Guest Account Protection:** Public demo / viewer role cannot start simulations, reset faults, approve proposals, or trigger execution.

---

## 6. Interview Defense & Technical Trade-offs

### 30-Second Summary
> "In Phase 7, we engineered a production-grade Incident Simulation Lab and an atomic human-approved remediation engine. Instead of dangerous host-level chaos scripts, we built six deterministic, in-application fault scenarios (S01–S06) into our microservice with automatic TTL cleanup. For remediation, we enforced a strict two-phase execution claim using PostgreSQL row-level locks, unique proposal constraints, and exact SHA-256 parameter hash re-validation, ensuring that unapproved, expired, tampered, or racing actions can never execute."

### Key Interview Questions & Answers
- **Q: Why not use Chaos Mesh or Docker socket mounting to stop containers?**
  - *A:* Mounting the host Docker socket (`/var/run/docker.sock`) into an API or runner container gives anyone who compromises that container full root access to the host machine. By using in-application fault handlers protected by authenticated secrets, we simulate identical network latency, 500 error rates, connection exhaustion, and probe failures with zero host attack surface.
- **Q: How did you solve the distributed race condition where two operators approve or execute an action simultaneously?**
  - *A:* We decoupled approval from execution and utilized PostgreSQL row-level locking (`FOR UPDATE`) with a unique database constraint on `action_executions(proposal_id)`. The first transaction transitions the proposal from `APPROVED` to `EXECUTING` and commits the claim record. Any subsequent or concurrent request hits the state conflict check or unique constraint violation and fails immediately, guaranteeing once-only execution.
- **Q: Why do you separate action execution success from recovery verification?**
  - *A:* Infrastructure actions often return HTTP 200 or exit code 0 even if the underlying workload is crash-looping or misconfigured. Equating command completion with incident resolution is a common SRE anti-pattern. AegisOps explicitly waits for health probes and metric thresholds to normalize before recording a `service.recovery_observed` event.
