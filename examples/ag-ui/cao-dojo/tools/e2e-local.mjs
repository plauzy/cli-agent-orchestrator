#!/usr/bin/env node
// Local-only end-to-end check of the CAO Dojo page against a real cao-server
// and a real Claude Code agent. Run it through e2e-local.sh, which brings the
// server, the page and the agent up and tears them down. Not wired into CI: it
// needs a logged-in coding CLI on this machine.
//
//   node e2e-local.mjs approve   card appears; Approve writes approved-by-dojo.txt
//   node e2e-local.mjs reject    card appears; Reject leaves no file
//   node e2e-local.mjs none      nothing pending: the run still finishes, no
//                                pending card; an unknown interrupt is RUN_ERROR
//
// Environment (e2e-local.sh sets these):
//   PAGE_URL        the served index.html
//   CAO_URL         the cao-server under test
//   E2E_WORKDIR     the agent's work dir (approve/reject check the file there)
//   E2E_INTERRUPT_ID  the open interrupt's id (approve/reject): its card must
//                   arrive over the stream before the page posts any run
//   E2E_VIDEO_DIR   opt-in: record a video of the page into this dir
//   E2E_CAPTION     opt-in: caption drawn on the page, e.g. the CAO build
//   E2E_SHOT_DIR    opt-in: save screenshots of each step into this dir
//   E2E_HOLD_MS     opt-in: pause this long on the card and on the result, so a
//                   recording is watchable
import { existsSync, mkdirSync, readFileSync, renameSync } from "node:fs";
import { join } from "node:path";

let chromium;
try {
  ({ chromium } = await import("@playwright/test"));
} catch {
  console.error(
    "e2e-local: Playwright is not installed. Run:\n" +
      "  (cd examples/ag-ui/cao-dojo/tools && npm install && npx playwright install chromium)",
  );
  process.exit(2);
}

const phase = process.argv[2];
if (!["approve", "reject", "none"].includes(phase)) {
  console.error("usage: node e2e-local.mjs <approve|reject|none>");
  process.exit(2);
}
const PAGE_URL = process.env.PAGE_URL;
const CAO_URL = process.env.CAO_URL;
if (!PAGE_URL || !CAO_URL) {
  console.error(
    "e2e-local: PAGE_URL and CAO_URL must be set (use e2e-local.sh)",
  );
  process.exit(2);
}
const FILE = "approved-by-dojo.txt";
const LINE = "written after approval";
const SETTLE_MS = 15_000;

const t0 = Date.now();
const at = () => `${((Date.now() - t0) / 1000).toFixed(1)}s`;
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "PASS" : "FAIL"} ${phase}: ${what}`);
  if (!ok) failures.push(what);
  return ok;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const hold = () => sleep(Number(process.env.E2E_HOLD_MS ?? 0));

const browser = await chromium.launch();
const videoDir = process.env.E2E_VIDEO_DIR;
const context = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  ...(videoDir
    ? { recordVideo: { dir: videoDir, size: { width: 1280, height: 800 } } }
    : {}),
});
const caption = process.env.E2E_CAPTION;
if (caption) {
  await context.addInitScript((t) => {
    const draw = () => {
      if (document.getElementById("e2e-caption")) return;
      const el = document.createElement("div");
      el.id = "e2e-caption";
      el.textContent = t;
      el.style.cssText =
        "position:fixed;left:0;right:0;bottom:0;z-index:99999;padding:6px 12px;" +
        "font:14px/1.4 monospace;background:#111;color:#fff;pointer-events:none";
      document.body.appendChild(el);
    };
    if (document.body) draw();
    else document.addEventListener("DOMContentLoaded", draw);
  }, `${caption} | ${phase}`);
}
const page = await context.newPage();

const shotDir = process.env.E2E_SHOT_DIR;
if (shotDir) mkdirSync(shotDir, { recursive: true });
async function shot(name) {
  if (!shotDir) return;
  await page
    .screenshot({ path: join(shotDir, `${phase}-${name}.png`) })
    .catch((e) =>
      console.log(`screenshot ${name} failed: ${e.message.split("\n")[0]}`),
    );
}

// Every POST /agui/v1/run the page makes, with how its stream ended.
const runs = [];
page.on("request", (r) => {
  if (r.method() === "POST" && r.url().endsWith("/agui/v1/run")) {
    r._run = {
      start: Date.now(),
      end: null,
      terminal: null,
      outcome: null,
      resume: false,
    };
    r._run.resume = (r.postData() ?? "").includes('"interruptId"');
    runs.push(r._run);
  }
});
page.on("requestfinished", async (r) => {
  if (!r._run) return;
  const body = (await (await r.response())?.text().catch(() => "")) ?? "";
  r._run.terminal = body.includes('"type":"RUN_ERROR"')
    ? "RUN_ERROR"
    : body.includes('"type":"RUN_FINISHED"')
      ? "RUN_FINISHED"
      : null;
  r._run.outcome = body.match(/"outcome":\{"type":"(\w+)"/)?.[1] ?? null;
  r._run.body = body;
  r._run.end = Date.now();
});
page.on("requestfailed", (r) => {
  if (r._run) r._run.end = Date.now();
});

async function agentStatus() {
  const res = await fetch(`${CAO_URL}/sessions/cao-dojo-demo/terminals`);
  const [terminal] = await res.json();
  return (await (await fetch(`${CAO_URL}/terminals/${terminal.id}`)).json())
    .status;
}

async function runsSettled() {
  const deadline = Date.now() + SETTLE_MS;
  while (Date.now() < deadline) {
    if (runs.length > 0 && runs.every((r) => r.end)) return true;
    await sleep(250);
  }
  return false;
}

const pending = page.locator(
  '[data-testid="approval-card"][data-state="pending"]',
);
const results = page.getByTestId("run-result");

try {
  await page.goto(PAGE_URL);
  await page.locator("#endpoint").fill(CAO_URL);
  await page.locator("#connect").click();
  await page.locator("#status.connected").waitFor({ timeout: SETTLE_MS });

  const prompt = page.locator("#prompt");
  const send = page.locator("#send");

  if (phase === "none") {
    await prompt.fill("Is anything waiting for my approval?");
    await send.click();
    check(await runsSettled(), `the run ended within ${SETTLE_MS / 1000}s`);
    check(
      runs.length === 1 &&
        runs[0].terminal === "RUN_FINISHED" &&
        runs[0].outcome === "success",
      "RUN_FINISHED with a success outcome",
    );
    await results.first().waitFor({ timeout: SETTLE_MS });
    check(
      (await results.first().getAttribute("data-terminal")) === "RUN_FINISHED",
      "the page shows RUN_FINISHED",
    );
    check((await pending.count()) === 0, "no pending approval card");
    await shot("2-settled");
    await hold();

    // FR-11: an unknown interrupt must surface as RUN_ERROR, not a hang.
    await page.evaluate(() =>
      window.__caoDojo.resume("00000000-0000-0000-0000-000000000000", {
        approved: true,
      }),
    );
    check(await runsSettled(), "the unknown-interrupt run ended");
    check(
      runs[1]?.terminal === "RUN_ERROR",
      "an unknown interrupt yields RUN_ERROR",
    );
    await page
      .locator('[data-testid="run-result"][data-terminal="RUN_ERROR"]')
      .first()
      .waitFor({ timeout: SETTLE_MS })
      .then(
        () => check(true, "the page shows RUN_ERROR"),
        () => check(false, "the page shows RUN_ERROR"),
      );
    await shot("3-run-error");
    await hold();
  } else {
    // FR-11.1: the card must come from the stream's GENERATIVE_UI frame, so
    // wait for this interrupt's card before the page posts any run. Earlier
    // phases' cards replay too, hence matching on the id e2e-local.sh probed.
    const id = process.env.E2E_INTERRUPT_ID;
    if (!check(Boolean(id), "E2E_INTERRUPT_ID is set"))
      throw new Error("no id");
    const card = page.locator(
      `[data-testid="approval-card"][data-interrupt-id="${id}"]`,
    );
    const streamed = await card
      .and(pending)
      .waitFor({ timeout: SETTLE_MS })
      .then(
        () => true,
        () => false,
      );
    if (!check(streamed, "the approval card arrived over the stream"))
      throw new Error("no card");
    check(runs.length === 0, "before the page posted any run");

    // Then the run plane reports the same interrupt and the page settles any
    // replayed cards, leaving this one as the only pending card.
    await prompt.fill("Is anything waiting for my approval?");
    await send.click();
    check(
      await runsSettled(),
      `the collecting run ended within ${SETTLE_MS / 1000}s`,
    );
    check(
      runs[0]?.terminal === "RUN_FINISHED" && runs[0]?.outcome === "interrupt",
      "RUN_FINISHED with an interrupt outcome",
    );
    check(
      Boolean(runs[0]?.body.includes(`"id":"${id}"`)),
      "the run lists the same interrupt",
    );
    check(
      (await pending.count()) === 1 && (await card.and(pending).count()) === 1,
      "exactly one pending card, for that interrupt",
    );
    console.log(`${at()} card: ${JSON.stringify(await card.innerText())}`);
    check(
      (await card.getByTestId("approval-reason").innerText()).includes(
        "claude-code:permission_request",
      ),
      "the card shows the reason",
    );
    await shot("1-card");
    await hold();

    const decideAt = runs.length;
    await card
      .getByTestId(phase === "approve" ? "approval-approve" : "approval-reject")
      .click();
    check(
      await runsSettled(),
      `the resumed run ended within ${SETTLE_MS / 1000}s`,
    );
    const resumed = runs[decideAt];
    check(
      resumed?.resume === true,
      "the decision was posted as a resume[] run",
    );
    check(
      resumed?.terminal === "RUN_FINISHED" && resumed?.outcome === "success",
      "the resumed run finished with a success outcome",
    );
    const decided = phase === "approve" ? "approved" : "rejected";
    check(
      await page
        .locator(
          `[data-testid="approval-card"][data-interrupt-id="${id}"][data-state="${decided}"]`,
        )
        .waitFor({ timeout: 5_000 })
        .then(
          () => true,
          () => false,
        ),
      `the card shows ${decided}`,
    );

    const workdir = process.env.E2E_WORKDIR;
    if (check(Boolean(workdir), "E2E_WORKDIR is set")) {
      const file = join(workdir, FILE);
      if (phase === "approve") {
        let found = false;
        for (let i = 0; i < 120 && !found; i++) {
          found =
            existsSync(file) && readFileSync(file, "utf8").trim() === LINE;
          if (!found) await sleep(500);
        }
        check(found, `${FILE} exists and contains "${LINE}"`);
      } else {
        // Wait for the agent to finish its turn before checking nothing was written.
        let done = false;
        for (let i = 0; i < 120 && !done; i++) {
          done = ["completed", "idle"].includes(
            await agentStatus().catch(() => ""),
          );
          if (!done) await sleep(500);
        }
        check(done, "the agent finished its turn");
        check(!existsSync(file), `${FILE} was not created`);
      }
    }
    await shot("2-settled");
    await hold();
  }
} catch (error) {
  if (!failures.length)
    check(false, `driver error: ${error.message.split("\n")[0]}`);
} finally {
  if (failures.length) await shot("9-failed");
  console.log(
    `${at()} runs: ` +
      JSON.stringify(
        runs.map((r) => ({
          ms: r.end ? r.end - r.start : null,
          terminal: r.terminal,
          outcome: r.outcome,
          resume: r.resume,
        })),
      ),
  );
  const video = page.video();
  await context.close().catch(() => {});
  if (video) {
    await video
      .path()
      .then((p) => renameSync(p, join(videoDir, `${phase}.webm`)))
      .catch(() => {});
  }
  await browser.close().catch(() => {});
}

console.log(
  failures.length ? `FAIL ${phase} (${failures.length})` : `PASS ${phase}`,
);
process.exit(failures.length ? 1 : 0);
