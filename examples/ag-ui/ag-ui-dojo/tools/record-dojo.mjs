#!/usr/bin/env node
// ABOUTME: Gated shift-left recorder for the CAO AG-UI Dojo — asserts the dojo renders
// ABOUTME: every component + panel + the off-list refusal BEFORE it exports any media.
//
// This is BUILD/CI tooling (not shipped). It loads the assembled static dojo
// (docusaurus/static/dojo/index.html), lets it replay the committed fixtures,
// and ASSERTS the contract: all six allow-listed generative components render,
// the four L2 panels render, and the off-list component becomes an INERT
// placeholder (never an iframe/script). Only if every assertion passes does it
// record Chromium and export an optimized GIF to docs/media/.
//
// THE GATE (shift-left): a broken dojo — a missing panel, an un-rendered
// component, or an off-list component that rendered — makes this exit non-zero
// and fails CI. No green recording without a correct dojo.
//
// Deterministic + credentials-free: renders from committed fixtures, no server.
//
// Usage:  npm ci && npm run playwright:install && npm run record

import { spawn } from "node:child_process";
import { mkdirSync, readdirSync, renameSync, rmSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";
import ffmpegStatic from "ffmpeg-static";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO = process.env.CAO_REPO || resolve(__dirname, "..", "..", "..", "..");
const DOJO_HTML = resolve(REPO, "docusaurus/static/dojo/index.html");
const OUT_DIR = resolve(REPO, "docs/media");
const TMP_DIR = resolve(__dirname, ".demo-tmp");
const FFMPEG_BIN = process.env.FFMPEG_BIN || ffmpegStatic || "ffmpeg";
const VIEWPORT = { width: 1100, height: 720 };

const EXPECTED_COMPONENTS = [
  "agent_card",
  "progress",
  "diff_summary",
  "metric",
  "choice_prompt",
  "approval_card",
];
const EXPECTED_PANELS = ["dashboard", "timeline", "generative", "frames"];
const OFFLIST = ["iframe", "script"];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function run(bin, args) {
  return new Promise((res, rej) => {
    const p = spawn(bin, args, { stdio: "inherit" });
    p.on("exit", (code) => (code === 0 ? res() : rej(new Error(`${bin} exited ${code}`))));
    p.on("error", rej);
  });
}

async function main() {
  if (!existsSync(DOJO_HTML)) {
    throw new Error(
      `dojo not built: ${DOJO_HTML} missing. Run \`npm run build-dojo\` in docusaurus/ first.`
    );
  }
  rmSync(TMP_DIR, { recursive: true, force: true });
  mkdirSync(TMP_DIR, { recursive: true });
  mkdirSync(OUT_DIR, { recursive: true });

  const videoDir = resolve(TMP_DIR, "ag-ui-dojo");
  mkdirSync(videoDir, { recursive: true });

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    recordVideo: { dir: videoDir, size: VIEWPORT },
  });
  const page = await context.newPage();
  await page.goto(`file://${DOJO_HTML}`, { waitUntil: "networkidle" });

  // The dojo signals readiness once it has replayed the fixtures.
  await page.waitForSelector('[data-dojo-ready="true"]', { timeout: 15000 });
  await sleep(600);

  // ---- THE GATE: assert the contract before exporting anything ----
  const problems = [];

  for (const panel of EXPECTED_PANELS) {
    const n = await page.locator(`[data-dojo-panel="${panel}"]`).count();
    if (n < 1) problems.push(`missing panel: ${panel}`);
  }
  for (const c of EXPECTED_COMPONENTS) {
    const n = await page.locator(`[data-dojo-component="${c}"]`).count();
    if (n < 1) problems.push(`generative component not rendered: ${c}`);
  }
  // Off-list MUST be refused (inert placeholder), and MUST NOT have created a
  // real iframe/script node.
  const refused = await page.locator('[data-dojo-offlist-refused="true"]').count();
  if (refused < 1) problems.push("off-list component was not refused (no inert placeholder)");
  for (const tag of OFFLIST) {
    const leaked = await page.locator(`[data-dojo-panel="generative"] ${tag}`).count();
    if (leaked > 0) problems.push(`off-list <${tag}> leaked into the DOM (safety breach)`);
  }
  // Privacy: no leaked message bodies in the rendered timeline.
  const bodyLeak = await page.locator("text=body excluded").count();
  if (bodyLeak > 0) problems.push("message body text leaked into the rendered dojo (privacy breach)");

  if (problems.length) {
    await context.close();
    await browser.close();
    throw new Error("dojo contract failed (shift-left gate):\n  - " + problems.join("\n  - "));
  }
  console.log("[record-dojo] contract OK: 4 panels, 6 components, off-list refused, privacy held.");

  await sleep(1500); // hold a clean final frame
  await context.close(); // finalizes the .webm
  await browser.close();

  // ---- export the GIF (only reached if the gate passed) ----
  const webm = readdirSync(videoDir).find((f) => f.endsWith(".webm"));
  if (!webm) throw new Error("no video captured");
  const outWebm = resolve(videoDir, "ag-ui-dojo-demo.webm");
  renameSync(resolve(videoDir, webm), outWebm);

  const outGif = resolve(OUT_DIR, "ag-ui-dojo-demo.gif");
  const palette = resolve(TMP_DIR, "ag-ui-dojo-palette.png");
  const vf = "fps=8,scale=880:-1:flags=lanczos";
  await run(FFMPEG_BIN, ["-y", "-i", outWebm, "-vf", `${vf},palettegen`, palette]);
  await run(FFMPEG_BIN, ["-y", "-i", outWebm, "-i", palette, "-lavfi", `${vf} [x]; [x][1:v] paletteuse`, outGif]);

  rmSync(TMP_DIR, { recursive: true, force: true });
  console.log(`[record-dojo] PASS: wrote ${outGif}`);
}

main().catch((e) => {
  console.error(`[record-dojo] FAIL: ${e.message}`);
  process.exit(1);
});
