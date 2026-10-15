import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const OUT_DIR = path.join(ROOT, "artifacts", "phase8-3", "after");

if (!fs.existsSync(OUT_DIR)) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
}

async function run() {
  const browser = await chromium.launch({
    headless: true,
  });

  try {
    // 1. Desktop 1440x900
    const context1440 = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });
    const page = await context1440.newPage();

    console.log("Navigating to http://127.0.0.1:3000 (1440x900)...");
    await page.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
    // Wait for preloader entrance animation to finish (approx 3.2s)
    await page.waitForTimeout(3800);

    // Desktop homepage
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_homepage_1440x900.png") });

    // Public navigation
    const nav = page.locator(".site-nav");
    if (await nav.count() > 0) {
      await nav.first().screenshot({ path: path.join(OUT_DIR, "public_navigation.png") });
    }

    // Hero before interaction
    const heroEl = page.locator(".hero");
    if (await heroEl.count() > 0) {
      await heroEl.first().screenshot({ path: path.join(OUT_DIR, "hero_before.png") });

      // Trigger node interaction on Inspect scenario button
      const inspectBtn = page.locator(".scenario-toggle-btn");
      if (await inspectBtn.count() > 0) {
        console.log("Clicking Inspect scenario toggle button...");
        await inspectBtn.click();
        await page.waitForTimeout(800);
      }
      await heroEl.first().screenshot({ path: path.join(OUT_DIR, "hero_after.png") });
    }

    // Platform page
    console.log("Navigating to /platform...");
    await page.goto("http://127.0.0.1:3000/platform", { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_platform.png") });

    // Login
    console.log("Authenticating at /login...");
    await page.goto("http://127.0.0.1:3000/login", { waitUntil: "networkidle" });
    await page.getByLabel("Work Email").fill("demo@aegisops.local");
    await page.getByLabel("Password", { exact: true }).fill("demo-password-123");
    await page.locator('form button[type="submit"]').click();
    await page.waitForURL("**/app**", { timeout: 10000 });
    await page.waitForTimeout(1500);

    // Dashboard 1440x900
    console.log("Capturing Dashboard 1440x900...");
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_dashboard_1440x900.png") });

    // Services Catalog
    console.log("Navigating to /app/services...");
    const sResp = await page.goto("http://127.0.0.1:3000/app/services", { waitUntil: "networkidle" });
    console.log("Services status:", sResp?.status());
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_services.png") });

    // Incidents feed
    console.log("Navigating to /app/incidents...");
    await page.goto("http://127.0.0.1:3000/app/incidents", { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_incidents.png") });

    // Runbooks
    console.log("Navigating to /app/runbooks...");
    await page.goto("http://127.0.0.1:3000/app/runbooks", { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_runbooks.png") });

    // Proposals
    console.log("Navigating to /app/proposals...");
    await page.goto("http://127.0.0.1:3000/app/proposals", { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_proposals.png") });

    // Simulation Lab
    console.log("Navigating to /app/simulation-lab...");
    await page.goto("http://127.0.0.1:3000/app/simulation-lab", { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(OUT_DIR, "desktop_simulation_lab.png") });

    await context1440.close();

    // 2. Desktop 1920x1080
    console.log("Capturing 1920x1080 views...");
    const context1920 = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
      deviceScaleFactor: 1,
    });
    const page1920 = await context1920.newPage();
    await page1920.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
    await page1920.waitForTimeout(3800);
    await page1920.screenshot({ path: path.join(OUT_DIR, "desktop_homepage_1920x1080.png") });

    // Login for 1920 dashboard
    await page1920.goto("http://127.0.0.1:3000/login", { waitUntil: "networkidle" });
    await page1920.getByLabel("Work Email").fill("demo@aegisops.local");
    await page1920.getByLabel("Password", { exact: true }).fill("demo-password-123");
    await page1920.locator('form button[type="submit"]').click();
    await page1920.waitForURL("**/app**", { timeout: 10000 });
    await page1920.waitForTimeout(1000);
    await page1920.screenshot({ path: path.join(OUT_DIR, "desktop_dashboard_1920x1080.png") });
    await context1920.close();

    // 3. Tablet 1024x768
    console.log("Capturing 1024x768 views...");
    const context1024 = await browser.newContext({
      viewport: { width: 1024, height: 768 },
      deviceScaleFactor: 1,
    });
    const page1024 = await context1024.newPage();
    await page1024.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
    await page1024.waitForTimeout(3800);
    await page1024.screenshot({ path: path.join(OUT_DIR, "tablet_homepage_1024x768.png") });
    await context1024.close();

    // 4. Mobile 390x844
    console.log("Capturing Mobile 390x844 views...");
    const mContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      isMobile: true,
      hasTouch: true,
    });
    const mPage = await mContext.newPage();
    await mPage.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
    await mPage.waitForTimeout(3800);
    await mPage.screenshot({ path: path.join(OUT_DIR, "mobile_homepage_390x844.png") });

    // Open mobile menu
    const menuBtn = mPage.locator(".nav-toggle");
    if (await menuBtn.count() > 0) {
      await menuBtn.click();
      await mPage.waitForTimeout(500);
      await mPage.screenshot({ path: path.join(OUT_DIR, "mobile_navigation_expanded.png") });
      await menuBtn.click();
      await mPage.waitForTimeout(300);
    }

    // Mobile login & dashboard
    await mPage.goto("http://127.0.0.1:3000/login", { waitUntil: "networkidle" });
    await mPage.getByLabel("Work Email").fill("demo@aegisops.local");
    await mPage.getByLabel("Password", { exact: true }).fill("demo-password-123");
    await mPage.locator('form button[type="submit"]').click();
    await mPage.waitForURL("**/app**", { timeout: 10000 });
    await mPage.waitForTimeout(1000);
    await mPage.screenshot({ path: path.join(OUT_DIR, "mobile_dashboard_390x844.png") });
    await mContext.close();

    // 5. Mobile 375x812
    console.log("Capturing Mobile 375x812 views...");
    const mContext375 = await browser.newContext({
      viewport: { width: 375, height: 812 },
      isMobile: true,
      hasTouch: true,
    });
    const mPage375 = await mContext375.newPage();
    await mPage375.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
    await mPage375.waitForTimeout(3800);
    await mPage375.screenshot({ path: path.join(OUT_DIR, "mobile_homepage_375x812.png") });

    await mPage375.goto("http://127.0.0.1:3000/login", { waitUntil: "networkidle" });
    await mPage375.getByLabel("Work Email").fill("demo@aegisops.local");
    await mPage375.getByLabel("Password", { exact: true }).fill("demo-password-123");
    await mPage375.locator('form button[type="submit"]').click();
    await mPage375.waitForURL("**/app**", { timeout: 10000 });
    await mPage375.waitForTimeout(1000);
    await mPage375.screenshot({ path: path.join(OUT_DIR, "mobile_dashboard_375x812.png") });
    await mContext375.close();

    console.log("All visual captures completed successfully in", OUT_DIR);
  } finally {
    await browser.close();
  }
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
