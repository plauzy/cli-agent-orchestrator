import { expect, test } from "@playwright/test";

/**
 * LIVE-path screen recording for the AG-UI dashboard.
 *
 * Unlike generative-ui.spec.ts (which plays the deterministic replay artifact),
 * this drives the *real* stack end-to-end:
 *
 *   real cao-server (CAO_AGUI_ENABLED, spawned by playwright.live.config.ts's
 *   webServer)  ──SSE──▶  the real cao_pwa dashboard (vite preview)
 *
 * The test adds the live CAO instance in the PWA, POSTs the six allow-listed
 * generative-UI components through the real `POST /agui/v1/emit_ui` producer
 * (so they traverse services/agui_stream.to_agui_event and arrive as
 * GENERATIVE_UI frames on the live SSE stream), asserts each card renders,
 * asserts the off-list `iframe` component is refused (HTTP 400, never rendered),
 * and exercises the client's reconnect path (a page reload re-establishes the
 * live stream). Video is "on" in the config → a real .webm of the live
 * path, uploaded by the workflow.
 *
 * This is the fork's "demos must drive the live path" rule applied to the
 * dashboard. It requires a real cao-server + chromium, so it runs in CI (and
 * any environment with both); it is a no-op-skip if the server env var is
 * absent.
 */

const CAO_URL = process.env.CAO_LIVE_URL ?? "http://localhost:9899";

const COMPONENTS: Array<{ component: string; props: Record<string, unknown>; assert: RegExp }> = [
  {
    component: "approval_card",
    props: { title: "Deploy to prod?", detail: "3 files, 1 migration", risk: "high" },
    assert: /Deploy to prod\?/,
  },
  {
    component: "choice_prompt",
    props: {
      question: "Pick a base branch",
      choices: [
        { label: "main", value: "main" },
        { label: "release", value: "release" },
      ],
    },
    assert: /Pick a base branch/,
  },
  {
    component: "diff_summary",
    props: { title: "PR #387 reshape", files: [{ path: "a2a/rpc.py", additions: 74, deletions: 3 }] },
    assert: /a2a\/rpc\.py/,
  },
  { component: "progress", props: { label: "Indexing repo", value: 0.42 }, assert: /Indexing repo/ },
  { component: "metric", props: { label: "tokens", value: 12840, unit: "tok" }, assert: /tokens/ },
  {
    component: "agent_card",
    props: { name: "worker-1", provider: "kiro_cli", status: "working" },
    assert: /worker-1/,
  },
];

test("live AG-UI dashboard renders emitted components and refuses off-list ones", async ({
  page,
  request,
}) => {
  // 1. Open the dashboard and register the live CAO instance.
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "CAO Dashboard" })).toBeVisible();

  await page.getByRole("button", { name: /Add CAO instance/i }).click();
  const urlInput = page.locator('input[type="url"]');
  await urlInput.fill(CAO_URL);
  await page.getByRole("button", { name: /^Add$/ }).click();

  // 2. The instance tab connects to the live SSE stream.
  await expect(page.locator(".cao-pwa-status.open")).toBeVisible({ timeout: 20_000 });

  // 3. Drive the six allow-listed components through the real producer.
  for (const { component, props } of COMPONENTS) {
    const resp = await request.post(`${CAO_URL}/agui/v1/emit_ui`, {
      data: { component, props },
    });
    expect(resp.status(), `emit ${component}`).toBe(200);
  }

  // 4. Each authored card renders on the live surface.
  for (const { assert } of COMPONENTS) {
    await expect(page.getByText(assert).first()).toBeVisible({ timeout: 20_000 });
  }
  // The generative panel shows all six.
  await expect(page.locator(".cao-pwa-generative .gen-ui")).toHaveCount(6, { timeout: 20_000 });

  // 5. Safety: an off-list component is refused server-side (400) and never rendered.
  const refused = await request.post(`${CAO_URL}/agui/v1/emit_ui`, {
    data: { component: "iframe", props: { src: "https://evil.example" } },
  });
  expect(refused.status()).toBe(400);
  await page.waitForTimeout(500);
  expect(await page.locator("iframe").count()).toBe(0);
  await expect(page.locator(".cao-pwa-generative .gen-ui")).toHaveCount(6);

  // Headline screenshot of the composed live surface.
  await page.screenshot({ path: "e2e/__screenshots__/live-dashboard-final.png", fullPage: true });

  // 6. Resilience / reconnect: a full page reload tears down the EventSource;
  //    the persisted instance (IndexedDB) auto-activates on load and the tab
  //    re-establishes the live stream, returning to "connected". (In-session
  //    drops additionally resume via ?since= — api.ts tracks the last event
  //    timestamp; the server-side ?since= replay is covered by the Python
  //    endpoint tests test_stream_since_*.)
  await page.reload();
  await expect(page.locator(".cao-pwa-status.open")).toBeVisible({ timeout: 30_000 });
});
