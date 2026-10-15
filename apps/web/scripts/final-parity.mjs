/* DEC-382: matched source/Docker states, real authorized synthetic QA records. */
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import console from "node:console";
/* global window, document, innerWidth, innerHeight, performance */
const output = "artifacts/final-design-parity/gallery";
const qa = JSON.parse(fs.readFileSync(".cache/final-parity-private/qa.json"));
const browser = await chromium.launch();
const measurements = [];
const widths = process.env.PARITY_WIDTH
  ? [[Number(process.env.PARITY_WIDTH), Number(process.env.PARITY_HEIGHT)]]
  : [
      [1920, 1080],
      [1440, 900],
      [1024, 768],
      [390, 844],
      [375, 812],
    ];
try {
  for (const [width, height] of widths) {
    for (const [kind, port] of [
      ["reference", 3002],
      ["actual", 3000],
    ]) {
      if (process.env.PARITY_KIND && process.env.PARITY_KIND !== kind) continue;
      const ctx = await browser.newContext({
        viewport: { width, height },
        ...(kind === "actual"
          ? { storageState: ".cache/final-parity-private/auth.json" }
          : {}),
      });
      const page = await ctx.newPage();
      await page.addInitScript(() => {
        for (const event of ["heron:entrance", "aegisops:entrance"])
          window.addEventListener(event, () => {
            window.parityEntrance = performance.now();
          });
      });
      const errors = [],
        warnings = [],
        overflow = [],
        geometry = {},
        axe = [];
      page.on("pageerror", (e) => errors.push(e.message));
      page.on("console", (m) => {
        if (m.type() === "warning" && !m.text().includes("development"))
          warnings.push(m.text());
      });
      const dir = path.join(output, `${width}x${height}`, kind);
      fs.mkdirSync(dir, { recursive: true });
      const snap = async (name) => {
        await page.screenshot({ path: path.join(dir, `${name}.png`) });
        const excess = await page.evaluate(
          () => document.documentElement.scrollWidth - innerWidth,
        );
        if (excess > 1) overflow.push({ name, excess });
      };
      const go = async (route) => {
        await page.goto(`http://localhost:${port}${route}`, {
          waitUntil: "networkidle",
        });
      };
      const settle = () => page.waitForTimeout(1800);
      await go("/");
      await snap("00-entrance");
      await page.waitForFunction(() => window.parityEntrance !== undefined);
      await page.waitForFunction(
        () => performance.now() - window.parityEntrance >= 650,
      );
      geometry.entranceMidMilliseconds = await page.evaluate(
        () => performance.now() - window.parityEntrance,
      );
      await snap("00-mid-entrance");
      await page
        .locator(".preloader")
        .waitFor({ state: "hidden", timeout: 20000 });
      await settle();
      await snap("01-hero");
      for (const s of [
        ".header",
        ".hero",
        ".hero-drawing",
        ".interactive-elevation",
        ".hero-caption",
        ".hero-caption h1",
      ])
        geometry[s] = await page.locator(s).first().boundingBox();
      if (width >= 1024) {
        const r = geometry[".interactive-elevation"];
        await page.mouse.move(r.x + r.width * 0.12, r.y + r.height * 0.15);
        await page.mouse.down();
        await page.mouse.move(r.x + r.width * 0.88, r.y + r.height * 0.85, {
          steps: 16,
        });
        await snap("02-drag");
        await page.mouse.up();
      } else await page.locator(".drawing-toolbar button").click();
      await snap("03-inspection");
      await page.locator(".drawing-toolbar button").click();
      for (const [i, name] of [
        [0, "observe"],
        [1, "advise"],
        [2, "act"],
        [3, "learn"],
        [1, "reverse-advise"],
        [0, "reverse-observe"],
      ]) {
        await page.locator(".phase-nav button").nth(i).click({ force: true });
        await settle();
        if (width >= 992)
          await page.evaluate(
            ({ i }) => {
              const track = document
                .querySelector(".workflow-track")
                .getBoundingClientRect();
              window.scrollTo(
                0,
                window.scrollY +
                  track.top -
                  document.querySelector("header").offsetHeight -
                  8 +
                  innerHeight * 6 * ((i + 0.85) / 4),
              );
            },
            { i },
          );
        if (width < 992)
          await page.evaluate(() => {
            const scene = document
              .querySelector(".model-workflow")
              .getBoundingClientRect();
            window.scrollTo(
              0,
              window.scrollY +
                scene.top -
                document.querySelector("header").offsetHeight -
                8,
            );
          });
        await settle();
        geometry[`workflow-${name}`] = await page.evaluate(() => ({
          scrollY: window.scrollY,
          trackTop: document
            .querySelector(".workflow-track")
            .getBoundingClientRect().top,
          path: document
            .querySelector(".workflow-drawing .editable-door")
            .getAttribute("d"),
        }));
        await snap(`04-workflow-${name}`);
      }
      for (const [sel, name] of [
        [".intro", "intro"],
        [".problem-section", "problems"],
        ["#platforms", "signals"],
        [".product-row", "preview"],
        [".why-section", "why"],
        [".use-cases", "use-cases"],
        [".final-cta", "ink"],
        [".footer-wordmark", "footer"],
      ]) {
        await page.locator(sel).first().scrollIntoViewIfNeeded();
        await settle();
        await snap(`05-${name}`);
      }
      if (kind === "actual" && width === 1440)
        axe.push({
          route: "/",
          violations: (await new AxeBuilder({ page }).analyze()).violations
            .filter((v) => ["serious", "critical"].includes(v.impact))
            .map((v) => ({
              id: v.id,
              nodes: v.nodes.map((n) => ({
                target: n.target,
                summary: n.failureSummary,
              })),
            })),
        });
      await go(kind === "reference" ? "/heron-dashboard" : "/platform");
      await settle();
      await snap("06-platform");
      for (let i = 0; i < 5; i++) {
        await page
          .locator(".feature-tabs button")
          .nth(i)
          .click({ force: true });
        await settle();
        if (width >= 992)
          await page.evaluate(
            ({ i }) => {
              const track = document
                .querySelector(".feature-track")
                .getBoundingClientRect();
              window.scrollTo(
                0,
                window.scrollY +
                  track.top -
                  document.querySelector("header").offsetHeight -
                  8 +
                  innerHeight * 4 * ((i + 0.85) / 5),
              );
            },
            { i },
          );
        await settle();
        await snap(`07-feature-${i}`);
        if (width < 992) {
          await page.evaluate(
            ({ i }) => {
              const visual = document
                .querySelector(`#feature-${i} .feature-visual`)
                .getBoundingClientRect();
              window.scrollTo(
                0,
                window.scrollY +
                  visual.top +
                  visual.height / 2 -
                  innerHeight * 0.44,
              );
            },
            { i },
          );
          await settle();
          await snap(`07-feature-${i}-complete`);
        }
      }
      await page.locator(".feature-tabs button").nth(1).click({ force: true });
      await settle();
      await page
        .getByRole("button", {
          name: kind === "reference" ? "Approve" : "Approve sample",
          exact: false,
        })
        .first()
        .click({ force: true });
      await snap("08-preview-approved");
      await page.locator("#feature-1 .product-preview").first().hover();
      await snap("08-preview-hover");
      await go(kind === "reference" ? "/projects/personal" : "/app");
      if (
        kind === "actual" &&
        !(await page.locator(".ws-project-card").count())
      ) {
        await go("/login");
        await page.getByLabel("Work Email").fill(qa.email);
        await page.getByLabel("Password", { exact: true }).fill(qa.password);
        await page.locator('form button[type="submit"]').click();
        await page.waitForURL(/\/app$/);
      }
      await page.locator(".ws-project-card").first().waitFor();
      await settle();
      await snap("09-workspace");
      await page.locator(".ws-project-card").first().hover();
      await snap("09-workspace-hover");
      geometry.sidebar = await page.locator(".ws-sidebar").boundingBox();
      geometry.card = await page
        .locator(".ws-project-card")
        .first()
        .boundingBox();
      await page.getByRole("button", { name: "List view" }).click();
      await snap("10-workspace-list");
      await go(
        kind === "reference"
          ? "/projects/northstar/payment-gateway"
          : `/app/services/${qa.service}`,
      );
      await settle();
      await snap("11-service");
      await page.locator(".an-primary-chart").scrollIntoViewIfNeeded();
      await settle();
      await snap("12-analytics");
      await page.locator("#incidents").scrollIntoViewIfNeeded();
      await snap("13-incidents");
      await go(
        kind === "reference"
          ? "/projects/northstar/payment-gateway/incidents/inc-payment-gw-01"
          : `/app/incidents/${qa.incident}`,
      );
      await settle();
      await snap("14-investigation");
      for (const [sel, name] of [
        [".an-hypotheses", "hypotheses"],
        [".an-evidence", "evidence"],
      ]) {
        await page.locator(sel).first().scrollIntoViewIfNeeded();
        await settle();
        await snap(`15-${name}`);
      }
      const evidenceTabs = page.locator(".an-evidence-tabs button");
      if ((await evidenceTabs.count()) > 1) {
        await evidenceTabs.nth(1).click();
        await snap("15-evidence-selected");
      }
      if (kind === "actual") {
        if (width === 1440)
          axe.push({
            route: "incident",
            violations: (await new AxeBuilder({ page }).analyze()).violations
              .filter((v) => ["serious", "critical"].includes(v.impact))
              .map((v) => ({
                id: v.id,
                nodes: v.nodes.map((n) => ({
                  target: n.target,
                  summary: n.failureSummary,
                })),
              })),
          });
        for (const route of [
          "services",
          "incidents",
          "runbooks",
          "proposals",
          "simulation-lab",
        ]) {
          await go(`/app/${route}`);
          await settle();
          await snap(`16-${route}`);
        }
      }
      measurements.push({
        kind,
        width,
        height,
        geometry,
        errors,
        warnings,
        overflow,
        axe,
      });
      fs.writeFileSync(
        path.join(output, `results-${kind}-${width}.json`),
        JSON.stringify(measurements.at(-1), null, 2),
      );
      console.log(kind, width, JSON.stringify({ errors, warnings, overflow }));
      await ctx.close();
    }
  }
} finally {
  await browser.close();
}
