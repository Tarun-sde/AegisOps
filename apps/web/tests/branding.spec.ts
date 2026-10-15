import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test("public identity and sample interactions never call account APIs", async ({
  page,
}) => {
  const requests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/")) requests.push(request.url());
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page).toHaveTitle(/AegisOps/);
  await expect(page.locator('link[rel="icon"]').first()).toHaveAttribute(
    "href",
    /icon.svg/,
  );
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute(
    "content",
    /aegisops-social.png/,
  );
  await expect(page.locator("body")).not.toContainText(
    /Heron|floor plan|pavilion|residential tower|firm standards/i,
  );
  await expect(
    page.getByLabel(/Illustrative Shop API request topology/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Inspect scenario" }).click();
  await expect(page.getByLabel("Sample incident inspection")).toContainText(
    "Pool saturation is unconfirmed",
  );
  await expect(page.locator(".hero .topology-anomaly")).toHaveAttribute(
    "stroke",
    "#b43e35",
  );
  await page
    .getByRole("link", { name: "Explore the platform", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/platform$/);
  await expect(page.locator(".header")).toHaveCount(1);
  await expect(page.locator(".approval-detail").first()).toContainText(
    "service_name: shop-api",
  );
  await expect(page.locator(".approval-detail").first()).toContainText(
    "grace_period_seconds: 10",
  );
  await page
    .getByRole("button", { name: "Approve sample", exact: false })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Execution has not occurred",
  );
  await page.getByRole("button", { name: "Reset preview" }).click();
  await page.getByRole("button", { name: "Reject sample" }).click();
  await expect(page.getByRole("status")).toContainText("No action taken");
  await page
    .getByRole("button", { name: "Can the AI execute production changes?" })
    .click();
  await expect(page.locator("#faq-a-2")).toContainText(
    "Production remediation is disabled",
  );
  expect(requests).toEqual([]);
});

test("four operational scenes scrub forward and backward on the same scroll clock", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".preloader")).not.toBeVisible({ timeout: 10000 });
  for (const index of [0, 1, 2, 3, 1, 0]) {
    await page.locator(".phase-nav button").nth(index).click({ force: true });
    await expect(page.locator(".phase-nav button").nth(index)).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    // The source keeps one system drawing and transforms its evidence/proposal layers.
    await expect(
      page.locator(".workflow-drawing .incident-plan"),
    ).toBeVisible();
    await expect(page.locator(".workflow-copy").nth(index)).toHaveCSS(
      "opacity",
      "1",
    );
    await expect(page.locator(".workflow-copy").nth((index + 1) % 4)).toHaveCSS(
      "opacity",
      "0",
    );
    if (index === 1)
      await expect(page.locator(".workflow-alert")).toHaveCSS("opacity", "1");
    if (index === 2) {
      await expect(
        page.locator(".workflow-drawing .editable-door"),
      ).toHaveAttribute("d", "M423 191h54v54h-54");
      await expect(page.locator(".workflow-copy").nth(index)).toContainText(
        "Approval does not execute",
      );
    }
    if (index === 3)
      await expect(page.locator(".model-standard-node").last()).toHaveCSS(
        "opacity",
        "1",
      );
    if (index === 0) {
      await expect(
        page.locator(".workflow-drawing .editable-door"),
      ).toHaveAttribute("d", "M423 191h-54v54h54");
      await expect(page.locator(".workflow-alert")).toHaveCSS("opacity", "1");
      await expect(page.locator(".workflow-alert")).toHaveCSS(
        "clip-path",
        "inset(0px 100% 0px 0px)",
      );
    }
  }
});

test("responsive keyboard inspection and reduced-motion workflow keep the full meaning", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.getByRole("button", { name: "Inspect scenario" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Sample incident inspection")).toBeVisible();
  await page.locator(".phase-nav button").nth(2).click();
  await expect(
    page.locator(".workflow-drawing .editable-door"),
  ).toHaveAttribute("d", "M423 191h54v54h-54");
  await expect(page.locator(".workflow-copy").nth(2)).toContainText(
    "Approval does not execute",
  );
  await expect(page.locator(".preloader")).not.toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto("/");
  await page.getByRole("button", { name: "Inspect scenario" }).click();
  const drawing = await page.locator(".hero-drawing").boundingBox();
  const details = await page
    .getByLabel("Sample incident inspection")
    .boundingBox();
  expect(drawing!.height).toBeGreaterThan(350);
  expect(details!.y).toBeGreaterThanOrEqual(drawing!.y + drawing!.height);
});

test("shipping marketing code contains only operational artwork and no account API adapter", () => {
  const dir = path.resolve("app/components/marketing");
  for (const file of fs
    .readdirSync(dir)
    .filter((file) => /\.tsx?$/.test(file))) {
    const source = fs.readFileSync(path.join(dir, file), "utf8");
    expect(source, file).not.toMatch(
      /architectural floor plan|door swing|ceiling height|firm standards|HERON AI|RESIDENTIAL TOWER/i,
    );
    expect(source, file).not.toMatch(
      /from ["'][^"']*lib\/api|fetch\(|\/api\/v1\//,
    );
  }
});

test("showcase evidence retains authored node positions after animated entry", async ({
  page,
}) => {
  await page.goto("/platform");
  await expect(page.locator(".preloader")).not.toBeVisible({ timeout: 10000 });
  await page.locator(".feature-tabs button").nth(2).click({ force: true });
  await expect(page.locator(".feature-tabs button").nth(2)).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  const items = page.locator("#feature-2 .history-event");
  await expect(items.last()).toHaveCSS("opacity", "1");
  const first = await items.first().boundingBox();
  const last = await items.last().boundingBox();
  expect(last!.y - first!.y).toBeGreaterThan(first!.height * 1.8);
});
