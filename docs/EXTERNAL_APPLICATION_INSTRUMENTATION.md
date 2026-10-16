# AegisOps — External Application Observability Instrumentation Guide

This guide describes how to connect external services (such as Express.js applications like **IRONLOG** or Python APIs) to AegisOps for continuous monitoring, Prometheus metrics collection, Loki log aggregation, and Tempo distributed tracing.

---

## 1. HTTP Healthcheck Monitoring (Zero-Dependency)

AegisOps scheduled workers continuously probe registered endpoints at configurable intervals (15s to 300s) with SSRF-safe outbound requests.

### Node.js / Express Example (IRONLOG)

```javascript
// Express healthcheck endpoint
app.get('/api/health', (req, res) => {
  res.status(200).json({
    status: 'ok',
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
  });
});
```

### Registration in AegisOps
1. In AegisOps, navigate to **Applications** -> **Connect an application** or open an existing application's **Settings** tab.
2. Enter the full public healthcheck URL (e.g. `https://ironlog-backend-jrqs.onrender.com/api/health`).
3. Click **Test Connection Now** to perform an immediate SSRF-safe probe.
4. Enable **Scheduled Continuous Probing** and select your desired interval.
5. AegisOps automatically monitors reachability, detects outages after consecutive failures (cold-start resistant), and auto-resolves outage incidents upon recovery.

---

## 2. Prometheus Metrics via `prom-client`

To collect request rates, p95 latencies, and error rates in AegisOps Analytics:

### Installation
```bash
npm install prom-client
```

### Express Middleware Setup
```javascript
const client = require('prom-client');

// Initialize default Node.js and runtime metrics
const collectDefaultMetrics = client.collectDefaultMetrics;
collectDefaultMetrics({ prefix: 'ironlog_' });

// Define HTTP request duration histogram
const httpRequestDuration = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [0.01, 0.05, 0.1, 0.3, 0.5, 1, 2.5, 5],
});

// Middleware to measure request duration
app.use((req, res, next) => {
  const end = httpRequestDuration.startTimer();
  res.on('finish', () => {
    const route = req.route ? req.route.path : req.path;
    end({ method: req.method, route, status_code: res.statusCode });
  });
  next();
});

// Expose Prometheus metrics endpoint
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', client.register.contentType);
  res.end(await client.register.metrics());
});
```

### Prometheus Target Configuration in AegisOps
Add the target to `infra/prometheus/targets/targets.yml`:
```yaml
- targets: ["your-application-host:port"]
  labels:
    job: ironlog
    service: IRONLOG
    environment: production
```
Prometheus automatically discovers the target via `file_sd_configs` within 10 seconds without needing container restarts.

---

## 3. Distributed Tracing & Logs via OpenTelemetry (OTLP)

AegisOps includes a hardened OpenTelemetry Collector listening on `127.0.0.1:4318` (HTTP) and `127.0.0.1:4317` (gRPC), routing traces directly to Grafana Tempo and logs to Grafana Loki.

### Installation
```bash
npm install @opentelemetry/sdk-node \
  @opentelemetry/auto-instrumentations-node \
  @opentelemetry/exporter-trace-otlp-http
```

### Node.js Tracing Bootstrap (`tracing.js`)
```javascript
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-http');

const traceExporter = new OTLPTraceExporter({
  url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://127.0.0.1:4318/v1/traces',
});

const sdk = new NodeSDK({
  traceExporter,
  instrumentations: [getNodeAutoInstrumentations()],
  serviceName: 'IRONLOG',
});

sdk.start();

process.on('SIGTERM', () => {
  sdk.shutdown()
    .then(() => console.log('Tracing terminated'))
    .finally(() => process.exit(0));
});
```

Run your application with:
```bash
node -r ./tracing.js server.js
```

---

## 4. Security Invariants

1. **SSRF Guard**: AegisOps strictly blocks all loopback (`127.0.0.0/8`), RFC 1918 private subnets, link-local metadata (`169.254.169.254`), and cloud internal domains. External applications must be hosted on reachable public domains or explicitly authorized demo gateways.
2. **Collector Exposure**: The OTLP collector is bound to `127.0.0.1:4318` by default to prevent unauthorized public telemetry ingestion. In production clusters, protect telemetry ingress with mTLS or API token gateways.
3. **Tenant Scoping**: All incidents, traces, and metrics are strictly isolated by organization ID and service ID.
