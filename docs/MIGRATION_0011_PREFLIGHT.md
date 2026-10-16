# Migration 0011 Preflight Operational Runbook: Active Incident Fingerprint Uniqueness

**Canonical path:** `docs/MIGRATION_0011_PREFLIGHT.md`  
**Target migration:** `apps/api/alembic/versions/0011_active_incident_fingerprint_unique.py`  
**Governing decision:** `DEC-400`  
**Status:** REQUIRED PRE-DEPLOYMENT RUNBOOK  

---

## 1. Background & Context

Migration `0011_active_incident_fingerprint_unique.py` replaces the single-state partial unique index (`status = 'open'`) with a comprehensive multi-state partial unique index:

```sql
CREATE UNIQUE INDEX uq_active_incident_fingerprint
ON incidents (organization_id, service_id, fingerprint)
WHERE status IN ('open', 'acknowledged', 'mitigating', 'reopened');
```

This prevents duplicate incidents across all in-flight operational states (e.g., when an outage is acknowledged by an on-call engineer, subsequent probe failures or alerts will attach to the active episode rather than spawning duplicate tickets).

If pre-existing duplicate active incidents exist for any `(organization_id, service_id, fingerprint)` tuple, PostgreSQL will reject index creation with:
```
ERROR: could not create unique index "uq_active_incident_fingerprint"
Key (organization_id, service_id, fingerprint)=(...) is duplicated.
```

---

## 2. Read-Only Duplicate Detection Query

Before executing `alembic upgrade head`, operators must run the following read-only query against the production PostgreSQL instance:

```sql
SELECT
    organization_id,
    service_id,
    fingerprint,
    COUNT(*) AS duplicate_count,
    ARRAY_AGG(id ORDER BY created_at ASC) AS incident_ids
FROM incidents
WHERE status IN ('open', 'acknowledged', 'mitigating', 'reopened')
GROUP BY organization_id, service_id, fingerprint
HAVING COUNT(*) > 1;
```

### Expected Output for Clean Database:
```
 organization_id | service_id | fingerprint | duplicate_count | incident_ids 
-----------------+------------+-------------+-----------------+--------------
(0 rows)
```

If `(0 rows)` is returned, the database is clean and migration `0011` can be safely applied immediately.

---

## 3. Safe Remediation Procedure (NO AUTOMATIC DELETION)

> [!CAUTION]
> **Production Safety Invariant:** Production incident records, historical investigations, and audit timelines must NEVER be deleted (`DELETE FROM incidents`) or automatically modified without audit provenance.

If duplicates are detected:

1. **Investigate Episodes:**
   For each tuple returned by the preflight query, inspect the conflicting incident IDs:
   ```sql
   SELECT id, title, status, created_at, updated_at
   FROM incidents
   WHERE id IN ('<id_1>', '<id_2>', ...);
   ```

2. **Select the Primary Active Episode:**
   Collaborate with the active incident commander or on-call team to identify the primary active incident (typically the earliest incident or the one with active responder commentary/investigation runs).

3. **Reconcile Redundant Duplicates to `resolved`:**
   Transition redundant duplicate rows to `resolved` status while writing a verifiable audit event:
   ```sql
   -- Example for redundant duplicate incident '<redundant_id>'
   UPDATE incidents
   SET status = 'resolved',
       resolved_at = NOW(),
       updated_at = NOW()
   WHERE id = '<redundant_id>'
     AND status IN ('open', 'acknowledged', 'mitigating', 'reopened');

   -- Record audit event
   INSERT INTO incident_events (
       id,
       incident_id,
       event_type,
       actor,
       occurred_at,
       payload,
       created_at
   ) VALUES (
       gen_random_uuid(),
       '<redundant_id>',
       'resolved',
       'operator:migration_0011_preflight',
       NOW(),
       '{"reason": "Deduplicated active incident prior to applying migration 0011 uq_active_incident_fingerprint"}',
       NOW()
   );
   ```

4. **Re-run Preflight Check:**
   Re-execute the read-only detection query. Verify that it returns `(0 rows)`.

5. **Apply Migration:**
   ```bash
   alembic upgrade head
   ```
