import { defineConfig } from "@playwright/test";

// LIVE recording harness: drives the real cao-server + real PWA (not the canned
// replay). Two web servers are started for the run:
//   1. a real cao-server with the AG-UI surface enabled (Python; started from
//      the repo root via uv), health-gated on /health;
//   2. the built PWA served by `vite preview`.
// The live spec then registers the cao-server instance in the PWA and drives
// emit_ui through it. Requires chromium + a working Python/uv env, so it runs in
// CI (see .github/workflows/cao-pwa-generative-ui.yml, job: live-dashboard).
//
// Kept as a separate config so the default `test:e2e` (deterministic replay,
// no server needed) is unaffected.

const CAO_PORT = process.env.CAO_LIVE_PORT ?? "9899";
const PWA_PORT = process.env.PWA_PREVIEW_PORT ?? "4173";

export default defineConfig({
  testDir: "./e2e",
  testMatch: /live-dashboard\.spec\.ts/,
  outputDir: "./test-results-live",
  timeout: 90_000,
  use: {
    baseURL: `http://localhost:${PWA_PORT}`,
    video: "on",
    screenshot: "on",
    trace: "on-first-retry",
    viewport: { width: 1200, height: 820 },
    colorScheme: "dark",
  },
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report-live" }]],
  webServer: [
    {
      // Real cao-server from the repo root, AG-UI enabled, on an isolated port.
      command: `bash -c 'cd .. && CAO_AGUI_ENABLED=1 CAO_API_PORT=${CAO_PORT} uv run cao-server'`,
      url: `http://localhost:${CAO_PORT}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      // Built PWA served statically.
      command: `npm run preview -- --port ${PWA_PORT} --strictPort`,
      url: `http://localhost:${PWA_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
