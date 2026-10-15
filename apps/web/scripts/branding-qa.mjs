/* DEC-363: actual Compose UI, no data seeding or operational mutations.
   QA credentials are read from the existing private Phase 8.1 QA file. */
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import process from "node:process";
import console from "node:console";
/* global document, innerWidth, getComputedStyle */
const qa = JSON.parse(fs.readFileSync(process.env.PHASE81_QA_FILE));
const output = "artifacts/phase8-2/after";
const imageId = () =>
  execFileSync(
    "docker",
    ["inspect", "--format", "{{.Image}}", "aegisops-web-1"],
    { encoding: "utf8" },
  ).trim();
const deliveredImage = imageId();
const browser = await chromium.launch();
const results = [];
try {
  const viewports = [
    [1920, 1080],
    [1440, 900],
    [1440, 700],
    [1024, 768],
    [390, 844],
    [375, 812],
  ];
  for (let batch = 0; batch < viewports.length; batch += 2) {
    await Promise.all(
      viewports.slice(batch, batch + 2).map(async ([width, height]) => {
        const context = await browser.newContext({
          viewport: { width, height },
        });
        const page = await context.newPage();
        const errors = [],
          warnings = [],
          publicRequests = [],
          overflow = [],
          axe = [];
        let publicPage = true;
        page.on("pageerror", (e) => errors.push(e.message));
        page.on("console", (m) => {
          if (m.type() === "warning" || m.type() === "error")
            warnings.push(m.text());
        });
        page.on("request", (r) => {
          if (publicPage && r.url().includes("/api/v1/"))
            publicRequests.push(r.url());
        });
        const dir = path.join(output, `${width}x${height}`);
        fs.mkdirSync(dir, { recursive: true });
        const capture = async (name) => {
          await page.screenshot({ path: path.join(dir, `${name}.png`) });
          overflow.push([
            name,
            await page.evaluate(
              () => document.documentElement.scrollWidth > innerWidth,
            ),
          ]);
        };
        const go = async (route) => {
          await page.goto(`http://127.0.0.1:3000${route}`, {
            waitUntil: "domcontentloaded",
          });
          await page.waitForTimeout(700);
        };
        const section = async (selector, name) => {
          await page.locator(selector).first().scrollIntoViewIfNeeded();
          await page.waitForTimeout(900);
          await capture(name);
        };
        const scan = async (name) => {
          if (width !== 1440 || height !== 900) return;
          const r = await new AxeBuilder({ page }).analyze();
          axe.push({
            name,
            violations: r.violations
              .filter((v) => ["serious", "critical"].includes(v.impact))
              .map((v) => ({
                id: v.id,
                nodes: v.nodes.map((n) => ({
                  target: n.target,
                  summary: n.failureSummary,
                })),
              })),
          });
        };
        await go("/");
        await capture("preloader");
        await page.locator(".preloader").waitFor({ state: "hidden" });
        await page.waitForTimeout(1700);
        await capture("hero");
        assert((await page.locator(".interactive-topology").count()) === 1);
        await page.getByRole("button", { name: "Inspect scenario" }).click();
        await capture("hero-inspected");
        assert((await page.locator(".issue-marker.is-active").count()) === 3);
        await scan("home-inspected");
        await section(".intro", "intro");
        await section(".practice-strip", "technology-strip");
        await section(".problem-section", "problems");
        for (let i = 0; i < 4; i++) {
          await page.locator(".phase-nav button").nth(i).click({ force: true });
          await page.waitForTimeout(1600);
          if (width < 992)
            await page.locator(".workflow-drawing").scrollIntoViewIfNeeded();
          await capture(`workflow-${i}`);
          const opacity = await page
            .locator(`.workflow-scene-${i}`)
            .evaluate((el) => getComputedStyle(el).opacity);
          assert.equal(opacity, "1", `Workflow ${i} visible at ${width}`);
        }
        await section("#platforms", "platform-signals");
        for (const tool of ["Logs", "Traces", "Runbooks"]) {
          await page.getByRole("tab", { name: tool, exact: true }).click();
          await page.waitForTimeout(600);
          await capture(`signals-${tool.toLowerCase()}`);
        }
        await section(".product-row", "product-preview");
        for (let i = 0; i < 4; i++) {
          await page.locator(".why-steps button").nth(i).click();
          await page.waitForTimeout(750);
          await section(".why-art", `why-${i}`);
        }
        await section(".use-cases", "use-cases");
        await section(".final-cta", "ink-reveal");
        await section(".footer-wordmark", "footer");
        if (width < 601)
          await section(".footer-compact-network", "footer-compact");
        const lens = await page.locator(".footer-wordmark").boundingBox();
        await page.mouse.move(
          lens.x + lens.width * 0.5,
          lens.y + lens.height * 0.5,
        );
        await page.waitForTimeout(1000);
        await capture("footer-lens");
        await go("/platform");
        await page.waitForTimeout(1500);
        await capture("showcase-hero");
        for (let i = 0; i < 5; i++) {
          await page
            .locator(".feature-tabs button")
            .nth(i)
            .click({ force: true });
          await page.waitForTimeout(1500);
          await capture(`showcase-${i}`);
        }
        await page.emulateMedia({ reducedMotion: "reduce" });
        assert(
          (await page.locator(".approval-detail").textContent()).includes(
            "service_name: shop-api",
          ),
        );
        assert(
          (await page.locator(".approval-detail").textContent()).includes(
            "grace_period_seconds: 10",
          ),
        );
        await page
          .getByRole("button", { name: "Approve sample", exact: false })
          .click();
        await capture("sample-approved");
        assert(
          (await page.getByRole("status").textContent()).includes(
            "Execution has not occurred",
          ),
        );
        await page
          .getByRole("button", {
            name: "Can the AI execute production changes?",
          })
          .click();
        await capture("faq");
        await scan("platform");
        assert.deepEqual(publicRequests, []);
        publicPage = false;
        await go("/login");
        await page.getByLabel("Work Email").fill(qa.email);
        await page.getByLabel("Password", { exact: true }).fill(qa.password);
        await page.locator('form button[type="submit"]').click();
        await page.waitForURL(/\/app$/);
        await page.locator(".ws-project-card").first().waitFor();
        await page
          .locator(".ws-context .ws-demo-label")
          .filter({ hasText: "AUTHORIZED DATA" })
          .waitFor({ state: "attached" });
        await capture("workspace");
        await scan("workspace");
        if (width < 992) {
          await page
            .getByRole("button", { name: "Open workspace navigation" })
            .click();
          await capture("workspace-drawer");
          await page.keyboard.press("Escape");
        }
        await go(`/app/services/${qa.service}`);
        await page.locator(".an-empty-chart").first().waitFor();
        await capture("service-overview");
        await section(".an-primary-chart", "analytics");
        await scan("analytics");
        await go("/app/incidents");
        await page
          .getByRole("heading", { name: /Incident/ })
          .first()
          .waitFor();
        await capture("incidents");
        await scan("incidents");
        await go(`/app/incidents/${qa.incident}`);
        await page.locator(".an-hypotheses").waitFor();
        await capture("investigation");
        await section(".an-hypotheses", "hypotheses");
        await section(".an-evidence", "evidence");
        await scan("investigation");
        assert.equal(
          imageId(),
          deliveredImage,
          "Web image must stay fixed throughout the capture run",
        );
        results.push({
          deliveredImage,
          width,
          height,
          errors,
          warnings,
          publicRequests,
          overflow,
          axe,
        });
        fs.writeFileSync(
          path.join(output, "measurements.json"),
          JSON.stringify(results, null, 2),
        );
        assert.equal(errors.length, 0);
        assert(
          !overflow.some(([, value]) => value),
          `Overflow at ${width}: ${overflow
            .filter(([, value]) => value)
            .map(([name]) => name)
            .join(", ")}`,
        );
        assert(
          !axe.some((r) => r.violations.length),
          `Accessibility failures at ${width}`,
        );
        console.log(
          `PASS ${width}x${height}: ${overflow.length} captures, no overflow/page errors, public APIs isolated`,
        );
        await context.close();
      }),
    );
  }
} finally {
  await browser.close();
}
