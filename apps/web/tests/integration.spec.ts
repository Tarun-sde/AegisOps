import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const api = process.env.BROWSER_API_URL!;
const incidentId = "00000000-0000-0000-0000-000000000067";
const serviceId = "00000000-0000-0000-0000-000000000066";
const orgId = "00000000-0000-0000-0000-000000000064";
async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Work Email").fill("browser-gate@example.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill(process.env.BROWSER_TEST_PASSWORD!);
  await page.locator('form button[type="submit"]').click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.locator(".ws-context")).toContainText(
    "Browser Gate Workspace",
  );
}
async function csrf(page: Page) {
  return {
    "x-csrf-token": (await page.context().cookies()).find(
      (c) => c.name === "aegisops_csrf",
    )!.value,
  };
}

test("service collection uses authenticated records, filters, list and detail without synthetic health", async ({
  page,
}) => {
  await login(page);
  const response = await page.request.get(`${api}/api/v1/services`);
  expect(response.status()).toBe(200);
  const services = await response.json();
  await expect(
    page.getByRole("heading", {
      name: `Registered services (${services.length})`,
    }),
  ).toBeVisible();
  await page.getByLabel("Search services").fill("nonexistent-service");
  await expect(
    page.getByRole("heading", { name: "No matching applications" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await page.getByLabel("Environment", { exact: true }).selectOption("staging");
  await page.getByRole("button", { name: "List view" }).click();
  await expect(page.locator(".service-collection")).toHaveClass(/list/);
  await page.getByRole("link", { name: "shop-api", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/app/services/${serviceId}$`));
  await expect(
    page.getByText("No performance data available yet.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Monitoring unknown").first()).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "shop-api", exact: true }),
  ).toBeVisible();
});

test("landing interaction, reduced motion and mobile keyboard navigation", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.getByRole("button", { name: "Inspect scenario" }).click();
  await expect(page.locator(".issue-marker.is-active")).toHaveCount(3);
  await expect(page.locator(".hero [role=status]")).toContainText(
    "3 issues selected",
  );
  await expect(page.locator(".preloader")).not.toBeVisible();
  await login(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.getByRole("button", { name: "Open workspace navigation" }).click();
  const dialog = page.getByRole("dialog", { name: "Workspace navigation" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Sign out", exact: true }).focus();
  await page.keyboard.press("Tab");
  await expect(
    dialog.getByRole("button", { name: "Close workspace navigation" }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(
    page.getByRole("button", { name: "Open workspace navigation" }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Open workspace navigation" }).click();
  await dialog.getByRole("link", { name: "Runbooks", exact: false }).click();
  await expect(page).toHaveURL(/\/app\/runbooks$/);
  await expect(dialog).not.toBeVisible();
});

test("onboarding persists a real service and denied connector verification stays an error", async ({
  page,
}) => {
  await login(page);
  await page.goto("/onboarding");
  await expect(page.getByLabel("Application name")).toHaveValue("");
  await page.getByLabel("Application name").fill("phase8-browser-service");
  await page
    .getByLabel("Environment", { exact: true })
    .selectOption("development");
  const created = page.waitForResponse(
    (r) =>
      r.url() === `${api}/api/v1/services` && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Register application →" }).click();
  expect((await created).status()).toBe(201);
  await page
    .getByLabel("Healthcheck URL")
    .fill("http://169.254.169.254/latest/meta-data/");
  const verification = page.waitForResponse((r) =>
    r.url().endsWith("/verify-connection"),
  );
  await page.getByRole("button", { name: "Test Connector" }).click();
  expect((await verification).status()).toBe(400);
  await expect(page.locator("main").getByRole("alert")).toContainText(
    /metadata services is prohibited/i,
  );
  const services = await page.request.get(`${api}/api/v1/services`);
  expect(
    (await services.json()).some(
      (s: { name: string }) => s.name === "phase8-browser-service",
    ),
  ).toBe(true);
  await page.goto("/app");
  await expect(
    page.getByRole("link", { name: "phase8-browser-service", exact: true }),
  ).toBeVisible();
});

test("incident lifecycle persists after refresh", async ({ page }) => {
  await login(page);
  await page.goto(`/app/incidents/${incidentId}`);
  const mutation = page.waitForResponse(
    (r) =>
      r.url().includes(`/incidents/${incidentId}`) &&
      r.request().method() === "PATCH",
  );
  await page.getByRole("button", { name: "Acknowledge", exact: true }).click();
  expect((await mutation).status()).toBe(200);
  await page.reload();
  const detail = await page.request.get(
    `${api}/api/v1/incidents/${incidentId}`,
  );
  expect((await detail.json()).status).toBe("acknowledged");
  await expect(
    page.getByText("acknowledged", { exact: true }).first(),
  ).toBeVisible();
});

test("explicit mock: evidence navigation resolves only records in the authorized run scope", async ({
  page,
}, testInfo) => {
  await login(page);
  const runId = "11111111-1111-4111-8111-111111111111",
    now = new Date().toISOString();
  const run = {
    id: runId,
    incident_id: incidentId,
    organization_id: orgId,
    service_id: serviceId,
    status: "INCONCLUSIVE",
    execution_mode: "offline",
    model: "explicit-browser-test-double",
    prompt_version: "test",
    summary: "Test fixture: insufficient evidence",
    missing_evidence: ["A second observation"],
    limitations: ["Explicit mocked browser data"],
    suggested_actions: [],
    tool_call_count: 0,
    error_message: null,
    started_at: now,
    completed_at: now,
    created_at: now,
    updated_at: now,
  };
  const evidence = {
    id: "record-1",
    evidence_id: "ev_test_1",
    run_id: runId,
    organization_id: orgId,
    service_id: serviceId,
    source: "logs",
    observed_at: now,
    locator: "explicit-test-fixture",
    redacted_snippet: "Test fixture redacted snippet",
    content_hash: "test-hash",
    query_metadata: {},
    created_at: now,
  };
  await page.route(
    `${api}/api/v1/incidents/${incidentId}/investigations`,
    (route) => route.fulfill({ json: [run] }),
  );
  await page.route(`${api}/api/v1/investigations/${runId}`, (route) =>
    route.fulfill({
      json: {
        ...run,
        evidence_items: [
          evidence,
          {
            ...evidence,
            id: "foreign",
            evidence_id: "ev_foreign",
            organization_id: "another-org",
            redacted_snippet: "FOREIGN MUST NOT DISPLAY",
          },
        ],
        hypotheses: [
          {
            id: "h1",
            run_id: runId,
            cause: "Test hypothesis",
            confidence: "low",
            supporting_evidence: [
              { evidence_id: "ev_test_1", supports: "Test support" },
              { evidence_id: "ev_foreign", supports: "Invalid scope" },
            ],
            contradicting_evidence_ids: ["ev_missing"],
            next_check: "Collect evidence",
            created_at: now,
          },
        ],
      },
    }),
  );
  await page.route(`${api}/api/v1/investigations/${runId}/events`, (route) =>
    route.fulfill({ json: [] }),
  );
  await page.goto(`/app/incidents/${incidentId}`);
  await expect(page.getByText("MODE: OFFLINE (TEST DOUBLE)")).toBeVisible();
  await expect(page.getByText("Unresolved citation: ev_foreign")).toBeVisible();
  await expect(page.getByText("Unresolved citation: ev_missing")).toBeVisible();
  await page.getByRole("button", { name: "ev_test_1 ↗" }).click();
  await expect(page.locator(".evidence-explorer")).toBeFocused();
  await expect(page.getByRole("tabpanel")).toContainText(
    "Test fixture redacted snippet",
  );
  await expect(page.getByText("FOREIGN MUST NOT DISPLAY")).toHaveCount(0);
  const evidenceAudit = await new AxeBuilder({ page }).analyze();
  expect(
    evidenceAudit.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious",
    ),
  ).toEqual([]);
  for (const width of [375, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.locator(".evidence-explorer").scrollIntoViewIfNeeded();
    await page.screenshot({
      path: testInfo.outputPath(`explicit-mock-evidence-${width}.png`),
      animations: "disabled",
    });
  }

  await page.reload();
  await expect(page.locator("#investigation-status-badge")).toHaveAttribute(
    "data-run-id",
    runId,
  );
});

test("real proposal review, staging execution and independent recovery survive redesign", async ({
  page,
}) => {
  await login(page);
  const headers = await csrf(page);
  const create = async (reason: string) => {
    const response = await page.request.post(
      `${api}/api/v1/actions/proposals`,
      {
        headers,
        data: {
          service_id: serviceId,
          environment: "staging",
          action_catalog_id: "restart_demo_service",
          immutable_parameters: { service_name: "shop-api", reason },
          reason,
          expected_outcome: "Reset controlled staging fault",
          known_risks: "Staging fixture only",
          idempotency_key: crypto.randomUUID(),
        },
      },
    );
    expect(response.status()).toBe(201);
    return response.json();
  };
  const proposal = await create("Phase 8 approved browser check");
  await page.goto("/app/proposals");
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "Review remediation proposal",
  });
  await expect(dialog).toContainText(proposal.parameters_hash);
  for (const width of [375, 768]) {
    await page.setViewportSize({ width, height: 812 });
    expect(
      await dialog.evaluate((node) => node.scrollWidth <= node.clientWidth),
    ).toBe(true);
    const bounds = await dialog.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
  }
  await dialog.getByRole("button", { name: "Authorize Approval" }).focus();
  await page.keyboard.press("Tab");
  await expect(dialog.getByLabel("Review Comment (Optional):")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve", exact: true }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await page.setViewportSize({ width: 1440, height: 900 });
  const modalAudit = await new AxeBuilder({ page }).analyze();
  expect(
    modalAudit.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious",
    ),
  ).toEqual([]);
  await expect(dialog).toContainText('"service_name": "shop-api"');
  const approve = page.waitForResponse((r) =>
    r.url().endsWith(`/proposals/${proposal.id}/approve`),
  );
  await dialog.getByRole("button", { name: "Authorize Approval" }).click();
  expect((await approve).status()).toBe(200);
  await expect(dialog).not.toBeVisible();
  const rejected = await create("Phase 8 rejected browser check");
  await page.reload();
  await page.getByRole("button", { name: "Reject", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Confirm Rejection" })
    .click();
  await expect(
    page.getByText(`Proposal ${rejected.id.slice(0, 8)} rejected.`, {
      exact: true,
    }),
  ).toBeVisible();
  await page.goto("/app/simulation-lab");
  await expect(
    page.getByRole("button", { name: "Activate Scenario", exact: true }),
  ).toHaveCount(6);
  const activate = page.waitForResponse(
    (r) => r.request().method() === "POST" && r.url().includes("/simulation/"),
  );
  await page
    .getByRole("button", { name: "Activate Scenario", exact: true })
    .first()
    .click();
  expect((await activate).status()).toBe(201);
  const execute = page.waitForResponse((r) =>
    r.url().endsWith(`/proposals/${proposal.id}/execute`),
  );
  await page
    .getByRole("button", { name: "Execute Remediation", exact: true })
    .click();
  expect((await execute).status()).toBe(200);
  await page.reload();
  await expect(
    page.getByText("Execution Succeeded", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Execution ID:/).first()).toBeVisible();
  const runs = await page.request.get(`${api}/api/v1/simulation/runs`);
  const active = (await runs.json()).items.find(
    (r: { status: string }) => r.status === "ACTIVE",
  );
  expect(active).toBeTruthy();
  const recovery = page.waitForResponse((r) =>
    r.url().endsWith(`/runs/${active.id}/verify-recovery`),
  );
  await page.getByRole("button", { name: /Verify Recovery/i }).click();
  expect((await recovery).status()).toBe(200);
  await expect(page.getByRole("status")).toContainText("recovery VERIFIED");
  // Reset the disposable run through the same authenticated API after checking the UI's recovery operation.
  const reset = await page.request.post(
    `${api}/api/v1/simulation/runs/${active.id}/reset`,
    { headers, data: { reason: "Browser test cleanup" } },
  );
  expect(reset.status()).toBe(200);
  const duplicate = await page.request.post(
    `${api}/api/v1/actions/proposals/${proposal.id}/execute`,
    { headers },
  );
  expect(duplicate.status()).toBe(200);
  const execution = await duplicate.json();
  expect(execution.proposal_id).toBe(proposal.id);
});

test("core screens have no serious/critical axe violations, readable text and responsive layouts", async ({
  page,
}, testInfo) => {
  test.setTimeout(90000);
  await login(page);
  const routes = [
    "/",
    "/login",
    "/onboarding",
    "/app",
    "/app/incidents",
    `/app/incidents/${incidentId}`,
    "/app/runbooks",
    "/app/proposals",
    "/app/simulation-lab",
  ];
  for (const route of routes) {
    await page.goto(route);
    await page.locator("main h1").waitFor();
    if (route === "/") {
      await expect(page.locator(".preloader")).not.toBeVisible();
      await page.waitForTimeout(1500);
    }
    await page.evaluate(() => document.fonts.ready);
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect
      .soft(
        result.violations.filter(
          (v) => v.impact === "critical" || v.impact === "serious",
        ),
        `${route}: accessibility`,
      )
      .toEqual([]);
    const small = await page.locator("main").evaluate((main) =>
      Array.from(
        main.querySelectorAll<HTMLElement>(
          location.pathname === "/"
            ? "button, .arrow-link"
            : "p,label,button,th,td,small,.badge",
        ),
      )
        .filter(
          (el) =>
            el.getClientRects().length &&
            parseFloat(getComputedStyle(el).fontSize) < 14,
        )
        .map((el) => el.textContent?.slice(0, 60)),
    );
    expect.soft(small, `${route}: metadata >=14px`).toEqual([]);
  }
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of [
      "/",
      "/app",
      `/app/incidents/${incidentId}`,
      "/app/proposals",
      "/app/simulation-lab",
    ]) {
      await page.goto(route);
      await page.locator("main h1").waitFor();
      if (route === "/app/simulation-lab") {
        await expect(
          page.getByRole("button", { name: "Activate Scenario", exact: true }),
        ).toHaveCount(6);
        await expect(
          page.getByText("Execution Succeeded", { exact: true }),
        ).toBeVisible();
      }
      expect
        .soft(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
          `${route} at ${width}`,
        )
        .toBe(true);
      await page.screenshot({
        path: testInfo.outputPath(
          `${route.replaceAll("/", "_") || "landing"}-${width}-viewport.png`,
        ),
        animations: "disabled",
      });
      await page.screenshot({
        path: testInfo.outputPath(
          `${route.replaceAll("/", "_") || "landing"}-${width}.png`,
        ),
        fullPage: true,
        animations: "disabled",
      });
    }
  }
});

test("mobile sign out invalidates the real session", async ({ page }) => {
  await login(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.getByRole("button", { name: "Open workspace navigation" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Sign out", exact: true })
    .click();
  await expect(page).toHaveURL(/\/login$/);
  const response = await page.request.get(`${api}/api/v1/me`);
  expect(response.status()).toBe(401);
});

test("application tabs preserve service scope, history, favorites and real evidence routes", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("button", { name: "Grid view", exact: true }).click();
  const card = page.locator(`[data-project="${serviceId}"]`);
  await card.getByRole("button", { name: "Pin shop-api", exact: true }).click();
  await page.reload();
  await expect(
    card.getByRole("button", { name: "Unpin shop-api", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await card.getByRole("button", { name: "Actions for shop-api" }).click();
  await page.getByRole("menuitem", { name: "View analytics" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/app/services/${serviceId}\\?view=analytics$`),
  );
  await expect(
    page.getByRole("heading", { name: "No performance data available yet." }),
  ).toBeVisible();
  await page.getByLabel("Performance metric").selectOption("1");
  await expect(page.locator("#chart-title")).toHaveText("Error rate");
  await page.reload();
  await expect(
    page.locator(".ws-project-tabs a[aria-current=page]"),
  ).toHaveText("Analytics");
  await page
    .locator(".ws-project-tabs")
    .getByRole("link", { name: "Incidents", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Application incidents" }),
  ).toContainText("Browser Gate Incident");
  await page
    .locator(".ws-project-tabs")
    .getByRole("link", { name: "Investigations", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "AI Incident Investigator",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .locator(".ws-project-tabs")
    .getByRole("link", { name: "Evidence", exact: true })
    .click();
  await expect(page.locator(".application-context-picker")).toContainText(
    "Evidence",
  );
  await page
    .locator(".ws-project-tabs")
    .getByRole("link", { name: "Activity", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Operational history" }),
  ).toBeVisible();
  await page.goBack();
  await expect(
    page.locator(".ws-project-tabs a[aria-current=page]"),
  ).toHaveText("Evidence");
  await page
    .getByRole("link", { name: "← All applications", exact: true })
    .click();
  await expect(page).toHaveURL(/\/app$/);
});

test("empty organization registers its first application and cannot read another organization's service", async ({
  page,
}) => {
  const registration = await page.request.post(`${api}/api/v1/auth/register`, {
    data: {
      email: `workspace-${Date.now()}@example.test`,
      password: process.env.BROWSER_TEST_PASSWORD!,
      name: "Workspace journey QA",
    },
  });
  expect(registration.status()).toBe(201);
  await page.goto("/app");
  await expect(
    page.getByRole("heading", { name: "No applications connected yet." }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Connect Your First Application" })
    .click();
  const input = page.getByLabel("Application name");
  await expect(input).toBeInViewport();
  await input.fill("Exact Application Name · QA");
  await page
    .getByLabel("Environment", { exact: true })
    .selectOption("development");
  await page
    .getByLabel("Description")
    .fill("Synthetic browser QA registration, not production telemetry.");
  const response = page.waitForResponse(
    (r) =>
      r.url() === `${api}/api/v1/services` && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Register application →" }).click();
  const created = await response;
  expect(created.status()).toBe(201);
  const service = await created.json();
  await page.getByRole("link", { name: "View applications →" }).click();
  const card = page.locator(`[data-project="${service.id}"]`);
  await expect(card).toContainText("Exact Application Name · QA");
  await card.locator(".ws-card-link").click();
  await expect(page).toHaveURL(new RegExp(`/app/services/${service.id}$`));
  await page
    .locator(".ws-project-tabs")
    .getByRole("link", { name: "Incidents", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "No incidents recorded." }),
  ).toBeVisible();
  await expect(
    page.getByText("Browser Gate Incident", { exact: true }),
  ).toHaveCount(0);
  expect(
    (
      await page.request.get(`${api}/api/v1/incidents?service_id=${serviceId}`)
    ).status(),
  ).toBe(404);
  await page.goto(`/app/services/${serviceId}`);
  await expect(
    page.getByRole("heading", { name: "shop-api", exact: true }),
  ).toHaveCount(0);
});
