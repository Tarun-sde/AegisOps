import crypto from "node:crypto";
import express, {
  type Request,
  type Response,
  type NextFunction,
} from "express";
import {
  Counter,
  Histogram,
  Registry,
  collectDefaultMetrics,
} from "prom-client";

// Prometheus metrics registry
export const registry = new Registry();
collectDefaultMetrics({ register: registry });

export const httpRequestsTotal = new Counter({
  name: "http_requests_total",
  help: "Total number of HTTP requests processed",
  labelNames: ["method", "route", "status_code"],
  registers: [registry],
});

export const httpRequestDurationSeconds = new Histogram({
  name: "http_request_duration_seconds",
  help: "Duration of HTTP requests in seconds",
  labelNames: ["method", "route", "status_code"],
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
  registers: [registry],
});

// Deterministic product catalog
export const PRODUCTS = [
  {
    id: "prod-1",
    name: "Enterprise NVMe SSD 1TB",
    price_cents: 8999,
    stock: 42,
  },
  { id: "prod-2", name: "ECC DDR5 RAM 32GB", price_cents: 11999, stock: 15 },
  {
    id: "prod-3",
    name: "Low-Profile Mechanical Keyboard",
    price_cents: 7499,
    stock: 28,
  },
];

// Fault state isolated to demo/test
let faultCheckout500Active = process.env.FAULT_CHECKOUT_500 === "1";
const DEMO_FAULT_SECRET =
  process.env.AEGISOPS_DEMO_FAULT_SECRET || "aegisops-demo-fault-secret";

export function setCheckoutFault(active: boolean): void {
  faultCheckout500Active = active;
}

export function isCheckoutFaultActive(): boolean {
  return faultCheckout500Active || process.env.FAULT_CHECKOUT_500 === "1";
}

// Redaction of sensitive fields before logging/export
const SENSITIVE_KEYS = new Set([
  "authorization",
  "cookie",
  "set-cookie",
  "password",
  "secret",
  "token",
  "api_key",
  "apikey",
  "credit_card",
  "card_number",
]);

export function redactSensitive(data: unknown): unknown {
  if (typeof data === "string") {
    return data.replace(/(bearer\s+)[a-zA-Z0-9_\-\.]+/gi, "$1[REDACTED]");
  }
  if (Array.isArray(data)) {
    return data.map(redactSensitive);
  }
  if (data !== null && typeof data === "object") {
    const redacted: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(data)) {
      if (SENSITIVE_KEYS.has(key.toLowerCase())) {
        redacted[key] = "[REDACTED]";
      } else {
        redacted[key] = redactSensitive(value);
      }
    }
    return redacted;
  }
  return data;
}

export interface StructuredLog {
  timestamp: string;
  level: "info" | "warn" | "error";
  service: string;
  environment: string;
  event: string;
  message: string;
  route: string;
  method: string;
  status_code: number;
  request_id: string;
  duration_ms: number;
  error_category?: string;
  error_code?: string;
  exception_class?: string;
  version: string;
  trace_id?: string;
  span_id?: string;
}

async function exportOtlpLog(logObj: StructuredLog): Promise<void> {
  const endpoint = process.env.OTEL_EXPORTER_OTLP_LOGS_ENDPOINT;
  if (!endpoint) return;
  try {
    await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resourceLogs: [
          {
            resource: {
              attributes: [
                { key: "service.name", value: { stringValue: logObj.service } },
                {
                  key: "service.version",
                  value: { stringValue: logObj.version },
                },
                {
                  key: "deployment.environment",
                  value: { stringValue: logObj.environment },
                },
              ],
            },
            scopeLogs: [
              {
                scope: { name: "shop-api.logger" },
                logRecords: [
                  {
                    timeUnixNano: String(BigInt(Date.now()) * 1000000n),
                    severityText: logObj.level.toUpperCase(),
                    body: { stringValue: logObj.message },
                    ...(logObj.trace_id ? { traceId: logObj.trace_id } : {}),
                    ...(logObj.span_id ? { spanId: logObj.span_id } : {}),
                    attributes: [
                      {
                        key: "http.route",
                        value: { stringValue: logObj.route },
                      },
                      {
                        key: "http.method",
                        value: { stringValue: logObj.method },
                      },
                      {
                        key: "http.status_code",
                        value: { intValue: logObj.status_code },
                      },
                      {
                        key: "request.id",
                        value: { stringValue: logObj.request_id },
                      },
                      {
                        key: "duration_ms",
                        value: { doubleValue: logObj.duration_ms },
                      },
                      ...(logObj.error_category
                        ? [
                            {
                              key: "error.category",
                              value: { stringValue: logObj.error_category },
                            },
                          ]
                        : []),
                      ...(logObj.error_code
                        ? [
                            {
                              key: "error.code",
                              value: { stringValue: logObj.error_code },
                            },
                          ]
                        : []),
                      ...(logObj.exception_class
                        ? [
                            {
                              key: "exception.type",
                              value: { stringValue: logObj.exception_class },
                            },
                          ]
                        : []),
                    ],
                  },
                ],
              },
            ],
          },
        ],
      }),
      signal: AbortSignal.timeout(1500),
    });
  } catch {
    // ponytail: fire-and-forget log export; never fail user requests on collector hiccup
  }
}

async function exportOtlpTrace(
  traceId: string,
  spanId: string,
  parentSpanId: string | undefined,
  name: string,
  startNano: bigint,
  endNano: bigint,
  statusCode: number,
  attributes: Array<{ key: string; value: Record<string, unknown> }>,
): Promise<void> {
  const endpoint = process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT;
  if (!endpoint) return;
  try {
    await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resourceSpans: [
          {
            resource: {
              attributes: [
                { key: "service.name", value: { stringValue: "shop-api" } },
                { key: "service.version", value: { stringValue: "0.1.0" } },
                {
                  key: "deployment.environment",
                  value: { stringValue: process.env.NODE_ENV || "development" },
                },
              ],
            },
            scopeSpans: [
              {
                scope: { name: "shop-api.tracer" },
                spans: [
                  {
                    traceId,
                    spanId,
                    ...(parentSpanId ? { parentSpanId } : {}),
                    name,
                    kind: 2,
                    startTimeUnixNano: String(startNano),
                    endTimeUnixNano: String(endNano),
                    status: { code: statusCode >= 500 ? 2 : 1 },
                    attributes,
                  },
                ],
              },
            ],
          },
        ],
      }),
      signal: AbortSignal.timeout(1500),
    });
  } catch {
    // ponytail: fire-and-forget trace export
  }
}

export const app = express();
app.disable("x-powered-by");
app.use(express.json({ limit: "64kb" }));

// Route normalizer to prevent high-cardinality label explosion
function normalizeRoute(path: string): string {
  if (
    path === "/" ||
    path === "/healthz" ||
    path === "/products" ||
    path === "/checkout" ||
    path === "/metrics"
  ) {
    return path;
  }
  if (path.startsWith("/fault")) {
    return "/fault";
  }
  return "other";
}

// Middleware: Request correlation, duration, RED metrics, and structured logging
app.use((request: Request, response: Response, next: NextFunction) => {
  const start = process.hrtime.bigint();
  const requestId =
    (request.headers["x-request-id"] as string) || crypto.randomUUID();
  response.setHeader("x-request-id", requestId);

  // W3C TraceContext extraction or generation
  const traceParent = request.headers["traceparent"] as string | undefined;
  let traceId: string;
  let parentSpanId: string | undefined;
  if (
    traceParent &&
    /^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$/i.test(traceParent)
  ) {
    const parts = traceParent.split("-");
    traceId = parts[1].toLowerCase();
    parentSpanId = parts[2].toLowerCase();
  } else {
    traceId = crypto.randomBytes(16).toString("hex");
  }
  const spanId = crypto.randomBytes(8).toString("hex");
  response.setHeader("x-trace-id", traceId);
  response.setHeader("x-span-id", spanId);

  response.on("finish", () => {
    const end = process.hrtime.bigint();
    const durationSeconds = Number(end - start) / 1e9;
    const durationMs = Math.round(durationSeconds * 100000) / 100;
    const route = normalizeRoute(request.path);
    const statusCode = String(response.statusCode);

    httpRequestsTotal.inc({
      method: request.method,
      route,
      status_code: statusCode,
    });
    httpRequestDurationSeconds.observe(
      { method: request.method, route, status_code: statusCode },
      durationSeconds,
    );

    const isError = response.statusCode >= 500;
    const isWarn = response.statusCode >= 400 && !isError;
    const level: "info" | "warn" | "error" = isError
      ? "error"
      : isWarn
        ? "warn"
        : "info";

    const logEntry: StructuredLog = {
      timestamp: new Date().toISOString(),
      level,
      service: "shop-api",
      environment: process.env.NODE_ENV || "development",
      event: isError ? "http_request_error" : "http_request_completed",
      message: isError
        ? `HTTP 500: checkout payment gateway failure on ${request.method} ${route}`
        : `${request.method} ${route} ${response.statusCode}`,
      route,
      method: request.method,
      status_code: response.statusCode,
      request_id: requestId,
      duration_ms: durationMs,
      error_category:
        response.locals.errorCategory ||
        (isError ? "GATEWAY_TIMEOUT" : undefined),
      error_code: response.locals.errorCode,
      exception_class: response.locals.exceptionClass,
      version: "0.1.0",
      trace_id: traceId,
      span_id: spanId,
    };

    const redacted = redactSensitive(logEntry) as StructuredLog;
    if (isError) {
      console.error(JSON.stringify(redacted));
    } else {
      console.log(JSON.stringify(redacted));
    }
    void exportOtlpLog(redacted);
    void exportOtlpTrace(
      traceId,
      spanId,
      parentSpanId,
      `${request.method} ${route}`,
      start,
      end,
      response.statusCode,
      [
        { key: "http.method", value: { stringValue: request.method } },
        { key: "http.route", value: { stringValue: route } },
        { key: "http.status_code", value: { intValue: response.statusCode } },
        { key: "request.id", value: { stringValue: requestId } },
      ],
    );
  });

  next();
});

// A1: Health probe
app.get("/healthz", (_request: Request, response: Response) => {
  response.json({
    status: "ok",
    service: "shop-api",
    version: "0.1.0",
    fault_active: isCheckoutFaultActive(),
  });
});

// A1: Product catalog
app.get("/products", (_request: Request, response: Response) => {
  response.json({ products: PRODUCTS });
});

// A1 & A4: Checkout endpoint with deterministic S01_CHECKOUT_500 fault mode
app.post("/checkout", (request: Request, response: Response) => {
  // Check fault mode
  if (isCheckoutFaultActive()) {
    response.locals.errorCategory = "APPLICATION_EXCEPTION";
    response.locals.errorCode = "CHECKOUT_GATEWAY_TIMEOUT";
    response.locals.exceptionClass = "PaymentGatewayTimeoutException";
    response.status(500).json({
      error: "Payment processing gateway connection timed out",
      code: "CHECKOUT_GATEWAY_TIMEOUT",
      scenario: "S01_CHECKOUT_500",
      retryable: false,
    });
    return;
  }

  const { items } = request.body || {};
  if (!Array.isArray(items) || items.length === 0) {
    response.status(400).json({
      error:
        "Invalid checkout request: 'items' array required and cannot be empty",
      code: "VALIDATION_ERROR",
    });
    return;
  }

  let totalCents = 0;
  for (const item of items) {
    const product = PRODUCTS.find((p) => p.id === item.id);
    const quantity = Number(item.quantity) || 1;
    if (product) {
      totalCents += product.price_cents * quantity;
    }
  }

  response.status(201).json({
    status: "success",
    order_id: `ord-${crypto.randomUUID().slice(0, 8)}`,
    total_cents: totalCents,
    currency: "USD",
  });
});

// A1: Prometheus metrics scrape endpoint
app.get("/metrics", async (_request: Request, response: Response) => {
  response.setHeader("Content-Type", registry.contentType);
  response.send(await registry.metrics());
});

// A4: Controlled demo-only fault management endpoints
app.post("/fault/inject", (request: Request, response: Response) => {
  if (process.env.NODE_ENV === "production") {
    response
      .status(403)
      .json({ error: "Fault injection forbidden in production" });
    return;
  }
  const secret = request.headers["x-demo-fault-secret"] || request.body?.secret;
  if (secret !== DEMO_FAULT_SECRET) {
    response.status(401).json({ error: "Unauthorized fault control" });
    return;
  }
  setCheckoutFault(true);
  response.json({ fault_active: true, scenario: "S01_CHECKOUT_500" });
});

app.post("/fault/reset", (request: Request, response: Response) => {
  if (process.env.NODE_ENV === "production") {
    response
      .status(403)
      .json({ error: "Fault injection forbidden in production" });
    return;
  }
  const secret = request.headers["x-demo-fault-secret"] || request.body?.secret;
  if (secret !== DEMO_FAULT_SECRET) {
    response.status(401).json({ error: "Unauthorized fault control" });
    return;
  }
  setCheckoutFault(false);
  response.json({ fault_active: false });
});

app.get("/fault/status", (_request: Request, response: Response) => {
  response.json({
    fault_active: isCheckoutFaultActive(),
    scenario: isCheckoutFaultActive() ? "S01_CHECKOUT_500" : null,
  });
});
