# Runbook: PostgreSQL Connection Pool Saturation and Recovery

## 1. Symptoms and Alert Signatures
When PostgreSQL connection pool is saturated, services report:
- `FATAL: remaining connection slots are reserved for non-replication superuser connections`
- `Knex: Timeout acquiring a connection. The pool is probably full.`
- Elevated HTTP 500 error rates on database-intensive endpoints like `/checkout` and `/orders`.
- p95 latency spikes exceeding 3000ms.

## 2. Immediate Diagnostic Procedures
1. Check active database connections via metrics:
   ```sql
   SELECT state, count(*) FROM pg_stat_activity GROUP BY state;
   ```
2. Inspect Prometheus metric `pg_stat_activity_count` with label `state="active"`.
3. Verify if `max_connections` limit has been reached on the primary instance.
4. Check for idle in transaction connections:
   ```sql
   SELECT pid, now() - xact_start AS duration, query FROM pg_stat_activity WHERE state = 'idle in transaction' ORDER BY duration DESC;
   ```

## 3. Recovery and Mitigation Steps
1. Scale up pool capacity if backend hardware allows:
   Increase `MAX_POOL_SIZE` from 20 to 50 in deployment environment variables.
2. Terminate rogue long-running blocking transactions:
   ```sql
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND now() - xact_start > interval '5 minutes';
   ```
3. Restart leaking background worker deployments to release retained pool sockets.
4. Route read-only queries to replica read pools using `DB_REPLICA_URL`.

## 4. Post-Incident Hardening
- Implement connection pooling proxy (PgBouncer or Odyssey) with transaction-level pooling.
- Enforce statement timeouts: `statement_timeout = 5000` (5 seconds).
- Enable `idle_in_transaction_session_timeout = 10000`.
