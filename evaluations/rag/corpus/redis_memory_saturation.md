# Runbook: Redis Memory Saturation and Eviction Storms

## 1. Symptoms and Alert Signatures
When Redis cache saturates its allocated RAM:
- Alerts firing: `RedisMemoryHigh` (used_memory > 90% of maxmemory).
- Error messages in application logs: `OOM command not allowed when used memory > 'maxmemory'`.
- Increased cache miss rate leading to backend database load amplification.
- Latency spikes on session verification and cart caching.

## 2. Diagnostic Procedures
1. Connect via `redis-cli` and inspect memory statistics:
   ```bash
   redis-cli info memory
   ```
2. Check eviction count and current eviction policy:
   ```bash
   redis-cli info stats | grep evicted_keys
   redis-cli config get maxmemory-policy
   ```
3. Run memory analysis for oversized keys:
   ```bash
   redis-cli --bigkeys
   ```

## 3. Remediation Actions
1. If maxmemory is configured with `noeviction`, switch to `volatile-lru` or `allkeys-lru`:
   ```bash
   redis-cli config set maxmemory-policy volatile-lru
   ```
2. Trigger non-blocking eviction of expired keys:
   ```bash
   redis-cli memory purge
   ```
3. Clear high-volume ephemeral session keys if corruption is detected.
4. Scale up the Redis cluster node memory tier via cloud infrastructure console.

## 4. Prevention
- Ensure all cached entries set explicit TTLs (maximum 24 hours for temporary tokens).
- Avoid storing large serialized payloads (> 100KB) in single keys.
