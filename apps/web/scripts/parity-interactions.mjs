/* DEC-382: supplemental start, menu and footer-hover comparisons. */
import { chromium } from "playwright";
import fs from "node:fs";
/* global document, window, innerHeight */
const browser = await chromium.launch();
try {
  for (const [width, height] of [
    [1920, 1080],
    [1440, 900],
    [1024, 768],
    [390, 844],
    [375, 812],
  ]) {
    for (const [kind, port] of [
      ["reference", 3002],
      ["actual", 3000],
    ]) {
      const context = await browser.newContext({ viewport: { width, height } });
      const page = await context.newPage();
      const dir = `artifacts/final-design-parity/gallery/${width}x${height}/${kind}`;
      fs.mkdirSync(dir, { recursive: true });
      await page.goto(`http://localhost:${port}`, { waitUntil: "networkidle" });
      await page.locator(".preloader").waitFor({ state: "hidden" });
      await page.waitForTimeout(1500);
      if (width < 992) {
        await page.getByRole("button", { name: /Menu/ }).click();
        await page.screenshot({ path: `${dir}/17-mobile-menu.png` });
        await page.getByRole("button", { name: "Close navigation" }).click();
      }
      await page.evaluate(() => {
        const rect = document
          .querySelector(".workflow-track")
          .getBoundingClientRect();
        window.scrollTo(
          0,
          window.scrollY +
            rect.top -
            document.querySelector("header").offsetHeight -
            8 +
            innerHeight * 6 * 0.02,
        );
      });
      await page.waitForTimeout(1800);
      await page.screenshot({ path: `${dir}/17-workflow-start.png` });
      await page.locator(".footer-wordmark").scrollIntoViewIfNeeded();
      await page.waitForTimeout(1800);
      await page.locator(".footer-wordmark").hover();
      await page.waitForTimeout(600);
      await page.screenshot({ path: `${dir}/17-footer-hover.png` });
      if (
        await page.evaluate(
          () => document.documentElement.scrollWidth > window.innerWidth + 1,
        )
      )
        throw new Error(`${kind} ${width}: horizontal overflow`);
      await context.close();
    }
  }
} finally {
  await browser.close();
}
