import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const OUT_DIR = "artifacts/phase8-3/baseline";
fs.mkdirSync(OUT_DIR, { recursive: true });

async function capture() {
  const browser = await chromium.launch();
  try {
    // 1. Desktop Context
    const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await desktop.newPage();

    // Homepage
    await page.goto("http://127.0.0.1:3000/", { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_homepage.png") });

    // Hero before interaction
    const heroEl = page.locator(".hero");
    if (await heroEl.count() > 0) {
      await heroEl.screenshot({ path: path.join(OUT_DIR, "hero_before.png") });
    }

    // Hero after interaction
    const inspectBtn = page.getByRole("button", { name: /Inspect scenario/i });
    if (await inspectBtn.count() > 0) {
      await inspectBtn.click();
      await page.waitForTimeout(500);
      await heroEl.screenshot({ path: path.join(OUT_DIR, "hero_after.png") });
    }

    // Platform page
    await page.goto("http://127.0.0.1:3000/platform", { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_platform.png") });

    // Login page
    await page.goto("http://127.0.0.1:3000/login", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_login.png") });

    // Perform Login
    await page.getByLabel("Work Email").fill("demo@aegisops.local");
    await page.getByLabel("Password", { exact: true }).fill("demo-password-123");
    await page.locator('form button[type="submit"]').click();
    await page.waitForURL("**/app**", { timeout: 10000 });
    await page.waitForTimeout(1500);

    // Dashboard
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_dashboard.png") });

    // Services page
    const sResp = await page.goto("http://127.0.0.1:3000/app/services", { waitUntil: "networkidle" });
    console.log("/app/services status:", sResp?.status());
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_services.png") });

    // Incidents page
    await page.goto("http://127.0.0.1:3000/app/incidents", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_incidents.png") });

    // Runbooks page
    await page.goto("http://127.0.0.1:3000/app/runbooks", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_runbooks.png") });

    // Proposals page
    await page.goto("http://127.0.0.1:3000/app/proposals", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_proposals.png") });

    // Simulation Lab page
    await page.goto("http://127.0.0.1:3000/app/simulation-lab", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_simulation_lab.png") });

    await desktop.close();

    // 2. Mobile Context (375x812)
    const mobile = await browser.newContext({ viewport: { width: 375, height: 812 } });
    const mPage = await mobile.newPage();

    // Mobile Homepage
    await mPage.goto("http://127.0.0.1:3000/", { waitUntil: "networkidle" });
    await mPage.waitForTimeout(1000);
    await mPage.screenshot({ path: path.join(OUT_DIR, "mobile_homepage.png") });

    // Mobile Menu
    const menuBtn = mPage.locator(".menu-toggle, button[aria-label*='menu' i], [aria-label*='navigation' i]").first();
    if (await menuBtn.count() > 0) {
      await menuBtn.click();
      await mPage.waitForTimeout(500);
      await mPage.screenshot({ path: path.join(OUT_DIR, "mobile_menu.png") });
    }

    // Mobile Login & Dashboard
    await mPage.goto("http://127.0.0.1:3000/login", { waitUntil: "networkidle" });
    await mPage.getByLabel("Work Email").fill("demo@aegisops.local");
    await mPage.getByLabel("Password", { exact: true }).fill("demo-password-123");
    await mPage.locator('form button[type="submit"]').click();
    await mPage.waitForURL("**/app**", { timeout: 10000 });
    await mPage.waitForTimeout(1500);
    await mPage.screenshot({ path: path.join(OUT_DIR, "mobile_dashboard.png") });

    await mobile.close();
    console.log("Baseline captures completed successfully!");
  } finally {
    await browser.close();
  }
}

capture().catch((err) => {
  console.error("Capture failed:", err);
  process.exit(1);
});
