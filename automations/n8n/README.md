# AegisOps — Internal n8n Automation Workflows

## 1. Architectural Role and Boundaries

In AegisOps, **PostgreSQL is the single authoritative source of truth** for all incident states, investigation findings, and remediation proposal decisions.

`n8n` functions strictly as an **outbound notification and integration adapter**, not a state store.
- **Outbox Driven:** Events reach n8n only *after* the triggering PostgreSQL transaction has committed durably.
- **No Inbound State Mutation:** n8n cannot mutate incident lifecycle or approve remediation actions directly.
- **Fail-Safe Decoupling:** An outage, slow response, or failure in n8n does NOT block incident ingestion, telemetry collection, or AI investigations.

---

## 2. Licensing Compliance & Permitted Scope (DEC-306)

AegisOps self-hosts **n8n Community Edition**, which is licensed under the [Sustainable Use License](https://docs.n8n.io/sustainable-use-license/).

### Strictly Prohibited Under AegisOps Architecture:
1. **No Embedded Customer Workflow Editor:** AegisOps does not embed the n8n canvas into the web application.
2. **No Workflow-as-a-Service:** AegisOps does not expose n8n to multi-tenant customers to create or edit automations.
3. **No AI-Generated Workflows:** LLMs are never permitted to modify or create workflow topologies.
4. **No Direct Execution Triggers:** Workflows never trigger production shell, SSH, or container mutations.

### Permitted Internal Scope:
- Operator-authored, version-controlled notification workflows maintained directly in this directory (`automations/n8n/workflows/`).
- Dispatches to team notification channels (Slack, Discord, Email) and internal operational ticketing sinks.

---

## 3. Workflow Catalog

| File | Trigger Event | Destination / Output |
|---|---|---|
| `incident-created.json` | `incident.created` | Formatted incident alert with severity, service name, and direct link. |
| `incident-investigated.json` | `investigation.completed` | AI investigation summary: top causal hypothesis, confidence level, verified evidence count, and link. |
| `approval-requested.json` | `proposal.created` | Action proposal review notification detailing service, catalog ID, risk classification, parameters hash, and link to AegisOps approval screen. |
| `incident-resolved.json` | `incident.resolved` | Incident resolution broadcast with resolution timestamp and closing actor. |

---

## 4. Security & Authentication Contract (DEC-303, DEC-304)

All outbound events from AegisOps to n8n are authenticated via HMAC-SHA256 headers:
- `X-AegisOps-Event-ID`: Unique event UUID.
- `X-AegisOps-Timestamp`: ISO-8601 UTC timestamp.
- `X-AegisOps-Key-ID`: Key version (`v1`).
- `X-AegisOps-Signature`: `sha256={hmac_digest}` computed over canonical representation `f"{timestamp}.{event_id}.{sha256(payload)}"` using `AEGISOPS_WEBHOOK_SECRET`.

### Replay & Skew Defense:
- Max allowable clock skew: $\pm 300$ seconds (5 minutes). Stale timestamps are rejected.
- Webhook endpoints enforce constant-time digest comparison (`crypto.timingSafeEqual` or `secrets.compare_digest`).

### Receiver Idempotency:
- Every event envelope includes an immutable `idempotency_key`.
- Receiving sinks deduplicate against previously seen keys, guaranteeing that retry dispatches never generate duplicate tickets or alerts.

---

## 5. Deployment and Verification

n8n is integrated into `docker-compose.yml` under the optional `automation` profile:
```bash
# Start AegisOps with n8n automation profile
docker compose --profile automation up -d n8n
```

Workflows can be imported directly into n8n using the n8n CLI:
```bash
docker compose exec n8n n8n import:workflow --input=/path/to/workflow.json
```
