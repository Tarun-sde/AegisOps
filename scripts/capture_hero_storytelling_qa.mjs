import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const outDir = "/run/media/tarun/Tarun Files1/AegisOps/AegisOps/artifacts/hero-storytelling-qa";
await fs.mkdir(outDir, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox", "--disable-setuid-sandbox"],
});

async function run() {
  console.log("=== 1. CAPTURING REFERENCE HERO (http://127.0.0.1:3002) ===");
  const refCtx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const refPage = await refCtx.newPage();
  await refPage.goto("http://127.0.0.1:3002", { waitUntil: "networkidle" });
  await refPage.waitForTimeout(3000); // allow preloader
  await refPage.screenshot({
    path: path.join(outDir, "01_reference_hero_1440x900.png"),
    clip: { x: 0, y: 0, width: 1440, height: 900 },
  });
  await refCtx.close();

  console.log("=== 2. CAPTURING AEGISOP HERO AT DIFFERENT VIEWPORTS ===");
  const viewports = [
    { w: 1920, h: 1080, name: "desktop_1920x1080" },
    { w: 1440, h: 900, name: "desktop_1440x900" },
    { w: 1024, h: 768, name: "tablet_1024x768" },
    { w: 390, h: 844, name: "mobile_390x844" },
    { w: 375, h: 812, name: "mobile_375x812" },
  ];

  for (const vp of viewports) {
    const ctx = await browser.newContext({
      viewport: { width: vp.w, height: vp.h },
      deviceScaleFactor: 2,
    });
    const page = await ctx.newPage();
    await page.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
    await page.waitForTimeout(3500); // allow preloader to dismiss

    // Hero before inspection
    await page.screenshot({
      path: path.join(outDir, `02_hero_before_inspection_${vp.name}.png`),
      clip: { x: 0, y: 0, width: vp.w, height: vp.h },
    });

    // Inspect scenario
    const inspectBtn = page.getByRole("button", { name: "Inspect scenario" });
    if (await inspectBtn.isVisible()) {
      await inspectBtn.click();
      await page.waitForTimeout(600);
      await page.screenshot({
        path: path.join(outDir, `03_hero_after_inspection_${vp.name}.png`),
        clip: { x: 0, y: 0, width: vp.w, height: Math.min(vp.h * 1.3, 1200) },
      });
    }

    await ctx.close();
  }

  console.log("=== 3. CAPTURING DRAG-TO-INSPECT ON DESKTOP 1440x900 ===");
  {
    const ctx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 2,
    });
    const page = await ctx.newPage();
    await page.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
    await page.waitForTimeout(3500);

    const topology = page.locator(".interactive-topology");
    const box = await topology.boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width * 0.15, box.y + box.height * 0.1);
      await page.mouse.down();
      await page.mouse.move(box.x + box.width * 0.9, box.y + box.height * 0.9, { steps: 10 });
      await page.mouse.up();
      await page.waitForTimeout(500);
      await page.screenshot({
        path: path.join(outDir, "04_hero_drag_selection_active.png"),
        clip: { x: 0, y: 0, width: 1440, height: 900 },
      });
    }
    await ctx.close();
  }

  console.log("=== 4. CAPTURING SCROLL-LINKED STORYTELLING (0%, 25%, 50%, 75%, 100%) ===");
  {
    const ctx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 2,
    });
    const page = await ctx.newPage();
    await page.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
    await page.waitForTimeout(3500);

    // Scroll down to how-it-works section
    const workflow = page.locator("#how-it-works");
    await workflow.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);

    // Phase 0: Observe at start (progress 0)
    await page.locator(".phase-nav button").nth(0).click({ force: true });
    await page.waitForTimeout(700);
    await page.screenshot({
      path: path.join(outDir, "05_workflow_scene_00_observe_start.png"),
    });

    // Phase 1: Investigate / Advise (progress ~25-50%)
    await page.locator(".phase-nav button").nth(1).click({ force: true });
    await page.waitForTimeout(700);
    await page.screenshot({
      path: path.join(outDir, "06_workflow_scene_01_investigate_advise.png"),
    });

    // Phase 2: Act (progress ~50-75%)
    await page.locator(".phase-nav button").nth(2).click({ force: true });
    await page.waitForTimeout(700);
    await page.screenshot({
      path: path.join(outDir, "07_workflow_scene_02_act_approval.png"),
    });

    // Phase 3: Learn (progress 100%)
    await page.locator(".phase-nav button").nth(3).click({ force: true });
    await page.waitForTimeout(700);
    await page.screenshot({
      path: path.join(outDir, "08_workflow_scene_03_learn_history.png"),
    });

    // Reverse test: Go back to Phase 1 and Phase 0
    await page.locator(".phase-nav button").nth(1).click({ force: true });
    await page.waitForTimeout(700);
    await page.screenshot({
      path: path.join(outDir, "09_workflow_reverse_to_phase_1.png"),
    });

    await page.locator(".phase-nav button").nth(0).click({ force: true });
    await page.waitForTimeout(700);
    await page.screenshot({
      path: path.join(outDir, "10_workflow_reverse_to_phase_0.png"),
    });

    await ctx.close();
  }

  console.log("=== 5. CAPTURING MOBILE WORKFLOW (375x812) ===");
  {
    const ctx = await browser.newContext({
      viewport: { width: 375, height: 812 },
      deviceScaleFactor: 2,
    });
    const page = await ctx.newPage();
    await page.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
    await page.waitForTimeout(3500);

    const workflow = page.locator("#how-it-works");
    await workflow.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);

    // Mobile Phase 0
    await page.screenshot({
      path: path.join(outDir, "11_mobile_workflow_phase_0.png"),
    });

    // Mobile Phase 1
    await page.locator(".phase-nav button").nth(1).click();
    await page.waitForTimeout(600);
    await page.screenshot({
      path: path.join(outDir, "12_mobile_workflow_phase_1.png"),
    });

    // Mobile Phase 2
    await page.locator(".phase-nav button").nth(2).click();
    await page.waitForTimeout(600);
    await page.screenshot({
      path: path.join(outDir, "13_mobile_workflow_phase_2.png"),
    });

    // Mobile Phase 3
    await page.locator(".phase-nav button").nth(3).click();
    await page.waitForTimeout(600);
    await page.screenshot({
      path: path.join(outDir, "14_mobile_workflow_phase_3.png"),
    });

    await ctx.close();
  }

  console.log("=== 6. CAPTURING REDUCED-MOTION BEHAVIOR ===");
  {
    const ctx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 2,
      reducedMotion: "reduce",
    });
    const page = await ctx.newPage();
    await page.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);

    await page.screenshot({
      path: path.join(outDir, "15_reduced_motion_hero_complete.png"),
      clip: { x: 0, y: 0, width: 1440, height: 900 },
    });

    const workflow = page.locator("#how-it-works");
    await workflow.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);

    await page.screenshot({
      path: path.join(outDir, "16_reduced_motion_workflow_complete.png"),
    });

    await ctx.close();
  }

  await browser.close();
  console.log("ALL QA SCREENSHOTS CAPTURED SUCCESSFULLY in:", outDir);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
