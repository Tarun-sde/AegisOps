# Engineering Decisions vs. Codebase Implementation Reconciliation

**Document Scope:** Reconciliation of critical architecture and security decisions with the active AegisOps implementation, covering the Transactional Outbox, HMAC Event Signing, Replay Windows, Action Proposal Hashes, and the Staging-Only Executor Boundary.  
**Governing Documents:** `docs/ENGINEERING_DECISIONS.md` (DEC-300, DEC-301, DEC-302, DEC-303, DEC-309, DEC-321, DEC-322).  
**Code References:** `apps/api/app/outbox/`, `apps/api/app/actions/`, `apps/api/app/models.py`.

---

## 1. Summary Matrix

| Decision Area | Governing DEC | Stated Decision Requirement | Code Implementation Reality | Status |
|---|---|---|---|---|
| **Transactional Outbox** | DEC-300, DEC-301, DEC-302 | Atomically committed `outbox_events` table; `<=64KB` bounds; multi-worker `FOR UPDATE SKIP LOCKED` leasing (60s); exponential backoff with jitter and dead-lettering. | Fully implemented in `apps/api/app/models.py:321-353`, `apps/api/app/outbox/service.py:16-71`, and `apps/api/app/outbox/dispatcher.py:32-188`. Verified with PostgreSQL integration tests. | **MATCH** *(Note: DEC status headers in log still read `ACCEPTED — DESIGN ONLY`)* |
| **HMAC Event Signing** | DEC-303 | Canonical string `f"{timestamp}.{event_id}.{sha256(payload)}"`, HMAC-SHA256 signature prefixed with `sha256=`, transmitted via `X-AegisOps-*` headers, timing-safe validation. | Exactly matches in `apps/api/app/outbox/signer.py:18-38,76-88` and `apps/api/app/outbox/dispatcher.py:114-127`. Uses `hmac.compare_digest`. | **MATCH** |
| **Replay Window** | DEC-303 | Constant-time comparison, 300-second maximum clock skew bounds (`MAX_SKEW_SECONDS = 300`). | Implemented in `apps/api/app/outbox/signer.py:11,61-75`. Rejects requests exceeding 300s clock skew tolerance against UTC. | **MATCH** |
| **Action Proposal Hash** | DEC-309, DEC-321 | Canonical serialization `json.dumps(params, sort_keys=True, separators=(",", ":"))` and SHA-256 hash. Re-verified at creation, approval, and immediately before execution. | Implemented in `apps/api/app/actions/service.py:65-70,153,275,492-498`. Fails closed if parameter tampering occurs. | **MATCH** |
| **Staging-Only Executor Boundary** | DEC-322 | Narrow allowlist; staging/development only; production targets fail closed raising immediate `SecurityException`; implements `restart_demo_service` and `rollback_demo_release`. | Implemented in `apps/api/app/actions/executor.py` and `apps/api/app/actions/service.py:482`. Enforces staging/development and allowlisted services (`shop-api`, `demo-service`, `cart-service`). Contains slight deviations in exception naming and additional action support (detailed below). | **SUBSTANTIAL MATCH (Minor Deviations Listed)** |

---

## 2. Detailed Technical Reconciliations

### 2.1 Transactional Outbox (DEC-300, DEC-301, DEC-302)

- **DEC-300 Stated Behavior:**
  - Database table `outbox_events` in PostgreSQL committed in same transaction as domain state mutations.
  - Strict payload size boundary of $\le 64$ KB.
- **Code Reality:**
  - `apps/api/app/models.py:321-353`: `OutboxEvent` table defines `id`, `organization_id`, `aggregate_type`, `aggregate_id`, `event_type`, `event_version`, `payload` (JSON), `idempotency_key` (String(128)), `status`, `attempt_count`, `max_attempts` (default 5), `next_attempt_at`, `locked_until`, `delivered_at`, `last_error_code`, `last_error_summary`.
  - `apps/api/app/outbox/service.py:16`: `MAX_PAYLOAD_BYTES = 65536` (64 KB).
  - `apps/api/app/outbox/service.py:35-39`: Raises `ValueError("Outbox event payload exceeds maximum size limit of 65536 bytes")` if payload exceeds 64 KB.
  - `create_outbox_event` (`apps/api/app/outbox/service.py:30-34`) intentionally does not commit the database session, allowing caller to commit domain entities and outbox events atomically.
- **DEC-301 Stated Behavior:**
  - Claim pending events with `FOR UPDATE SKIP LOCKED` and 60-second `locked_until` lease.
  - HTTP network dispatch occurs strictly outside database transaction.
- **Code Reality:**
  - `apps/api/app/outbox/dispatcher.py:66-79`: PostgreSQL dialect branches on `.with_for_update(skip_locked=True)`.
  - `apps/api/app/outbox/dispatcher.py:84-92`: Sets `ev.locked_until = now + timedelta(seconds=lease_seconds)` (default 60s), sets `ev.status = "PROCESSING"`, increments `attempt_count`, and commits the claim transaction immediately.
  - `apps/api/app/outbox/dispatcher.py:99-148`: Dispatches HTTP network request outside the claiming transaction.
- **DEC-302 Stated Behavior:**
  - Exponential backoff with random jitter: `next_attempt_at = now + min(3600, base * 2^(attempt-1)) + jitter`.
  - Transitions to `DEAD_LETTERED` on attempt exhaustion (default 5) or non-429 client errors (4xx).
- **Code Reality:**
  - `apps/api/app/outbox/dispatcher.py:32-43`: `calculate_backoff_delay(attempt, base_seconds=2.0, max_seconds=3600.0, jitter=True)` computes exact formula with `random.uniform(0.1, 1.0)` jitter.
  - `apps/api/app/outbox/dispatcher.py:174-188`: Transitions to `DEAD_LETTERED` if `attempt_count >= max_attempts` or `400 <= status_code < 500 and status_code != 429`.

---

### 2.2 HMAC Event Signing Envelope (DEC-303)

- **DEC-303 Stated Behavior:**
  - Canonical signing string: `f"{timestamp}.{event_id}.{sha256(payload)}"`.
  - Signed with HMAC-SHA256, transmitted via `X-AegisOps-Signature`, `X-AegisOps-Timestamp`, and `X-AegisOps-Event-ID`.
  - Constant-time validation.
- **Code Reality:**
  - `apps/api/app/outbox/signer.py:18-21`:
    ```python
    def build_canonical_string(timestamp_str: str, event_id: str, payload_bytes: bytes) -> str:
        payload_digest = hashlib.sha256(payload_bytes).hexdigest()
        return f"{timestamp_str}.{event_id}.{payload_digest}"
    ```
  - `apps/api/app/outbox/signer.py:30-38`: Generates HMAC-SHA256 digest formatted with `sha256={sig}` prefix.
  - `apps/api/app/outbox/dispatcher.py:114-120`: Sets HTTP request headers:
    - `X-AegisOps-Event-ID: str(event.id)`
    - `X-AegisOps-Timestamp: timestamp_str`
    - `X-AegisOps-Key-ID: "v1"`
    - `X-AegisOps-Signature: signature`
  - `apps/api/app/outbox/signer.py:86`: Compares provided and recomputed signatures using `hmac.compare_digest(provided_sig, expected_sig)`.

---

### 2.3 Replay Window & Clock Skew Limits (DEC-303)

- **DEC-303 Stated Behavior:**
  - 300-second maximum clock skew window tolerance.
- **Code Reality:**
  - `apps/api/app/outbox/signer.py:11`: `MAX_SKEW_SECONDS = 300` (5 minutes).
  - `apps/api/app/outbox/signer.py:61-72`:
    ```python
    clean_ts = timestamp_str.replace("Z", "+00:00")
    event_time = datetime.fromisoformat(clean_ts)
    now = datetime.now(UTC)
    skew = abs((now - event_time).total_seconds())
    if skew > max_skew_seconds:
        return (False, f"Timestamp skew ({skew:.1f}s) exceeds allowed limit of {max_skew_seconds}s")
    ```
  - Enforces absolute UTC skew check rejecting timestamps older than 300s or post-dated beyond 300s.

---

### 2.4 Action Proposal Hash (DEC-309, DEC-321)

- **DEC-309 & DEC-321 Stated Behavior:**
  - Deterministic serialization: `json.dumps(params, sort_keys=True, separators=(",", ":"))` and SHA-256 hash.
  - Approval and execution require exact hash validation.
- **Code Reality:**
  - `apps/api/app/actions/service.py:65-70`:
    ```python
    def compute_parameters_hash(params: dict[str, Any]) -> str:
        canonical = json.dumps(params, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    ```
  - `apps/api/app/actions/service.py:153`: Proposal creation stores `parameters_hash`.
  - `apps/api/app/actions/service.py:275-278`: Proposal approval validates:
    ```python
    if approval_data.expected_parameters_hash != proposal.parameters_hash:
        raise ProposalHashMismatchError(...)
    ```
  - `apps/api/app/actions/service.py:492-498`: Proposal execution re-computes parameter hash from stored `proposal.immutable_parameters`:
    ```python
    recomputed_hash = compute_parameters_hash(proposal.immutable_parameters)
    if recomputed_hash != proposal.parameters_hash:
        raise ProposalHashMismatchError("Parameters hash tampering detected! Execution aborted.")
    if not proposal.approval or proposal.approval.parameters_hash != proposal.parameters_hash:
        raise ProposalHashMismatchError("Approval parameters hash mismatch! Execution aborted.")
    ```

---

### 2.5 Staging-Only Executor Boundary (DEC-322)

- **DEC-322 Stated Behavior:**
  - Strict staging-only execution engine with narrow allowlist.
  - Implements two allowlisted actions: `restart_demo_service` and `rollback_demo_release`.
  - Execution against production targets raises immediate `SecurityException`.
- **Code Reality & Discrepancies:**
  1. **Exception Class Name:**
     - DEC-322 states production targets raise `SecurityException`.
     - In `apps/api/app/actions/executor.py:23,61-64`, the raised exception is `ExecutionSecurityError`:
       ```python
       class ExecutionSecurityError(Exception):
           """Raised when an execution violates environment or safety constraints."""
       ```
     - In `apps/api/app/actions/service.py:482-485`, the pre-dispatch check raises standard `ValueError`:
       ```python
       if proposal.environment == "production":
           raise ValueError("Remediation execution against production targets is strictly forbidden.")
       ```
  2. **Allowed Action Catalog Set:**
     - DEC-322 states the executor implements *"only two allowlisted staging actions: restart_demo_service ... and rollback_demo_release"*.
     - In `apps/api/app/actions/executor.py:89-137`, the executor implements **three** actions:
       - `restart_demo_service` (lines 89–104)
       - `rollback_demo_release` (lines 105–121)
       - `request_staging_rollback` (lines 122–137, rollback by commit SHA)
  3. **Target Service Allowlist Enforcement:**
     - `apps/api/app/actions/executor.py:72-76` explicitly restricts target services to:
       `allowlisted_services = ("shop-api", "demo-service", "cart-service")`
       Raising `ExecutionSecurityError` for any other service name.
  4. **Decision Log Status Label:**
     - In `docs/ENGINEERING_DECISIONS.md`, DEC-300 through DEC-310 still have header status `ACCEPTED — DESIGN ONLY`, whereas all outbox and proposal functionality was implemented and verified in Phase 6 and Phase 7. DEC-321 and DEC-322 are correctly labeled `Status: VERIFIED`.

---

## 3. Conclusion

The codebase matches the architectural intent, cryptographic security guarantees, and concurrency mechanisms described in the engineering decision records. The discrepancies identified in the staging-only executor boundary are minor naming and extension differences (`ExecutionSecurityError` / `ValueError` vs `SecurityException`, and the inclusion of `request_staging_rollback` alongside the two actions listed in DEC-322).
