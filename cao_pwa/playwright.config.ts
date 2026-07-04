import { defineConfig } from "@playwright/test";

// Recording harness for the generative-UI proof.
//
// NOTE: in the restricted build sandbox the Playwright browser CDN
// (cdn.playwright.dev) is blocked, so this cannot run there. It runs in CI
// (GitHub Actions) where the CDN is reachable — `npm run test:e2e:install`
// fetches chromium, then `npm run test:e2e` produces the video + screenshots
// under `test-results/` and `e2e/__screenshots__/`. Those artifacts are the
// "screen recording" proof referenced in docs/generative-ui-*.md.
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  timeout: 30_000,
  use: {
    video: "on",
    screenshot: "on",
    trace: "on-first-retry",
    viewport: { width: 1100, height: 760 },
    colorScheme: "dark",
  },
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
});
