import { test, expect } from "@playwright/test";
test("reference hero selection and four-phase motion survive route transitions", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".preloader")).not.toBeVisible({ timeout: 10000 });
  await page.waitForTimeout(1600);
  const hero = page.locator(".interactive-topology");
  const box = await hero.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box!.x + box!.width * 0.15, box!.y + box!.height * 0.1);
  await page.mouse.down();
  await page.mouse.move(box!.x + box!.width * 0.9, box!.y + box!.height * 0.9, {
    steps: 12,
  });
  await page.mouse.up();
  await expect(page.locator(".issue-marker.is-active")).toHaveCount(3);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page
    .locator(".phase-nav")
    .getByRole("button", { name: /Advise/ })
    .click();
  await expect(
    page.locator(".phase-nav").getByRole("button", { name: /Advise/ }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .locator(".desktop-nav")
    .getByRole("link", { name: "Workspace" })
    .click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.locator(".header")).toHaveCount(0);
  await expect(page.locator(".preloader")).toHaveCount(0);
  await expect(page.locator(".pin-spacer")).toHaveCount(0);
  await expect(page.locator("html")).not.toHaveClass(/lenis/);
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect(page.locator(".workspace")).toHaveClass(/ws-collapsed/);
  const rail = await page.locator(".ws-sidebar").boundingBox();
  expect(rail!.width).toBeLessThan(100);
});
