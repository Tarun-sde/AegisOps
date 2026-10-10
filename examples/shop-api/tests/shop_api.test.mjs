import assert from "node:assert/strict";
import { test } from "node:test";
import { once } from "node:events";
import { app, setCheckoutFault, redactSensitive } from "../dist/app.js";

test("shop-api comprehensive test suite", async () => {
  const server = app.listen(0, "127.0.0.1");
  await once(server, "listening");
  const base = `http://127.0.0.1:${server.address().port}`;

  try {
    // 1. Health endpoint
    const healthRes = await fetch(`${base}/healthz`);
    assert.equal(healthRes.status, 200);
    const healthJson = await healthRes.json();
    assert.equal(healthJson.status, "ok");
    assert.equal(healthJson.service, "shop-api");
    assert.equal(healthJson.version, "0.1.0");

    // 2. Products endpoint
    const productsRes = await fetch(`${base}/products`);
    assert.equal(productsRes.status, 200);
    const productsJson = await productsRes.json();
    assert.ok(Array.isArray(productsJson.products));
    assert.ok(productsJson.products.length >= 3);

    // 3. Normal checkout
    const checkoutRes = await fetch(`${base}/checkout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: [{ id: "prod-1", quantity: 2 }],
      }),
    });
    assert.equal(checkoutRes.status, 201);
    const checkoutJson = await checkoutRes.json();
    assert.equal(checkoutJson.status, "success");
    assert.equal(checkoutJson.total_cents, 8999 * 2);

    // 4. Checkout validation error
    const badCheckoutRes = await fetch(`${base}/checkout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: [] }),
    });
    assert.equal(badCheckoutRes.status, 400);

    // 5. Fault injection via endpoint
    const injectRes = await fetch(`${base}/fault/inject`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-demo-fault-secret": "aegisops-demo-fault-secret",
      },
    });
    assert.equal(injectRes.status, 200);
    const injectJson = await injectRes.json();
    assert.equal(injectJson.fault_active, true);
    assert.equal(injectJson.scenario, "S01_CHECKOUT_500");

    // 6. Checkout under fault mode
    const faultCheckoutRes = await fetch(`${base}/checkout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: [{ id: "prod-1", quantity: 1 }] }),
    });
    assert.equal(faultCheckoutRes.status, 500);
    const faultCheckoutJson = await faultCheckoutRes.json();
    assert.equal(faultCheckoutJson.code, "CHECKOUT_GATEWAY_TIMEOUT");
    assert.equal(faultCheckoutJson.scenario, "S01_CHECKOUT_500");

    // 7. Reset fault mode
    const resetRes = await fetch(`${base}/fault/reset`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-demo-fault-secret": "aegisops-demo-fault-secret",
      },
    });
    assert.equal(resetRes.status, 200);
    const resetJson = await resetRes.json();
    assert.equal(resetJson.fault_active, false);

    // 8. Normal checkout succeeds again
    const recoveredCheckout = await fetch(`${base}/checkout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: [{ id: "prod-2", quantity: 1 }] }),
    });
    assert.equal(recoveredCheckout.status, 201);

    // 9. Metrics endpoint
    const metricsRes = await fetch(`${base}/metrics`);
    assert.equal(metricsRes.status, 200);
    const metricsText = await metricsRes.text();
    assert.ok(metricsText.includes("http_requests_total"));
    assert.ok(metricsText.includes('route="/checkout"'));
    assert.ok(metricsText.includes('status_code="500"'));
    assert.ok(metricsText.includes('status_code="201"'));
    assert.ok(metricsText.includes("http_request_duration_seconds"));

    // 10. Redaction helper
    const sensitiveObj = {
      user: "alice",
      token: "secret-token-123",
      authorization: "Bearer super-secret-jwt",
      headers: {
        cookie: "session=xyz123",
        "api-key": "secret-key",
      },
    };
    const redacted = redactSensitive(sensitiveObj);
    assert.equal(redacted.token, "[REDACTED]");
    assert.equal(redacted.authorization, "[REDACTED]");
    assert.equal(redacted.headers.cookie, "[REDACTED]");
    assert.equal(redacted.user, "alice");
  } finally {
    setCheckoutFault(false);
    await new Promise((resolve, reject) =>
      server.close((error) => (error ? reject(error) : resolve())),
    );
  }
});
