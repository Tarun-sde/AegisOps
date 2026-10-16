import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const ARTIFACTS_DIR = "/home/tarun/.gemini/antigravity-ide/brain/ea6eb491-675a-4b2f-a002-461ab04d73cc";
const SESSION_COOKIE = "ABTQJ2P_3d0gsynbVyb7Is4yge8Q_eQROjTltywUNMY";
const SERVICE_ID = "40c1e585-f9b2-4977-9b7d-0a0bd51fae66";
const HEALTHCHECK_URL = "https://ironlog-backend-jrqs.onrender.com/api/health";

async function main() {
  console.log("=== AegisOps Real Localhost:3000 Runtime Verification ===");

  const browser = await chromium.launch({
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    baseURL: "http://localhost:3000",
  });

  // Inject user session cookie for mukeshjoshi01980@gmail.com
  await context.addCookies([
    {
      name: "aegisops_session",
      value: SESSION_COOKIE,
      domain: "localhost",
      path: "/",
      httpOnly: false,
      secure: false,
      sameSite: "Lax",
    },
  ]);

  const page = await context.newPage();

  // 1. Visit workspace
  console.log("1. Navigating to http://localhost:3000/app ...");
  const appRes = await page.goto("/app", { waitUntil: "networkidle" });
  console.log("App response status:", appRes.status(), "URL:", page.url());

  const appTitle = await page.title();
  console.log("Page title:", appTitle);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "real_01_workspace_dashboard.png"), fullPage: true });

  // 2. Navigate to IRONLOG application
  console.log(`2. Navigating to IRONLOG application (/app/services/${SERVICE_ID}) ...`);
  const serviceRes = await page.goto(`/app/services/${SERVICE_ID}`, { waitUntil: "networkidle" });
  console.log("Service response status:", serviceRes.status(), "URL:", page.url());

  // Check tabs
  const tabTexts = await page.locator(".ws-project-tabs a").allInnerTexts();
  console.log("Application tabs rendered in UI:", tabTexts);
  if (!tabTexts.includes("Settings")) {
    throw new Error(`Settings tab missing from navigation! Found tabs: ${JSON.stringify(tabTexts)}`);
  }
  console.log("SUCCESS: Settings tab is present in application detail navigation.");
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "real_02_ironlog_overview.png"), fullPage: true });

  // 3. Inspect Analytics tab
  console.log("3. Clicking Analytics tab ...");
  await page.click('.ws-project-tabs a:has-text("Analytics")');
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1000);
  console.log("Analytics view URL:", page.url());

  const analyticsHeading = await page.locator("h2").allInnerTexts();
  console.log("Headings in Analytics view:", analyticsHeading);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "real_03_ironlog_analytics_view.png"), fullPage: true });

  // 4. Click Settings tab
  console.log("4. Clicking Settings tab ...");
  await page.click('.ws-project-tabs a:has-text("Settings")');
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1000);
  console.log("Settings view URL:", page.url());

  const inputSelector = "#service-healthcheck-input";
  await page.waitForSelector(inputSelector, { state: "visible", timeout: 5000 });
  console.log("Found healthcheck URL input field #service-healthcheck-input");
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "real_04_ironlog_settings_initial.png"), fullPage: true });

  // 5. Fill Healthcheck URL
  console.log(`5. Entering Healthcheck URL: ${HEALTHCHECK_URL} ...`);
  await page.fill(inputSelector, HEALTHCHECK_URL);

  // 6. Save connection settings
  console.log("6. Clicking Save Connection Settings ...");
  await page.click('button.ws-button.ws-primary:has-text("Save Connection Settings")');
  await page.waitForSelector('.an-alert-success, [role="status"]:has-text("Saved")', { timeout: 10000 });
  const saveSuccessText = await page.locator('[role="status"]').innerText();
  console.log("Save status notification:", saveSuccessText);

  // 7. Test connection now
  console.log("7. Clicking Test Connection Now button ...");
  await page.click('button.ws-button:has-text("Test Connection Now")');
  await page.waitForSelector('[role="status"]:has-text("Probe Succeeded")', { timeout: 15000 });
  const probeResultText = await page.locator('[role="status"]:has-text("Probe Succeeded")').innerText();
  console.log("Probe result notification:", probeResultText);

  // Allow router refresh / observation table update
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "real_05_ironlog_settings_saved_and_tested.png"), fullPage: true });

  // 8. Refresh page to verify persistence
  console.log("8. Reloading page to verify persistence ...");
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(1500);

  const reloadedUrlValue = await page.inputValue(inputSelector);
  console.log("Persisted Healthcheck URL in input after reload:", reloadedUrlValue);
  if (reloadedUrlValue !== HEALTHCHECK_URL) {
    throw new Error(`Expected Healthcheck URL to be ${HEALTHCHECK_URL}, but found ${reloadedUrlValue}`);
  }
  console.log("SUCCESS: Healthcheck URL persisted across page reload!");

  // Check header health badge
  const headerHealthBadge = await page.locator(".ws-project-badges .ws-health").innerText();
  console.log("Header health badge text:", headerHealthBadge);

  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "real_06_ironlog_settings_persisted_after_refresh.png"), fullPage: true });

  // Check observations table
  const obsRows = await page.locator(".an-service-table tbody tr").count();
  console.log("Number of historical health observation rows rendered:", obsRows);

  console.log("\n=== ALL REAL LOCALHOST:3000 ACCEPTANCE CHECKS PASSED SUCCESSFULLY ===");
  await browser.close();
}

main().catch((err) => {
  console.error("FATAL ERROR in real verification:", err);
  process.exit(1);
});
