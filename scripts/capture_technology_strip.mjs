import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const outDir = "/run/media/tarun/Tarun Files1/AegisOps/AegisOps/artifacts/technology-strip";
await fs.mkdir(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });

async function captureStrip(width, height, name) {
  const context = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  await page.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
  await page.waitForTimeout(3500); // allow preloader to dismiss

  const strip = page.locator(".practice-strip");
  await strip.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);

  // Capture isolated element
  await strip.screenshot({ path: path.join(outDir, `${name}_element.png`) });

  // Capture section in context (with introductory text above)
  const introAndStrip = page.locator(".intro, .practice-strip");
  const introBox = await page.locator(".intro").boundingBox();
  const stripBox = await strip.boundingBox();
  
  if (introBox && stripBox) {
    const y = Math.max(0, introBox.y + introBox.height - 180);
    const clipHeight = stripBox.y + stripBox.height - y + 40;
    await page.screenshot({
      path: path.join(outDir, `${name}_context.png`),
      clip: {
        x: 0,
        y: y,
        width: width,
        height: clipHeight,
      },
    });
  }

  await context.close();
}

console.log("Capturing Desktop 1440x900...");
await captureStrip(1440, 900, "desktop_1440x900");

console.log("Capturing Tablet 768x1024...");
await captureStrip(768, 1024, "tablet_768x1024");

console.log("Capturing Mobile 375x812...");
await captureStrip(375, 812, "mobile_375x812");

await browser.close();
console.log("Technology strip capture complete!");
