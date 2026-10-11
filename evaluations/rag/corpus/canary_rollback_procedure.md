# Runbook: Canary Deployment Rollback and Release Recovery

## 1. Trigger Criteria for Rollback
Initiate immediate rollback when any of the following occur within 60 minutes of release:
- Error rate on canary pods exceeds baseline by more than 0.5%.
- p99 request latency degrades by more than 50% compared to previous version.
- CrashLoopBackOff or UnhandledException spikes in container logs.
- Memory leak detected via linear RSS growth slope.

## 2. Emergency Rollback Execution
1. Stop traffic routing to canary pods:
   ```bash
   kubectl set weight service/shop-api-canary --weight=0
   ```
2. Revert Kubernetes deployment to previous revision:
   ```bash
   kubectl rollout undo deployment/shop-api
   ```
3. Verify rollout completion:
   ```bash
   kubectl rollout status deployment/shop-api
   ```

## 3. Post-Rollback Diagnostics
1. Preserve crashing container logs and coredumps before pod termination:
   ```bash
   kubectl logs -l app=shop-api,version=canary --previous > /tmp/canary_crash.log
   ```
2. Notify release engineering team in `#incident-war-room`.
3. Freeze automated CI/CD pipeline triggers until root cause is identified.
