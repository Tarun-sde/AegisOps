import assert from "node:assert/strict";
import { test } from "node:test";
import { once } from "node:events";
import { app } from "../dist/app.js";

test("health works and no fault controls exist", async () => {
  const server = app.listen(0, "127.0.0.1");
  await once(server, "listening");
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const response = await fetch(`${base}/healthz`);
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), {
      status: "ok",
      service: "shop-api",
      phase: 0,
    });
    assert.equal((await fetch(`${base}/checkout`)).status, 404);
  } finally {
    await new Promise((resolve, reject) =>
      server.close((error) => (error ? reject(error) : resolve())),
    );
  }
});
