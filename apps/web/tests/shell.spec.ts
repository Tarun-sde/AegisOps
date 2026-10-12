import { expect, test, type Page } from "@playwright/test";

test("shell navigates to workspace and incidents feed on desktop and mobile", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Open workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Operational overview" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Connected Services (1)" }),
  ).toBeVisible();

  // Navigate to incidents feed
  await page.getByRole("link", { name: "Incidents" }).click();
  await expect(
    page.getByRole("heading", { name: "Incident Feed" }),
  ).toBeVisible();

  // Responsive check on mobile viewport
  await page.setViewportSize({ width: 375, height: 812 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);

  // Keyboard navigation & accessibility
  await page.goto("/app");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
});

test("health endpoint responds", async ({ request }) => {
  const response = await request.get("/healthz");
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ status: "ok", service: "web" });
});

const api = process.env.BROWSER_API_URL!;
const organizationId = "00000000-0000-0000-0000-000000000064";
const incidentId = "00000000-0000-0000-0000-000000000067";
const deniedIncidentId = "00000000-0000-0000-0000-000000000068";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Work Email").fill("browser-gate@example.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill(process.env.BROWSER_TEST_PASSWORD!);
  await page.locator('form button[type="submit"]').click();
  await expect(page).toHaveURL(/\/app$/);
  const me = await page.request.get(`${api}/api/v1/me`);
  expect(me.status()).toBe(200);
  expect((await me.json()).active_organization.id).toBe(organizationId);
}

test("authenticated investigation creates and displays the persisted run", async ({
  page,
}) => {
  await login(page);
  await page.goto("/app/incidents");
  await page
    .getByRole("link", { name: "Browser Gate Incident", exact: true })
    .click();
  await expect(page).toHaveURL(new RegExp(`/app/incidents/${incidentId}$`));
  const incident = await page.request.get(
    `${api}/api/v1/incidents/${incidentId}`,
  );
  expect(incident.status()).toBe(200);
  expect((await incident.json()).organization_id).toBe(organizationId);

  const creation = page.waitForResponse(
    (response) =>
      response.url() ===
        `${api}/api/v1/incidents/${incidentId}/investigations` &&
      response.request().method() === "POST",
  );
  await page.locator("#start-investigation-btn").click();
  const response = await creation;
  expect(response.status()).toBe(201);
  const run = await response.json();
  expect(run.id).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
  );
  expect(run.incident_id).toBe(incidentId);
  expect(run.organization_id).toBe(organizationId);
  expect(run.execution_mode).toBe("offline");
  const badge = page.locator("#investigation-status-badge");
  await expect(badge).toHaveAttribute("data-run-id", run.id);
  await expect(badge).toHaveText(
    /STATUS: (QUEUED|COLLECTING_CONTEXT|INVESTIGATING|VALIDATING|COMPLETE|INCONCLUSIVE)$/,
  );

  const persisted = await page.request.get(
    `${api}/api/v1/investigations/${run.id}`,
  );
  expect(persisted.status()).toBe(200);
  expect(await persisted.json()).toMatchObject({
    id: run.id,
    incident_id: incidentId,
    organization_id: organizationId,
  });
  await page.reload();
  await expect(badge).toHaveAttribute("data-run-id", run.id);
  await expect(badge).toHaveText(
    /STATUS: (QUEUED|COLLECTING_CONTEXT|INVESTIGATING|VALIDATING|COMPLETE|INCONCLUSIVE)$/,
  );
  console.log(
    `Persisted offline investigation ${run.id} for incident ${incidentId}; visible after reload`,
  );
});

test("investigation HTTP 403 displays failure without a successful run", async ({
  page,
}) => {
  await login(page);
  const endpoint = `${api}/api/v1/incidents/${deniedIncidentId}/investigations`;
  const before = await page.request.get(endpoint);
  expect(before.status()).toBe(200);
  expect(await before.json()).toEqual([]);
  await page.goto(`/app/incidents/${deniedIncidentId}`);
  await page.route(endpoint, async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Investigation denied" }),
      });
    } else {
      await route.continue();
    }
  });
  const denial = page.waitForResponse(
    (response) =>
      response.url() === endpoint && response.request().method() === "POST",
  );
  await page.locator("#start-investigation-btn").click();
  expect((await denial).status()).toBe(403);
  await expect(
    page
      .locator('section[aria-labelledby="ai-investigation-title"]')
      .getByRole("alert"),
  ).toContainText("403");
  await expect(page.locator("#investigation-status-badge")).toHaveCount(0);
  const after = await page.request.get(endpoint);
  expect(after.status()).toBe(200);
  expect(await after.json()).toEqual([]);
});

test("unauthenticated access to protected incident endpoints is rejected with 401", async ({
  request,
}) => {
  const res = await request.get(`${api}/api/v1/incidents`);
  expect(res.status()).toBe(401);
  expect((await res.json()).detail).toContain("Authentication required");
});

test("mutating requests with missing CSRF token are rejected with 403", async ({
  page,
}) => {
  await login(page);
  const res = await page.request.post(
    `${api}/api/v1/actions/proposals/00000000-0000-0000-0000-000000000000/approve`,
    {
      data: { expected_parameters_hash: "a".repeat(64) },
    },
  );
  expect(res.status()).toBe(403);
  expect((await res.json()).detail).toContain("CSRF token mismatch");
});

test("responsive layout prevents horizontal document overflow across core routes", async ({
  page,
}) => {
  const viewports = [
    { width: 375, height: 812 },
    { width: 768, height: 1024 },
    { width: 1280, height: 800 },
    { width: 1440, height: 900 },
  ];

  const routes = [
    "/",
    "/app",
    "/app/incidents",
    "/app/runbooks",
    "/app/proposals",
    "/app/simulation-lab",
    "/login",
    "/onboarding",
  ];

  for (const vp of viewports) {
    await page.setViewportSize(vp);
    for (const route of routes) {
      await page.goto(route);
      const hasOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      );
      expect(
        hasOverflow,
        `Document overflow on ${route} at ${vp.width}x${vp.height}`,
      ).toBe(false);
    }
  }
});

test("simulation lab renders catalog and environment controls", async ({
  page,
}) => {
  await page.goto("/app/simulation-lab");
  await expect(
    page.getByRole("heading", {
      name: "Incident Simulation Lab & Remediation",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /Failure Scenario Catalog/i }),
  ).toBeVisible();
});
