# Runbook: Checkout Service HTTP 500 Spike Investigation

## 1. Symptoms and Alert Triggers
- Prometheus alert `High5xxRate` or `CheckoutErrorRateExceeded` firing.
- HTTP status 500 returning on POST `/checkout` and GET `/checkout/status`.
- User-facing error message: "Payment service unavailable, please retry later".
- Elevated error budget burn rate exceeding 2% per hour.

## 2. Triaging Steps
1. Determine whether errors correlate with a recent deployment:
   - Check GitHub deployment timestamp vs alert start timestamp.
   - Inspect release notes and commit history for `/checkout` route modifications.
2. Check external payment gateway dependencies:
   - Stripe / PayPal webhook health and third-party status dashboard.
   - Look for `GATEWAY_TIMEOUT` or `ETIMEDOUT` in Loki structured logs.
3. Inspect internal downstream dependencies:
   - Verify PostgreSQL connection latency and query execution times.
   - Verify Redis session lookup latencies.

## 3. Immediate Mitigation
1. If correlated with a recent release (< 30 minutes prior):
   - Initiate immediate rollback to previous stable commit tag.
2. If downstream gateway is degraded:
   - Enable circuit breaker fallback mode to queue payment intents asynchronously.
3. If database pool is saturated:
   - Refer to `Runbook: PostgreSQL Connection Pool Saturation` for socket drain procedures.

## 4. Verification
- Confirm HTTP 500 error rate drops below 0.1% for 15 consecutive minutes.
- Validate synthetic health probes against `/healthz` and `/readyz`.
