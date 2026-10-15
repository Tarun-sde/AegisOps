/* DEC-356: rendered comparison against an untouched reference and the real Compose web image.
   Run from repository root with PHASE81_AUTH_STATE and PHASE81_QA_FILE pointing to private QA files. */
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import process from "node:process";
import console from "node:console";
/* global document, innerWidth, window */
const widths = [
  [1920, 1080],
  [1440, 900],
  [1440, 700],
  [1024, 768],
  [390, 844],
  [375, 812],
];
const output = process.env.PARITY_OUTPUT || "artifacts/phase8-1/parity";
const qa = JSON.parse(fs.readFileSync(process.env.PHASE81_QA_FILE));
const state = process.env.PHASE81_AUTH_STATE;
(async () => {
  const browser = await chromium.launch();
  const results = [];
  for (const [width, height] of widths) {
    for (const [kind, port] of [
      ["reference", 3002],
      ["actual", 3000],
    ]) {
      if (process.env.PARITY_KIND && process.env.PARITY_KIND !== kind) continue;
      const context = await browser.newContext({
        viewport: { width, height },
        ...(kind === "actual" ? { storageState: state } : {}),
      });
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      const dir = path.join(output, `${width}x${height}`, kind);
      fs.mkdirSync(dir, { recursive: true });
      const capture = async (name) => {
        await page.screenshot({
          path: path.join(dir, `${name}.png`),
          animations: "allow",
        });
      };
      const go = async (route) => {
        await page.goto(`http://127.0.0.1:${port}${route}`, {
          waitUntil: "domcontentloaded",
        });
        await page.waitForTimeout(700);
      };
      const box = async (sel) => page.locator(sel).first().boundingBox();
      await go("/");
      await capture("preloader");
      await page.locator(".preloader").waitFor({ state: "hidden" });
      await page.waitForTimeout(1700);
      await capture("hero");
      const hero = await box(".interactive-elevation");
      assert(
        hero && hero.width > width * 0.7,
        "Hero must use reference full-width composition",
      );
      if (width >= 1024) {
        await page.mouse.move(
          hero.x + hero.width * 0.16,
          hero.y + hero.height * 0.15,
        );
        await page.mouse.down();
        await page.mouse.move(
          hero.x + hero.width * 0.9,
          hero.y + hero.height * 0.9,
          { steps: 18 },
        );
        await capture("hero-drag");
        await page.mouse.up();
      } else
        await page.getByRole("button", { name: "Inspect all issues" }).click();
      assert(
        (await page.locator(".issue-marker.is-active").count()) > 0,
        "Inspection must change visible SVG marker state",
      );
      await capture("hero-inspected");
      await page.locator(".phase-nav").scrollIntoViewIfNeeded();
      await page.waitForTimeout(500);
      for (const phase of ["Observe", "Advise", "Act", "Learn"]) {
        await page
          .locator(".phase-nav")
          .getByRole("button", { name: new RegExp(phase) })
          .click({ force: true });
        await page.waitForTimeout(1400);
        await capture(`workflow-${phase.toLowerCase()}`);
      }
      await page.locator("#platforms").scrollIntoViewIfNeeded();
      await page.waitForTimeout(1000);
      await capture("platforms");
      await page.locator(".product-row").first().scrollIntoViewIfNeeded();
      await page.waitForTimeout(700);
      await capture("product-preview");
      await page.locator(".final-cta").scrollIntoViewIfNeeded();
      await page.waitForTimeout(1000);
      await capture("ink-reveal");
      await page.locator(".footer-wordmark").scrollIntoViewIfNeeded();
      const footer = await box(".footer-wordmark");
      await page.mouse.move(
        footer.x + footer.width * 0.5,
        footer.y + footer.height * 0.5,
      );
      await page.waitForTimeout(800);
      await capture("footer-lens");
      await go(kind === "reference" ? "/projects/personal" : "/app");
      await capture("workspace-grid");
      assert(
        (await page.locator(".ws-sidebar").count()) === 1,
        "One architectural sidebar",
      );
      assert(
        (await page.locator(".header").count()) === 0,
        "No marketing header in workspace",
      );
      const sidebar = await box(".ws-sidebar");
      const card = await box(".ws-project-card");
      assert(card, "Registered card rendered");
      await page.locator(".ws-project-card").first().scrollIntoViewIfNeeded();
      await capture("workspace-card");
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.getByRole("button", { name: "List view" }).click();
      await capture("workspace-list");
      if (width >= 1024) {
        await page.getByRole("button", { name: "Collapse sidebar" }).click();
        await page.waitForTimeout(300);
        const rail = await box(".ws-sidebar");
        assert(
          rail.width < sidebar.width,
          "Collapse changes rendered rail width",
        );
        await capture("workspace-collapsed");
        await page.getByRole("button", { name: "Expand sidebar" }).click();
      } else {
        await page
          .getByRole("button", { name: "Open workspace navigation" })
          .click();
        await capture("workspace-drawer");
        await page.keyboard.press("Escape");
      }
      await go(
        kind === "reference"
          ? "/projects/northstar/payment-gateway"
          : `/app/services/${qa.service}`,
      );
      await capture("service-overview");
      const metric = page
        .locator(".an-metric")
        .filter({ hasText: "p95" })
        .first();
      await metric.click();
      await page.locator(".an-primary-chart").scrollIntoViewIfNeeded();
      await page.waitForTimeout(400);
      await capture("analytics-chart");
      assert(
        (await page.locator(".an-metric[aria-pressed=true]").count()) === 1,
        "Selected metric state",
      );
      if (kind === "reference") {
        const chart = await box(".an-chart-svg");
        if (chart)
          await page.mouse.move(
            chart.x + chart.width * 0.6,
            chart.y + chart.height * 0.5,
          );
        await capture("chart-interaction");
      } else {
        assert(
          (await page.locator(".an-empty-chart").textContent()).includes(
            "No healthy value",
          ),
          "Missing series is explicit",
        );
        await capture("chart-unavailable");
      }
      await page.locator("#services").scrollIntoViewIfNeeded();
      await capture("service-table");
      await page.locator("#incidents").scrollIntoViewIfNeeded();
      await capture("incident-register");
      await go(
        kind === "reference"
          ? "/projects/northstar/payment-gateway/incidents/inc-payment-gw-01"
          : `/app/incidents/${qa.incident}`,
      );
      await capture("investigation");
      await page.locator(".an-hypotheses").scrollIntoViewIfNeeded();
      await capture("hypotheses-timeline");
      await page.locator(".an-evidence").scrollIntoViewIfNeeded();
      await capture("evidence");
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      );
      results.push({
        kind,
        width,
        height,
        hero,
        sidebar,
        card,
        incidentOverflow: overflow,
        errors,
      });
      console.log(
        `${kind} ${width}x${height}: captured; overflow=${overflow}; errors=${errors.length}`,
      );
      await context.close();
    }
  }
  await browser.close();
  fs.writeFileSync(
    path.join(
      output,
      process.env.PARITY_KIND
        ? `measurements-${process.env.PARITY_KIND}.json`
        : "measurements.json",
    ),
    JSON.stringify(results, null, 2),
  );
  for (const r of results.filter((r) => r.kind === "actual")) {
    assert(!r.incidentOverflow, `Incident overflow ${r.width}`);
    assert.equal(r.errors.length, 0);
    const reference = results.find(
      (v) =>
        v.kind === "reference" && v.width === r.width && v.height === r.height,
    );
    if (reference) {
      for (const part of ["hero", "sidebar", "card"]) {
        if (r[part] && reference[part])
          assert(
            Math.abs(r[part].width - reference[part].width) < 1,
            `${part} width matches reference at ${r.width}x${r.height}`,
          );
      }
    }
  }
  console.log(
    "PASS: rendered state comparison capture and interaction assertions",
  );
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
