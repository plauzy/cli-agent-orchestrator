import { defineConfig } from "@playwright/test";

// LIVE-path harness: runs only e2e/live-dashboard.spec.ts, which self-manages
// its servers (spawns .venv/bin/cao-server and vite preview directly — see the
// spec header for why the wrapper-free spawns matter for the restart step).
// Kept as a separate config so the default `npm run test:e2e` (deterministic
// replay, no Python toolchain needed) stays hermetic; run this one with
// `npm run test:e2e:live`.
export default defineConfig({
  testDir: "./e2e",
  testMatch: /live-dashboard\.spec\.ts/,
  outputDir: "./test-results-live",
  timeout: 180_000,
  use: {
    video: "on",
    screenshot: "on",
    trace: "on-first-retry",
    viewport: { width: 1100, height: 760 },
    colorScheme: "dark",
    // Sandboxes that pre-install a Chromium (and block the Playwright CDN)
    // can point at it instead of the version-pinned download; CI leaves this
    // unset and uses `playwright install`.
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {},
  },
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report-live" }]],
});
