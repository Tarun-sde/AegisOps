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
