import { spawn, type ChildProcess } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { test, expect } from "@playwright/test";

// LIVE-PATH proof for the AG-UI surface — no canned replay anywhere.
//
// Boots a real `cao-server` (CAO_AGUI_ENABLED=true) plus the built PWA
// (`vite preview`), adds the instance through the real add-instance dialog,
// then drives POST /agui/v1/emit_ui through every allow-listed component and
// asserts each card renders from the live SSE stream. Also proves the two
// hardest runtime claims end-to-end:
//
//   * an off-list component is refused server-side (400) and nothing renders,
//   * a dropped connection resumes via ?since= replay with no gap (an event
//     emitted while the page is offline appears after reconnect).
//
// Video is recorded by the shared config (video: "on"); CI uploads it as the
// generative-ui-recording artifact. Requires `npm run build` first (preview
// serves dist/) and `uv` on PATH at the repo root.

const DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(DIR, "../..");
const CAO_PORT = 9899;
const PWA_PORT = 4173;
const CAO_URL = `http://localhost:${CAO_PORT}`;
const PWA_URL = `http://localhost:${PWA_PORT}`;

let caoServer: ChildProcess;
let pwaServer: ChildProcess;

async function waitForHttp(url: string, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastErr: unknown = null;
  while (Date.now() < deadline) {
    try {
      const resp = await fetch(url);
      if (resp.ok) return;
      lastErr = new Error(`HTTP ${resp.status}`);
    } catch (err) {
      lastErr = err;
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`timed out waiting for ${url}: ${String(lastErr)}`);
}

async function emitUI(component: string, props: Record<string, unknown>): Promise<number> {
  const resp = await fetch(`${CAO_URL}/agui/v1/emit_ui`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ component, props }),
  });
  return resp.status;
}

// The venv entry point, NOT `uv run cao-server`: the restart step below kills
// the process, and killing a `uv run` wrapper orphans the actual server child.
const CAO_SERVER_BIN = path.join(REPO_ROOT, ".venv", "bin", "cao-server");

function spawnCaoServer(): ChildProcess {
  return spawn(CAO_SERVER_BIN, ["--port", String(CAO_PORT)], {
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      CAO_AGUI_ENABLED: "true",
      // The PWA is a cross-origin browser client of the CAO API.
      CAO_CORS_ORIGINS: PWA_URL,
    },
    stdio: "inherit",
  });
}

test.beforeAll(async () => {
  caoServer = spawnCaoServer();
  // Same wrapper-free rationale as CAO_SERVER_BIN: killing an `npm run`
  // wrapper orphans the actual vite child, which then squats the port for
  // the next run. Spawn the vite binary directly so afterAll's kill lands
  // on the real server process.
  const viteBin = path.resolve(DIR, "..", "node_modules", ".bin", "vite");
  pwaServer = spawn(
    viteBin,
    ["preview", "--port", String(PWA_PORT), "--strictPort", "--host"],
    { cwd: path.resolve(DIR, ".."), stdio: "inherit" },
  );
  await waitForHttp(`${CAO_URL}/health`, 60_000);
  await waitForHttp(PWA_URL, 60_000);
});

test.afterAll(() => {
  caoServer?.kill("SIGTERM");
  pwaServer?.kill("SIGTERM");
});

test("live dashboard renders real emit_ui traffic, refuses off-list, resumes via ?since=", async ({
  page,
}) => {
  test.setTimeout(180_000);

  // 1. Connect through the real add-instance flow.
  await page.goto(PWA_URL);
  await page.getByRole("button", { name: "Add CAO instance" }).click();
  await page.getByLabel("URL").fill(CAO_URL);
  await page.getByLabel("Label").fill("live");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByText("● connected")).toBeVisible({ timeout: 15_000 });

  // 2. Every allow-listed component, emitted through the real producer
  //    endpoint, renders live off the SSE stream.
  expect(await emitUI("agent_card", { name: "fleet_worker", provider: "mock_cli", status: "working" })).toBe(200);
  // Renderer-true props: progress value is 0.0–1.0 (the renderer clamps to
  // [0,1]) and diff_summary titles via `title` — asserted below so a
  // vocabulary/renderer drift fails this spec instead of hiding behind a 200.
  expect(await emitUI("progress", { label: "Analyzing dataset", value: 0.6 })).toBe(200);
  expect(await emitUI("metric", { label: "Coverage", value: 99, unit: "%" })).toBe(200);
  expect(
    await emitUI("diff_summary", {
      title: "auth hardening",
      files: [{ path: "api/main.py", additions: 18, deletions: 2 }],
    }),
  ).toBe(200);
  expect(await emitUI("choice_prompt", { question: "Pick a deploy target", choices: ["staging", "prod"] })).toBe(200);
  expect(
    await emitUI("approval_card", {
      title: "Approve handoff to prod?",
      detail: "all gates green",
      risk: "high",
    }),
  ).toBe(200);

  await expect(page.getByText("fleet_worker").first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Analyzing dataset")).toBeVisible();
  // The rendered <progress> carries the un-clamped value — pins the 0–1 scale.
  await expect(page.locator(".gen-ui-progress progress")).toHaveAttribute("aria-valuenow", "0.6");
  await expect(page.getByText("Coverage")).toBeVisible();
  // The diff card's heading comes from `title` (not `summary`) — pins the prop name.
  await expect(page.getByRole("heading", { name: "auth hardening" })).toBeVisible();
  await expect(page.getByText("api/main.py")).toBeVisible();
  await expect(page.getByText("Pick a deploy target")).toBeVisible();
  await expect(page.getByText("Approve handoff to prod?")).toBeVisible();
  await expect(page.getByText("Generative UI (6)")).toBeVisible();

  // 3. Safety: an off-list component is refused by the server and never
  //    reaches the page.
  expect(await emitUI("iframe", { src: "https://evil.example" })).toBe(400);
  expect(await page.locator("iframe").count()).toBe(0);
  await expect(page.getByText("Generative UI (6)")).toBeVisible();

  // 4. Resilience: hard-restart the server. The client detects the drop,
  //    backs off, and resumes via ?since= — an event emitted right after the
  //    restart (while the client is still backing off) arrives via replay,
  //    so the dashboard recovers with no gap and no manual reload.
  caoServer.kill("SIGKILL");
  await expect(page.getByText("✗ error")).toBeVisible({ timeout: 30_000 });

  caoServer = spawnCaoServer();
  await waitForHttp(`${CAO_URL}/health`, 60_000);
  expect(await emitUI("metric", { label: "Emitted during outage", value: 1 })).toBe(200);

  await expect(page.getByText("● connected")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Emitted during outage")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Generative UI (7)")).toBeVisible();

  // 5. Persistence: a full page reload tears the client down entirely; the
  //    saved instance (IndexedDB) auto-activates on load and the tab returns
  //    to the live stream with no re-registration. (Complementary to step 4:
  //    that one proves in-session ?since= gap recovery; this proves the
  //    across-session instance persistence path.)
  await page.reload();
  await expect(page.getByText("● connected")).toBeVisible({ timeout: 30_000 });

  await page.screenshot({ path: "e2e/__screenshots__/live-dashboard-final.png", fullPage: true });
});
