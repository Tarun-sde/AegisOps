import { defineConfig, devices } from "@playwright/test";

const port = process.env.BROWSER_WEB_PORT;
if (
  !port ||
  !process.env.BROWSER_API_URL ||
  !process.env.BROWSER_TEST_PASSWORD
) {
  throw new Error(
    "Run make browser to provision isolated authenticated test dependencies.",
  );
}
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./tests",
  workers: 1,
  use: { baseURL, ...devices["Desktop Chrome"] },
  webServer: {
    command: `npm run start -- --port ${port}`,
    url: `${baseURL}/healthz`,
    reuseExistingServer: false,
    timeout: 120000,
  },
});
