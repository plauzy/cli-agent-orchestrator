import { test, expect } from "@playwright/test";

// Screen-recording proof for the generative-UI feature.
//
// Loads the deterministic replay artifact (frames produced by the real Python
// adapter, services/agui_stream.to_agui_event), plays it, and records video +
// screenshots. Every assertion below maps to an "additive value" claim in
// docs/generative-ui-implementation-2026-07-04.md.
//
// Produces (in CI): test-results/**/video.webm and the screenshots inline in
// the HTML report — the referenced recording.

// ESM-safe path to the replay artifact (this package is "type": "module",
// so __dirname is not defined — derive the file:// URL from import.meta.url).
const REPLAY = new URL("../demo/generative-ui-replay.html", import.meta.url).href;

test("generative UI renders uniformly across heterogeneous providers and refuses off-list components", async ({ page }) => {
  await page.goto(REPLAY);
  await expect(page.getByRole("heading", { name: /Generative UI over heterogeneous CLI agents/i })).toBeVisible();

  // Play the whole captured sequence.
  await page.getByRole("button", { name: /Play/ }).click();

  // Each allow-listed component, authored by a different CLI provider, renders.
  await expect(page.getByText("Which architecture for the cache layer?")).toBeVisible({ timeout: 15_000 }); // kiro_cli
  await expect(page.getByText("Approve handoff of DB migration to reviewer?")).toBeVisible({ timeout: 15_000 }); // claude_code
  await expect(page.getByText("api/main.py")).toBeVisible({ timeout: 15_000 }); // diff_summary
  await expect(page.locator("progress")).toBeVisible({ timeout: 15_000 }); // codex progress
  await expect(page.getByText(/tok\/s/)).toBeVisible({ timeout: 15_000 }); // metric

  // Provider badges prove the "uniform across providers" claim.
  await expect(page.locator(".prov", { hasText: "kiro_cli" }).first()).toBeVisible();
  await expect(page.locator(".prov", { hasText: "claude_code" }).first()).toBeVisible();
  await expect(page.locator(".prov", { hasText: "codex" }).first()).toBeVisible();

  // Safety: the off-list component is REFUSED, never rendered as an iframe.
  await expect(page.getByText(/REFUSED off-list component/i)).toBeVisible({ timeout: 15_000 });
  expect(await page.locator("iframe").count()).toBe(0);

  // Capture the final composed surface as the headline screenshot.
  await page.screenshot({ path: "e2e/__screenshots__/generative-ui-final.png", fullPage: true });
});
