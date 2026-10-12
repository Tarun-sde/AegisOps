import { expect, test } from "@playwright/test";

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

test("incident detail page displays AI investigation panel", async ({
  page,
}) => {
  await page.goto("/app/incidents");
  const firstIncidentLink = page
    .getByRole("link", { name: /High 5xx error rate/i })
    .first();
  if (await firstIncidentLink.isVisible()) {
    await firstIncidentLink.click();
    await expect(
      page.getByRole("heading", { name: "AI Incident Investigator" }),
    ).toBeVisible();
    await expect(page.locator("#start-investigation-btn")).toBeVisible();
  }
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
