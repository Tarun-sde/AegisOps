# Runbook: Network ECONNRESET and TCP Connection Drops

## 1. Symptoms and Alert Signatures
- Node.js runtime exceptions: `Error: read ECONNRESET` or `write ECONNRESET`.
- Sudden TCP socket closure between microservices and ingress proxy.
- Intermittent HTTP 502 Bad Gateway responses from Envoy / NGINX reverse proxies.
- Spikes in client-side retry storms causing amplified connection pressure.

## 2. Root Cause Categories
1. Keep-Alive Mismatch:
   Backend HTTP server keep-alive timeout is shorter than upstream load balancer idle timeout.
2. Kernel TCP Backlog Saturation:
   `net.core.somaxconn` limit reached during sudden burst traffic.
3. Network Middlebox Termination:
   Stateful firewall or NAT gateway dropping idle connections after 350 seconds.

## 3. Resolution Procedures
1. Adjust Keep-Alive Timeout settings:
   Ensure backend keep-alive timeout (e.g. 65 seconds) exceeds load balancer timeout (60 seconds).
   ```javascript
   server.keepAliveTimeout = 65000;
   server.headersTimeout = 66000;
   ```
2. Tune Linux kernel socket parameters on host nodes:
   ```bash
   sysctl -w net.core.somaxconn=1024
   sysctl -w net.ipv4.tcp_max_syn_backlog=2048
   ```
3. Enable HTTP client keep-alive agent pooling in service configuration.
