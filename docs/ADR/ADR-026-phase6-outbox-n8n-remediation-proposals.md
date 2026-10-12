# ADR-026: Reliable Transactional Outbox, Internal n8n Automation Workflows, and Human-Governed Remediation Proposals

- **Date:** 2026-10-12
- **Status:** ACCEPTED — DESIGN ONLY
- **Owner:** Principal Distributed Systems & Security Architect
- **Scope:** `apps/api/app/outbox`, `apps/api/app/actions`, `automations/n8n`, `apps/worker/tasks.py`, `apps/web/app/app/proposals`
- **Governing Phase:** Phase 6 of `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md`

---

## 1. Context and Problem Statement

In automated incident response and SRE platforms, connecting real-time incident state changes to external notification sinks (Slack, Discord, email, ticketing) and proposing remediation actions present two core failure modes:

1. **The Dual-Write Failure Mode:**
   If the API writes incident or lifecycle state to PostgreSQL and immediately sends an HTTP notification to an external webhook (e.g. n8n or Slack), an unexpected network failure, webhook timeout, or process crash leaves the system in an inconsistent state: either the incident was created but no alert was sent, or the alert was sent but the database transaction rolled back.
   Conversely, publishing asynchronously via an in-memory queue (like Celery without persistent event state) loses events on worker crashes and offers zero durable delivery tracking or auditability.

2. **The Autonomous Remediation Hazard:**
   Giving an AI agent direct, unconstrained access to shell commands, container lifecycles, or cloud infrastructure mutation is catastrophic in production. Even if an LLM is 90% accurate, hallucinated parameters, malicious prompt injection from attacker-controlled log telemetry, or timing races can cause devastating infrastructure damage.

Phase 6 resolves both hazards with a hardened, auditable architectural foundation:
- A **PostgreSQL Transactional Outbox** guaranteeing reliable, atomic at-least-once event publication.
- **Signed HMAC-SHA256 Webhook Delivery** with timestamp skew limits and receiver-side deduplication.
- **Operator-Authored n8n Workflows** restricted strictly to internal automation under Community licensing boundaries.
- A **Human-Governed Remediation Proposal Service** with immutable parameter schemas, SHA-256 canonical hashing, RBAC role-gated approval, and explicit non-execution in Phase 6.

---

## 2. Decision and Architecture

### 2.1 PostgreSQL Transactional Outbox Over Dual-Write and Message Bus
We strictly implement the Transactional Outbox pattern in PostgreSQL:
- **Atomic Persistence:** When an incident is created/resolved, an investigation finishes, or a proposal is created/approved, the state change and an `outbox_events` record are committed in the **exact same database transaction**.
- **Rollback Safety:** If the incident transaction fails or rolls back, zero outbox event is ever written.
- **Decoupled Delivery:** External delivery to n8n or notification sinks is executed asynchronously by background workers after the transaction is durable in PostgreSQL. Webhook timeouts or third-party outages cannot block or delay incident ingestion.
- **At-Least-Once Semantics:** The system provides guaranteed at-least-once delivery with exponential backoff and jitter. Exactly-once delivery across distributed systems is impossible without end-to-end distributed transactions; instead, receiver-side deduplication guarantees idempotent side effects.

### 2.2 Concurrency-Safe Leasing and Delivery Worker
The outbox delivery worker (`process_outbox_events`):
- Claims batches using PostgreSQL row locking (`FOR UPDATE SKIP LOCKED`) or lease timestamps (`locked_until`), preventing concurrent workers from processing the same event.
- Network requests are made **outside** the database transaction, preventing transaction pooling starvation during slow HTTP requests.
- Transient failures (HTTP 5xx, 429, timeouts) increment `attempt_count` and compute exponential backoff with random jitter.
- Permanent failures or attempts exceeding `max_attempts` (default 5) transition to `DEAD_LETTERED`, preserving error summaries for operator inspection.

### 2.3 Signed HMAC-SHA256 Delivery Envelope and Idempotency
All webhook dispatches from AegisOps carry cryptographically signed headers:
- `X-AegisOps-Event-ID`: Unique event UUID.
- `X-AegisOps-Timestamp`: ISO-8601 UTC timestamp.
- `X-AegisOps-Key-ID`: Key version identifier (`v1`).
- `X-AegisOps-Signature`: `sha256={hmac_hex}` computed over canonical string `f"{timestamp}.{event_id}.{sha256(payload)}"` using a shared secret.
- Constant-time verification (`secrets.compare_digest` / `hmac.compare_digest`) and clock-skew tolerance (+/- 300 seconds) prevent timing attacks and replay exploits.
- Receiving sinks enforce durable idempotency deduplication by `idempotency_key` and `event_id`, ensuring repeated delivery attempts do not produce duplicate logical tickets.

### 2.4 Internal n8n Automation Workflows & Licensing Boundary
We deploy self-hosted n8n Community in Docker Compose under the optional `automation` profile:
- **Licensing Compliance:** n8n Community is governed by the Sustainable Use License. In accordance with license terms, AegisOps uses n8n **strictly for internal, operator-authored automation workflows**.
- **No Embedded Customer Editor:** AegisOps will never expose an embedded n8n workflow editor, customer-facing workflow builder, or AI-generated workflow deployment.
- **Workflow Versioning:** All 4 initial workflows (`incident-created`, `incident-investigated`, `approval-requested`, `incident-resolved`) are versioned in `automations/n8n/workflows/`.
- **Resource Discipline:** Memory is capped at 384MB; execution history is pruned after 7 days (168 hours); the core AegisOps stack starts and runs completely independently when n8n is disabled.

### 2.5 Remediation Proposals: Immutable Parameters and Exact-Payload Approval
Remediation actions are structured through a deterministic domain model:
- **Typed Action Catalog:** Supported actions (`restart_demo_service`, `rollback_demo_release`, `request_staging_rollback`) are strictly bounded by typed parameter schemas, allowed environments (`staging`, `development`), and risk levels. Arbitrary shell commands, container IDs, or scripts are impossible.
- **Canonical Parameter Hashing:** Proposal creation computes a canonical SHA-256 hash (`parameters_hash`) over `json.dumps(params, sort_keys=True, separators=(",", ":"))`.
- **Exact-Payload Approval:** An approval requires `admin` or `owner` role and must supply the exact `parameters_hash`. If a proposal's parameters are tampered with or modified, the hash check fails and approval is rejected.
- **Time-Bounded Expiry:** Proposals have an explicit `expires_at` timestamp (default 30 minutes). Stale proposals transition to `EXPIRED` and can never be approved.
- **Strict Execution Boundary:** Phase 6 implements proposals, lifecycle state transitions, RBAC approval, and audit trails. **Zero execution engine exists in Phase 6.** Approval cannot execute infrastructure mutations until the Phase 7 security gate.

---

## 3. Comparison of Alternatives

| Dimension | Transactional Outbox (Selected) | Direct Webhook in Request | Redis / Celery Only |
|---|---|---|---|
| **Atomicity** | 100% atomic with DB state | None (dual-write hazard) | None (lost if Redis restarts before commit) |
| **Outage Resilience** | Durable in PostgreSQL; survives API/worker restart | Lost if destination down | Lost if queue unpersisted or broker evicts |
| **Auditability** | Complete delivery attempt history | None | Temporary Celery result backend |
| **Operational Cost** | Reuses existing PostgreSQL | None | Requires Redis broker tuning |

---

## 4. Technical Trade-Offs and Risks

- **Downside:** At-least-once delivery means destination sinks might occasionally receive duplicate deliveries during network splits.
  - *Mitigation:* Receivers must implement idempotency deduplication keyed on `event_id` or `idempotency_key`. The demo sink demonstrates this explicitly.
- **Downside:** Celery outbox polling introduces minor latency (typically 500ms–2s) compared to synchronous HTTP dispatches.
  - *Mitigation:* This 1-second delay is standard for notification pipelines and eliminates request latency and timeout cascades from the main API thread.
- **Downside:** Action proposals cannot be executed yet.
  - *Mitigation:* Deliberate security decision. In an SRE platform, an unverified executor is a liability; proving proposal governance and approval invariants first is required for safety.

---

## 5. Interview Defense (30–60 Second Explanation)

> "In Phase 6, we solved the distributed dual-write problem by implementing a PostgreSQL Transactional Outbox. When an incident or investigation state changes, we write the outbox event in the same ACID transaction. Our background workers claim events using PostgreSQL `FOR UPDATE SKIP LOCKED`, sign them with HMAC-SHA256, and deliver them to internal n8n workflows with exponential backoff and jitter. Because external delivery is at-least-once, we enforce durable idempotency deduplication on the receiver to prevent duplicate tickets. For remediation, we decoupled AI diagnosis from execution: the agent can only suggest catalog-approved actions, which are validated into immutable, SHA-256 hashed proposals that require admin RBAC approval before any staging action can ever be taken in Phase 7."

---

## 6. Follow-up Technical Questions

1. **Why not use Kafka or RabbitMQ instead of PostgreSQL outbox?**
   *Answer:* Introducing Kafka or RabbitMQ adds significant operational overhead, memory consumption, and distributed transaction complexity (2PC). PostgreSQL already owns our ACID transaction boundary. Storing outbox events in PostgreSQL guarantees atomic consistency without another stateful distributed cluster.
2. **How do you handle worker crashes during HTTP delivery?**
   *Answer:* Workers acquire a time-bounded lease (`locked_until`). If a worker is SIGKILL'd during an HTTP call, the lease expires after 60 seconds, allowing another worker to safely reclaim the event and retry delivery.
3. **Can an attacker bypass approval by altering the proposal in the database?**
   *Answer:* The approval transaction verifies that the approver's submitted payload hash matches the proposal's original SHA-256 `parameters_hash`. Tampering invalidates the hash and aborts the approval. Furthermore, approvals are restricted to `admin` and `owner` roles via server-side session RBAC.
