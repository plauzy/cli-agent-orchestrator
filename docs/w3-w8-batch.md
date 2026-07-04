# W3–W8 — CAO-orchestrated batch (deferred execution)

> Frozen 2026-05-12. **Execution is deferred to a fresh session.** This document is the pickup record.
>
> **Template instance.** This doc is the first reference instance of the six-section reusable evaluation template in [`docs/TENETS.md`](TENETS.md#3-beforeafter-metrics-on-every-meaningful-change-2026-05-12) §3. Future batches, RFCs, and large changes should follow the same structure.

---

## 1. Why this batch exists

**What outcome are we trying to change?** The WebSocket auth feature shipped in PR #23 left four manual smoke checkboxes unchecked. Today, verifying that the auth contract (`default-off`, `4401`, `cao:read`-only viewer, `cao:read cao:write` operator) still holds requires a human to set up the env, mint tokens, and click through four scenarios on every release — roughly 20 minutes of focused human time, and the kind of work that gets skipped under pressure. Worse: there is currently no automated CI signal that catches a regression in the WS auth contract before it reaches a release.

**What would have to be true** for that to change? (a) An automated test for each of the four scenarios runs on every PR. (b) The test infrastructure runs without authenticating any external provider CLI (otherwise contributors from forks can't reproduce locally and CI can't run on fork PRs). (c) The pattern generalises so the same closure exists for future surfaces (Playwright, MCP iframe, PWA).

**Smallest change?** Ten independent units (W0–W9). W0 ships a `mock_cli` provider so the e2e suite runs without external auth (the missing piece that unblocks every other unit). W2 already merged the Python integration smoke. W3/W4 add browser + MCP coverage. W5 generalises the fixture surface. W6 wires CI gates. W7 cleans up the PR #23 stub. W8 picks off the smallest carry-over items from the 2.5.0a3 menu.

**How will we know it worked?** See §4 — quantified targets against the same five axes measured in §2.

---

## 2. Before-state measurement (2026-05-12 baseline)

Quantitative axes per [`docs/TENETS.md`](TENETS.md#3-beforeafter-metrics-on-every-meaningful-change-2026-05-12) §3:

| Axis | Current state | Source |
|---|---|---|
| **Manual smoke** | 4 unchecked checkboxes × ~5 min ≈ **20 min of human verification per release** for the WS auth contract alone | PR #23 description |
| **Onboarding bar** | New contributor must authenticate ≥1 of 8 provider CLIs (Kiro / Claude Code / Codex / Q / Gemini / Kimi / Copilot / OpenCode) to run the e2e suite. PR #25 confirmed kiro-cli's IDLE/COMPLETED regex is stale — drift has already begun. | W2 run; CLAUDE.md |
| **Feedback latency on a WS auth regression** | "Next release" (manual smoke cycle); on a busy week, ≥ 1 week from regression introduced to caught | PR #23 description |
| **CI green rate on `main`** | Currently **red** — `uv run black --check src/ test/` fails on two files (`src/cli_agent_orchestrator/mcp_server/server.py` extra blank line; `test/scripts/test_bump_version.py` quote style). This PR includes the fix. | `.github/workflows/ci.yml` `Code Quality` job, observed 2026-05-12 |
| **Per-session pickup time** | New session re-reads PR #24 hand-off + scrapes PR comments to find work state ≈ **10–15 min** before first productive action | Observed in this session pre-`docs/w3-w8-batch.md` |

**Status snapshot (per-workstream):**

| # | Workstream | State | PR |
|---|---|---|---|
| W1 | Managed `cao-server` subprocess fixture | ✅ merged | #24 |
| W2 | Python WS integration smoke (4 scenarios) | ✅ merged | #25 |
| W3 | Playwright browser e2e | ⏸ pending | — |
| W4 | MCP Apps iframe smoke | ⏸ pending | — |
| W5 | Test infrastructure scaling | ⏸ pending | — |
| W6 | CI gating | ⏸ pending | — |
| W7 | PR #23 cleanup | ⏸ pending | — |
| W8 | Carry-over backlog (#2/#3/#4; #5 deferred) | ⏸ pending | — |

The 8-workstream decomposition is canonical in PR #24's hand-off comment ([#issuecomment-4419077619](https://github.com/plauzy/cli-agent-orchestrator.bak/pull/24#issuecomment-4419077619)). This doc adds **W0** as the unblocker.

---

## 3. The change — 10 independent batch units

### Resolved decisions (2026-05-12)

- **Spawn mechanism:** CAO `cao launch --headless --async --yolo` (dogfood the orchestrator on its own development).
- **Parallelism:** fire all units in parallel; accept rebases on `docs/testing.md` (W0/W5 overlap) and on TS `jwt.ts` helpers (W3/W4/W5 overlap).
- **W8 scope:** include sub-items #2, #3, #4. Defer #5 (multi-tenant CAO, needs design RFC first).

### Unit table

| # | Title | Branch | Critical files |
|---|---|---|---|
| 0 | **W0 — Provider tiers + `mock_cli`** | `claude/w0-provider-tiers` | `src/cli_agent_orchestrator/providers/mock_cli.py` (new), `test/providers/test_mock_cli.py` (new), `docs/testing.md` §"Provider tiers", `.github/workflows/e2e-mock.yml` (new), audit of existing `test-*-provider.yml` for secret hygiene |
| 1 | W3 — Playwright browser e2e | `claude/w3-playwright-ws` | `web/playwright.config.ts`, `web/e2e/ws-auth.spec.ts`, `web/e2e/helpers/{jwt.ts,start-cao-server.mjs}` |
| 2 | W4 — MCP Apps iframe smoke | `claude/w4-mcpjam-iframe` | `cao_mcp_apps/scripts/smoke-mcpjam.mjs` (extend) |
| 3 | W5 — Test infrastructure scaling | `claude/w5-test-infra` | `test/fixtures/{jwt_factory.py,jwks_server.py,terminal_factory.py}`, `web/e2e/helpers/jwt.ts`, `cao_mcp_apps/e2e/helpers/jwt.ts`, merge with W0's `docs/testing.md` |
| 4 | W6a — CI gate: python-e2e + PR template | `claude/w6a-ci-python-e2e` | `.github/workflows/python-e2e.yml` (new, uses W0's `mock_cli`), `.github/PULL_REQUEST_TEMPLATE.md` (new) |
| 5 | W6b — CI gate: web-e2e + nightly matrix | `claude/w6b-ci-web-e2e` | `.github/workflows/web-e2e.yml` (new), `.github/workflows/nightly-e2e.yml` (new — Tier-3 matrix per TENETS.md) |
| 6 | W7 — PR #23 cleanup + `docs/auth.md` | `claude/w7-pr23-cleanup` | PR #23 description, `docs/auth.md` lines 136–196 |
| 7 | W8/#3 — PWA refresh-token rotation | `claude/w8-3-refresh-token` | `web/src/auth/*` (~250 LOC) |
| 8 | W8/#4 — Mobile-responsive PWA layout | `claude/w8-4-mobile-layout` | `web/src/**/*.tsx` container queries (~150 LOC) |
| 9 | W8/#2 — PWA bidirectional WS commands | `claude/w8-2-pwa-ws-cmds` | `web/src/components/TerminalView.tsx` (~600 LOC); will rebase on W3 |

**Excluded:**
- W6c (extend `mcp-apps-smoke` with W4 specs) — folded into W4.
- W8/#5 (multi-tenant CAO, ~1500 LOC) — deferred per hand-off; needs design RFC first.

**Conflict expectations under parallel-fire:**
- W0 + W5 both touch `docs/testing.md` → W5 worker prompt says "expect a merge conflict and resolve by appending to W0's tier section".
- W3/W4 both ship a local `jwt.ts` helper; W5 canonicalizes; rebase collapses.
- W6a references `mock_cli`; if W0 lands first, no-op; if W6a lands first, the workflow's first run skips with "provider not found" and a follow-up commit re-enables.

### CAO launch recipe (per unit)

```bash
# One-time per session
uv run cao-server &  # :9889

# Per unit
uv run cao launch \
  --agents code_supervisor \
  --provider <chosen-provider> \
  --headless --async --yolo \
  --session-name w<N>-<short-slug> \
  "$(cat <<'EOF'
<self-contained worker prompt — see template below>
EOF
)"
```

### Worker prompt template

1. **Goal** — "Ship W<N> from PR #24's hand-off comment."
2. **This unit's spec** — title, critical files, change description copied verbatim from the table above.
3. **Setup** — `git fetch origin main && git checkout -b <branch> origin/main`.
4. **Conventions:**
   - Reuse W1 fixtures (`test/fixtures/cao_server.py`).
   - Reuse W2 WS helper pattern (`test/e2e/helpers/ws.py`, `test/e2e/test_websocket_auth.py`).
   - For TS analogs, mirror the Python `JWTFactory` shape but use `jose` or `@panva/jose`.
   - mypy strict on `src/`; black/isort line length 100; pytest excludes `e2e` by default — add `pytest.mark.e2e`.
   - Honour [`docs/TENETS.md`](TENETS.md): pick a provider tier explicitly, fail loudly on provider-side issues, answer the four "why" questions in the PR description.
5. **E2E verification recipe** — see §Verification below.
6. **Closing:** invoke `/simplify`, run `uv run pytest --no-cov` (or web/MCP test scripts), commit, push, open a **draft PR** via `mcp__github__create_pull_request`, end with `PR: <url>`.

---

## 4. After-state target

Same five axes as §2, with the post-batch numbers we will be measurable against:

| Axis | Target | Mechanism |
|---|---|---|
| **Manual smoke** | **0 min/release** for the WS auth contract — W2 (Python, already merged), W3 (Playwright), W4 (MCP iframe) cover all four scenarios automatically | W2 closes Python; W3/W4 close browser + MCP host |
| **Onboarding bar** | **0 providers** required to run the full e2e suite (Tier 2 `mock_cli`); ≥1 real provider only needed for Tier 3 nightly | W0 |
| **Feedback latency on a WS auth regression** | **≤ 5 min** (next CI run on the offending PR) | W6a + W6b: `python-e2e`, `web-e2e`, extended `mcp-apps-smoke` as merge-blocking jobs |
| **CI green rate on `main`** | **100%** — Black fix lands first (this PR); subsequent units are added as already-green CI gates | Black fix in PR #28; all subsequent unit PRs add their own green gates before being merge-blocking |
| **Per-session pickup time** | **≤ 2 min** — fresh session reads §6 "Pickup pointer" and is productive | This doc + TENETS.md, pointed at from PR #24's hand-off |

**Forty-fold reduction on manual smoke time** (20 min → 30 s automated) is the headline single-axis improvement. The compound improvement — every PR runs the full smoke matrix — is what shifts left.

---

## 5. Self-referential proof — the plan is built using its own approach

This batch dogfoods CAO's own abstractions at every layer. If the approach were not idiomatic — if we had to reach outside the project's own building blocks to ship it — that would be a signal the project is missing primitives. The fact that we can shows the primitives are there.

| Layer | The CAO primitive | How this batch uses it |
|---|---|---|
| **Subprocess isolation** | CAO's tmux-subprocess model (`src/cli_agent_orchestrator/clients/tmux.py`) wraps real CLI processes in isolated tmux panes and drives them by tailing pane log files. | W1's `test/fixtures/cao_server.py` uses the *same* `subprocess.Popen` + log-tail health-check pattern to manage cao-server itself. W1 fixtures **are** mini-CAO for testing. |
| **WS auth contract** | The production WS endpoint reads JWTs from `Sec-WebSocket-Protocol: cao.bearer.<jwt>` (`src/cli_agent_orchestrator/api/main.py:1257`). | W2's `test/e2e/helpers/ws.py` builds the *exact* same subprotocol string in `[f"cao.bearer.{token}"]`. The test exercises the production contract — not a parallel test contract. |
| **Parallel agent fan-out** | `cao launch --headless --async` returns a terminal id immediately; the worker calls `send_message` back when done. That is *the* core CAO pattern. | The W3–W9 batch fires 9 of these calls in parallel. The batch decomposition (10 self-contained units, no shared mutable state, mergeable in any order) is the same constraint CAO imposes on agents fanning out under `Assign`. |
| **Provider tiers** | CAO supports 8 provider CLIs. Each has its own auth path; CAO's `providers/manager.py` arbitrates. | Tenet #1 (provider-onboarding as first-class concern) makes this arbitration **explicit** at the policy layer. W0's `mock_cli` becomes the 9th provider — produced by the same `providers/base.Provider` abstraction. |
| **Why-first** | The four-question filter in Tenet #2 maps onto an `AskUserQuestion` clarify-then-act loop — the same loop CAO's supervisor agents run before delegating. | This very document answers the four questions in §1 before §3 introduces the change. The doc itself is shaped by the methodology it codifies. |

**The recursive case:** this batch was decomposed using the same parallelism rules CAO enforces on agents (independent, self-contained units; no shared state; mergeable in any order). If those rules don't hold for human workstreams, they don't hold for agent workstreams either — and CAO's value proposition collapses. So the batch's structure is a stress test of CAO's own design.

---

## 6. Verification

**Provider sanity check (gate the whole batch):**
```bash
uv run cao-server &
sleep 3
uv run cao launch --provider <chosen> --agents developer --headless --yolo \
  --session-name probe-<provider> "Print the word READY and exit."
```
Expect: terminal reaches IDLE within 30 s; output contains "READY". If this fails, fix the provider per TENETS.md §1 "Cycle time" before firing the batch.

**Per-unit verification (what each worker is told):**

- **W0:** `uv run pytest test/providers/test_mock_cli.py -v` green; `cao launch --provider mock_cli "say hi"` returns "hi" within 5 s.
- **W3:** `cd web && npm run test:e2e -- --grep "ws-auth"` runs the 4 specs against a managed cao-server; expect green.
- **W4:** `cd cao_mcp_apps && node scripts/smoke-mcpjam.mjs --iframe` returns 0 with non-empty HTML for the agent resource.
- **W5:** `uv run pytest test/fixtures/test_jwt_factory.py -v` plus a single W2 scenario rewritten on top of `JWTFactory` still passes.
- **W6a/b:** workflow files validate (`actionlint` if available) and dry-run on the unit's own draft PR.
- **W7:** PR #23 description shows the new automated-smoke pointer; `docs/auth.md` diff small and references `test/e2e/test_websocket_auth.py`.
- **W8/#2-#4:** each unit ships its own integration test (where applicable) and is exercised manually via `cd web && npm run dev` in the worker's worktree before commit.

**Batch tracker:** after launching all 10, the coordinating session renders the status table and re-renders as each worker reports `PR: <url>`.

---

## 7. Pickup / onboarding pointer

For a fresh contributor (or a fresh session) picking this up cold. Linear reading order; time estimates assume a contributor familiar with Python + git but new to this repo:

| # | Read | Time | Why |
|---|---|---|---|
| 1 | [`docs/TENETS.md`](TENETS.md) | ~5 min | The "why" filter all work passes through (Tenets #1–#3). Read this *first* — every other doc presupposes you've internalised it. |
| 2 | `README.md` + `CLAUDE.md` | ~10 min | What CAO is and how to talk to it. |
| 3 | **This file** (`docs/w3-w8-batch.md`) | ~15 min | The current batch's why, before-state, change, after-state, self-referential proof. |
| 4 | PR #24 hand-off ([#issuecomment-4419077619](https://github.com/plauzy/cli-agent-orchestrator.bak/pull/24#issuecomment-4419077619)) | ~10 min | The original W1–W8 decomposition from the previous session. Cross-reference for unit specifics. |
| 5 | `docs/rfc/cao-auth0-websocket-2026-05-11-v1.md` | ~10 min | The auth contract the batch is hardening. Skip if you're picking up a non-WS unit (W8/#4 layout, etc.). |
| 6 | `test/fixtures/cao_server.py` + `test/e2e/test_websocket_auth.py` | ~10 min | The W1/W2 patterns every unit reuses. Read the code, not just the docstrings. |

**Total cold-start time: ~60 min.** Compare to ~10–15 min before this doc existed *but with no clear "why" to anchor the work*. The extra 45 minutes pays for itself the first time a contributor doesn't go down a wrong path.

**Then act:**

1. Run the **Provider sanity check** in §6. If it fails, fix the provider first (per TENETS.md §1).
2. Decide: fire all 10 in parallel (faster, accept rebases), or land W0 first and then fire 9 (cleaner, +1 PR cycle).
3. Fire the worker prompts.

---

## 8. Critical files referenced

- `test/fixtures/cao_server.py` — W1 fixtures, reused by every unit that needs a server.
- `test/e2e/test_websocket_auth.py` + `test/e2e/helpers/ws.py` — W2 helper pattern, reused by W3/W5.
- `test/conftest.py` — `mint_test_token` helper, reused by W5 (becomes `JWTFactory`).
- `src/cli_agent_orchestrator/api/main.py:1257` — `terminal_ws` endpoint, contract reference for W3/W4.
- `src/cli_agent_orchestrator/clients/tmux.py` — the tmux-subprocess primitive cited in §5.
- `src/cli_agent_orchestrator/providers/base.py` — the `Provider` ABC that W0's `mock_cli` extends.
- `docs/rfc/cao-auth0-websocket-2026-05-11-v1.md` — WS auth spec, reference for W7.
- `cao_mcp_apps/scripts/smoke-mcpjam.mjs` — existing MCP smoke, extended by W4.
- [`docs/TENETS.md`](TENETS.md) — provider tier model, why-first filter, reusable template, referenced by every unit.
