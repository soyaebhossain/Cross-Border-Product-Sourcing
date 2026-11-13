import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.PLAYWRIGHT_PORT || 3100);
const baseURL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${port}`;
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
// CI tests the production build (`npm run build` first). The development server
// compiles pages on demand, and on a slow runner a page can be requested while
// its manifest is half written, which fails with "Unexpected end of JSON input".
const useBuiltServer = process.env.PLAYWRIGHT_USE_BUILD === "1";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["line"], ["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    launchOptions: executablePath ? { executablePath } : undefined,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    locale: "en-BD",
    timezoneId: "Asia/Dhaka",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-chromium",
      grep: /@public/,
      use: { ...devices["Pixel 7"] },
    },
  ],
  webServer: process.env.PLAYWRIGHT_BASE_URL ? undefined : {
    command: useBuiltServer ? `npm run start -- --port ${port}` : `npm run dev -- --port ${port}`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      API_BASE_URL: process.env.API_BASE_URL || "http://127.0.0.1:8001",
      NEXT_PUBLIC_CATALOG_SNAPSHOT_FALLBACK:
        process.env.NEXT_PUBLIC_CATALOG_SNAPSHOT_FALLBACK || "1",
    },
  },
});
