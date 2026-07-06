# PR #387 review audit — unified synthesis (Claude × Kiro × Gemini)

- **Date:** 2026-07-06
- **Subject:** [awslabs/cli-agent-orchestrator#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387) — "AG-UI protocol adapter + agentic protocol surface & generative UI (#386)"
- **PR head audited:** `plauzy:feat/agentic-protocols-generative-ui @ f40933d` (1 squashed commit; merge base with upstream main: `01472e2`)
- **Feedback synthesized:**
  - [Review 4632216702](https://github.com/awslabs/cli-agent-orchestrator/pull/387#pullrequestreview-4632216702) by @gutosantos82 — "Request changes" (2 blocking, 6 important, 7 nits, 1 internal disagreement)
  - Review 4630767146 + inline comment by @fanhongy (collaborator) — decomposition ask + independent reproduction of the A2A auth bypass
  - Copilot review 4630445573 — 5 inline nits
  - Codecov patch-coverage note (author already addressed with targeted tests)
  - **Kiro agent audit** + paste-ready response draft (`baf9d45`, `docs/reviews/pr387-agui-response-draft.md` on plauzy/cli-agent-orchestrator)
  - **Gemini architectural audit** — "Glass Wall" MCP-Apps framing, six accept/reject decisions, 5-phase execution plan
- **Method:** every consequential claim was re-verified against the fetched PR branch, upstream `awslabs:main`, and the sibling branches (`feat/port-fork-net-new-subsystems`, `claude/ag-ui-next-gen-audit-l7uedx`). Each verdict below carries its reproducible proof.

---

## 1. Executive summary — the reframe that matters

**The review validates the AG-UI thesis; it does not reject it.** gutosantos82's own dynamic verification confirmed every issue-#386 acceptance criterion on the AG-UI core: default-off/byte-identical with no flags (404s, no extra listener), message bodies never on the wire (redaction by construction, fed a canary secret through both event shapes), generative-UI allow-list refusal at both the adapter and producer layers, 99% adapter coverage, and tests judged "genuinely meaningful shift-left — not coverage-gaming."

**Every blocking finding lives in the bundled A2A transport — none in AG-UI.** The correct move is therefore the one the collaborator (@fanhongy) already proposed and the PR author already offered: split, land the verified AG-UI core first, hold A2A until auth is wired. Splitting is *pro*-AG-UI — it stops a 3.4k-line unrelated transport from holding the headline feature hostage.

**But the review also contains six findings that are misattributed to this PR** (they describe pre-existing upstream state or things not in the diff at all), plus one materially wrong number ("~400 files" — it is 157). Those are itemized in §4 with evidence, as clean pushback material.

**And one real defect none of the reviews caught:** the PR *adds* `examples/cross-provider/data_analyst_gemini_cli.md` declaring `provider: gemini_cli` — a provider that does not exist anywhere in the tree (removed upstream in #353). That example is dead-on-arrival configuration and should be dropped or retargeted to `antigravity_cli` (the documented Gemini successor, upstream since #323).

### Why AG-UI benefits CAO (the value being defended)

1. **One standard face over N heterogeneous CLI agents.** Every other AG-UI source is single-framework. CAO's normalized six-event vocabulary makes it the first *heterogeneous* source — Kiro CLI, Claude Code, Codex render uniformly in any stock AG-UI client (CopilotKit, Dojo, plain `EventSource`) with zero custom adapter code. The Playwright demo already proves it.
2. **Real-process runtime.** AG-UI assumes an addressable HTTP agent; CAO supplies the missing tmux-backed OS-process lifecycle (spawn/resume/multiplex). Nobody else bridges real terminal agents into the protocol.
3. **Privacy-bounded observability.** Metadata-only on the wire, enforced by construction and asserted by tests the reviewer verified. A genuinely novel posture in the AG-UI ecosystem.
4. **Bidirectional context loop (Gemini's "Glass Wall" point).** The AG-UI SSE surface and the already-upstream MCP Apps surface share one in-process event source — which is exactly why `_agui_enabled()` treats `CAO_MCP_APPS_ENABLED` as an enabling condition. UI interactions flow back through `submit_command` and `app.updateModelContext()` without forcing an inference cycle; AG-UI extends the same loop to any browser, no MCP host required.
5. **Bounded dependency risk.** The whole protocol dependency is one pinned, default-off module (`services/agui_stream.py`, 377 lines) — the hedge #386 promised, and it holds in the code.

---

## 2. Ground truth established this session

These facts anchor every verdict below.

| # | Fact | Proof |
|---|------|-------|
| G1 | The PR diff is **157 files, +16,288 / −119** — not "~400 files" | `git diff --stat origin/main...HEAD`; Copilot's review header says "150 of 157 changed files" |
| G2 | The PR **deletes nothing**: 117 added, 40 modified, **0 deleted** | `git diff --name-status origin/main...HEAD \| awk '{print $1}' \| sort \| uniq -c` → `117 A / 40 M` |
| G3 | `q_cli.py` / `gemini_cli.py` were removed by **upstream #353** (commit `f6d3b29`, "Remove Amazon Q CLI and Gemini CLI providers (#353)"), which is an **ancestor of the merge base** — awslabs `main` has no such providers today | `git log --diff-filter=D --follow -- src/.../providers/q_cli.py`; `git ls-tree origin/main:src/cli_agent_orchestrator/providers/`; live fetch of awslabs main providers dir |
| G4 | The PR **adds** `examples/cross-provider/data_analyst_gemini_cli.md` with `provider: gemini_cli` — a nonexistent provider | `git diff --name-status` → `A examples/cross-provider/data_analyst_gemini_cli.md`; file front-matter reads `provider: gemini_cli` |
| G5 | A2A routes carry **no auth**: `build_a2a_router()` / `build_stream_router()` attach no dependency; `agent_card/listener.py::build_listener_app` does bare `app.include_router(a2a_router)`; yet `a2a/rpc.py:24-25` claims "Authentication is enforced via the JWKS" | Source read of `a2a/rpc.py`, `agent_card/listener.py`; @fanhongy reproduced anonymous `task.send → 200` with auth enabled |
| G6 | `InMemoryTaskStore` is a plain dict with no cap/TTL ("Tasks live until either explicitly deleted or until the process restarts") | Source read of `a2a/store.py` |
| G7 | `security/auth.py::extract_scopes_from_token` raises `PyJWTError` subclasses; the SSE path (`api/main.py:781`) wraps nothing; `_extract_ws_scopes` (main.py:1894) catches only `HTTPException` | Source read |
| G8 | Main app `uvicorn.run()` (main.py:2545) sets no `access_log=False`; the `:9890` listener does (listener.py:113) | Source read |
| G9 | `polecat / Cedar / policy_queue / WAL / swarm` → **zero matches** in `src/` on the PR branch | `git grep -riE 'polecat\|cedar\|policy_queue\|\bWAL\b\|swarm' -- src/` |
| G10 | Files cited by the review as "introduced" violations are **not in the diff** and exist on upstream main: `services/audit_log.py` (`AUDIT_EVENT_WHITELIST`), `memory_scoring.py`, `memory_service.py`, `docs/memory.md`, `docs/mcp-apps.md`, `docs/inbox-delivery.md`, `.github/workflows/ci.yml`, `.coverage-baseline.json` | Per-file `git diff --stat origin/main...HEAD -- <file>` → "NOT IN PR DIFF"; `AUDIT_EVENT_WHITELIST` verified present on awslabs main |
| G11 | The PR's two **new** workflows use `npm ci` correctly; the `npm install` occurrences are in untouched `ci.yml` (lines 120/186 — the review's "ci.yml:361,427" don't exist on this branch) | `git grep -n 'npm (ci\|install)' -- .github/workflows/` |
| G12 | mypy `python_version = "3.11"` (the PR *fixed* main's corrupt `"2.1.1"`) vs `requires-python = ">=3.10"`; only one `[tool.mypy]` `python_version` remains | `pyproject.toml` on branch, lines 6 / 119 |
| G13 | The MCP Apps surface (`mcp_server/app_tools.py` with `submit_command` + `cao_fetch_history`, `cao_mcp_apps/` incl. `scan-jit.mjs`, `check-bundle-size.mjs`, `coverage-ratchet.mjs`) and `antigravity_cli.py` are **already on upstream main** — they pre-date this PR | `git ls-tree origin/main:...` for each path |
| G14 | Gemini Phase-4 UI items mostly exist in the ported `cao_mcp_apps`: `AgentStatus.tsx`, `HeaderBar.tsx` (fleet counts), `container-type: inline-size` (styles.css:27), `updateModelContext` (mcpApp.ts:236). **Not found:** any `execution_mode` / headless-vs-interactive badge logic | `git grep` over `origin/feat/port-fork-net-new-subsystems -- cao_mcp_apps/src/` |

Branch roles, for the record: `claude/ag-ui-next-gen-audit-l7uedx` = the value-articulation / issue-#386 narrative work; `feat/port-fork-net-new-subsystems` = the Kiro-agent port of fork subsystems with all lint/type/test gates green (+ WS-auth RFC implementation); `feat/agentic-protocols-generative-ui` = the combined bundle submitted upstream as PR #387.

---

## 3. Verdicts — findings we accept (and how the three audits compare)

### Blocking (both fix in the A2A follow-up PR, not in the AG-UI core PR)

**B1 — A2A auth bypass. ACCEPT unreservedly.** (G5.) Real, reproduced, and the false docstring makes it worse than silence. Fix: per-method scope enforcement inside the JSON-RPC handler using the *existing* `security/auth.py` infra (`require_any_scope`, `is_auth_enabled`) — `task.send`/`task.cancel` → `cao:write`; `task.get`/stream/REST reads → `cao:read` — plus a fail-closed mount guard and truthful docstrings. All three audits agree; Kiro's fix sketch is correct and adopted.

**B2 — Unbounded task store. ACCEPT, with Kiro's severity caveat.** (G6.) Cap + TTL-evict. Note in the reply that remote exploitability is conditional on B1 plus a non-loopback bind (`CAO_AGENT_CARD_HOST=0.0.0.0` opt-in): fixing auth removes the remote vector; the bound is defense-in-depth. Frame as "ships together with B1," not an independent critical.

### Scope / decomposition

**B3 — "Split the PR." ACCEPT the direction; CORRECT the number; propose a two-PR split.**
- Accept: 157 files is still too big for core `src/`, the author already offered to split, and the collaborator asked for exactly this.
- Correct: "~400 files" is wrong (G1). Say so politely — the inflated figure is the anchor of the "reckless scope" framing.
- Structure (measured): **PR-A** = AG-UI core + generative UI + PWA + `mock_cli` + OTel ≈ 12.9k lines — precisely the subset fanhongy asked to land first and the subset the reviewer's verifier already validated. **PR-B** = A2A + Agent Card ≈ 3,351 lines / 25 files, held until B1/B2 are fixed.
- Where the audits differ: Kiro proposed 4–5 PRs including a dedicated *provider-removal* PR — dropped, because no removal exists in this PR (G2/G3). gutosantos82's stricter 6-way split buys little: OTel is 695 lines and default-off; `mock_cli` is test infrastructure the CI depends on; forcing five re-review cycles is the real cost.

### Important — fix in PR-A

**I1 — PR description oversells. ACCEPT (doc-only).** (G9.) Polecat/Cedar/WAL/swarm/3-layer-cache don't exist in the tree; **and the body's "deletion of q_cli/gemini_cli" claim is equally false** (G2/G3) — the description is wrong in both directions. Fix = rewrite the PR body to list only what the diff contains. No code to build. State plainly in the reply that this is prose debt, not half-shipped features.

**I2 — JWT in query string. ACCEPT the log-leak concern; REJECT the "token-in-URL is inherently the bug" framing.** Browser `EventSource` cannot set an `Authorization` header, so query-param tokens (or short-lived tickets) are the standard SSE pattern. Fix = scrub/disable access logging on `/agui/v1/stream` (G8 — the listener already does this; the main app doesn't), document short token TTLs, and file the short-lived-ticket handshake as a follow-up. Also note the exposure preconditions: auth enabled *and* non-default binding.

**I3 — Token-parse exceptions surface as 500 / opaque WS handshake error. ACCEPT.** (G7.) It fails *closed* today (no data served — the reviewer concedes this), so it's telemetry hygiene, not a bypass. Broad-catch → 401 (SSE) / 4401 (WS), plus the missing malformed/expired-bearer tests.

### Nits — accept, batch into PR-A

- `_agui_enabled()` also true under `CAO_MCP_APPS_ENABLED` (main.py:644-655): intentional (shared event source — see §1.4), but tighten the docstring/docs wording; the "byte-identical with no new flags" claim survives either way.
- De-stub the `?since=` boundary in `test/api/test_agui_stream_endpoint.py` (the fake log ignores kwargs, so main.py replay wiring isn't exercised end-to-end).
- Fold `docs/generative-ui-implementation-2026-07-04.md` into `docs/pwa.md` (dated impl logs drift).
- OTel deps → `[otel]` optional extra; `authlib` + `python-multipart` leave with PR-B anyway. (Note for the reply: the review lists `pyjwt[crypto]` among the added deps — it's pre-existing upstream; only 5 deps are new.)
- Copilot's five, all valid: delete stray `tests/__init__.py` (13-byte second test root); mypy `python_version` → `"3.10"` to match `requires-python` (G12 — the PR already fixed main's corrupt `"2.1.1"`); fix the RFC 9114 mis-citation in `plugins/events.py` (that's HTTP/3 — cite W3C Trace Context); restructure the nested interactive `<button>` in `InstancePicker.tsx`; update the stale `test_headless_ci.py` docstring (conftest auto-starts the server).
- Strip unrelated README/CODEBASE prose reformatting to cut diff noise.

---

## 4. Verdicts — findings we push back on (evidence quoted, paste-ready arguments in the response draft)

**R1 — "PR deletes q_cli/gemini_cli; CHANGELOG missing `### Removed`." REJECT — misattributed.** G2 + G3: zero deletions in the diff; the removal is upstream history (#353, in the merge base). There is nothing for this PR's CHANGELOG to record under `Removed`. **Counter-offer that shows good faith:** this PR *does* contain a related real bug — the re-added `data_analyst_gemini_cli.md` example targeting the nonexistent provider (G4) — which we'll delete/retarget. (Kiro's draft conceded R1 and even proposed a dedicated provider-removal PR; that concession is withdrawn in draft v2. Kiro's underlying observation about the example file was correct — just inverted: the example isn't "left behind after deletion," it's newly added against a provider that no longer exists.)

**R2 — "Inclusive-language violations, introduced." REJECT the attribution; accept the convention.** G10: every cited file is untouched by this PR and the terms exist on upstream main today. Fix what a PR actually introduces; pre-existing occurrences go to a separate hygiene PR (offered — see remediation plan Phase E) so they don't gate this stack.

**R3 — "inbox-delivery.md doc drift, introduced this PR." REJECT — misattributed.** G10: neither `docs/inbox-delivery.md` nor `services/inbox_service.py` is in the diff; the `deliver_pending()` rename pre-dates this PR on main. Happy to fix the 4 stale references in the hygiene PR.

**R4 — "New cao-mcp-apps CI job runs `npm install` (ci.yml:361,427)." REJECT — misattributed.** G11: `ci.yml` is untouched; the cited lines don't exist on this branch; both workflows this PR adds use `npm ci`. (The `cao-mcp-apps` job itself pre-dates the PR — G13.)

**R5 — `.coverage-baseline.json` disagreement. MOOT for this PR.** G10: not in the diff. Independently: it's the ratchet-floor config the coverage script reads (the review's own conventions-reviewer reached the same conclusion) — keep, add a one-line header comment in the hygiene PR so it isn't mistaken for a stray artifact.

**R6 — "~400 files / +16k lines." CORRECT THE RECORD.** G1: 157 files. The +16k is right. This matters because the file count anchors the scope argument; several stale line references (ci.yml:361, CHANGELOG:773-807) suggest part of the review ran against a stale or stacked checkout — worth one polite sentence, no more.

> **Accuracy scorecard on review 4632216702:** its `api/main.py`, `a2a/*`, and `agent_card/*` findings are precise and its dynamic verification of the AG-UI core is exemplary. Its misses cluster where it relied on repo-wide greps or historical claims without checking diff attribution (R1–R6). Engage it as a strong review with a fixable evidence problem in six places.

---

## 5. Gemini's audit — how it integrates

Gemini's six accept/reject decisions answer **fork-side design-review comments** (deprecate the localhost dashboard; ship Auth0 now; granular mutation tools; relax JIT-free; headless-agent support; localStorage persistence) — not the comments on PR #387. They are preserved here as **standing architectural positions** to reuse verbatim if these topics surface in the upstream CR or future reviews:

1. **Keep both dashboard surfaces** (standalone PWA/web *and* IDE-embedded MCP App): different consumer profiles (SSH-tunneled headless boxes vs IDE sidebars), shared React component library, CSP-bug fallback. *Consistent with this audit:* PR-A ships `cao_pwa` alongside the upstream MCP Apps surface.
2. **Defer the full Auth0 / OAuth 2.1 loop (DCR, OBO tokens) to the sibling RFC.** ⚠️ *One precision so this is never quoted against PR-B:* the A2A fix (B1) is **not** the Auth0 loop — it's wiring the *already-shipped* JWT scope infra (`require_any_scope`) into routes that falsely claim protection. Cheap, required, and unrelated to the deferred OAuth work. Don't let "we deferred auth" blur into "we deferred fixing the bypass."
3. **Keep the single `submit_command` choke point** — tool-registry hygiene, lower token latency, one RBAC pinch point when the Auth0 phase lands. (Already upstream — G13.)
4. **Keep JIT-free bundles** (`allowUnsafeEval: false` hosts) — enforced by the shipped `scan-jit.mjs` gate. (Already upstream — G13.)
5. **Interactive vs headless agents: ACCEPT** — the one Gemini Phase-4 item with a real gap (G14): no `execution_mode` badge logic exists in `cao_mcp_apps`. Fork-side follow-up, not CR work.
6. **Reject `localStorage`; keep `cao_fetch_history` rehydration** — already shipped upstream (G13).

Gemini's 5-phase execution plan is **largely already landed** (G13/G14): Phase 1 (JIT scanner, bundle-size budget, coverage ratchet), Phase 2 (event log service, ui_state_service, `cao_fetch_history` with app-only visibility), Phase 3 (`submit_command`), most of Phase 4 (AgentStatus/HeaderBar/container queries/updateModelContext), Phase 5 (`antigravity_cli.py`, upstream via #323). Treat that plan as historical record; the genuinely outstanding remnants — headless badges (4.1), HeaderBar token-rate warning (4.2, unverified), Auth0 scope stubs (3.3, superseded by `security/auth.py`) — are catalogued in the remediation plan's backlog section, **outside** the CR.

Gemini's "Glass Wall" / inference-free-ingestion framing is adopted into the value narrative (§1.4) — it is the best articulation of why the AG-UI surface and MCP Apps surface are one program, not two.

---

## 6. Kiro's audit — how it integrates

Kiro's audit is the closest to this one and its response draft (`baf9d45`) is ~80% adopted. Differences, resolved by evidence:

| Topic | Kiro's position | This audit | Resolution |
|---|---|---|---|
| Provider deletions | "Real, confirmed" (checked absence on branch); accepts `### Removed`; proposes dedicated removal PR | Absence ≠ deletion-by-this-PR: 0 `D` entries; removal is merge-base history (#353) | **Correct Kiro** — draft v2 withdraws both concessions, adds R1 pushback + the G4 example counter-offer |
| gemini example | "Still ships — inconsistent leftover after deletion" | It's newly **added** by this PR against a nonexistent provider | Same file, inverted causality; fix is identical (drop/retarget) — keep, reworded |
| "~400 files" | Overstated → 157 | Same | Agree |
| B1/B2, I2 EventSource pushback, I3, `.coverage-baseline` keep, Copilot five | Accept/fix | Same | Adopted verbatim into draft v2 |
| Split shape | 4–5 PRs (core / A2A / providers / extras / telemetry) | 2 PRs (core+extras / A2A) | Provider PR evaporates with R1; OTel+extras are too small to justify their own review cycles — fold into PR-A |
| Inclusive language | "Some flagged files pre-existing — verify" | Verified: **all** cited files untouched (G10) | Strengthened from hedge to evidence |

---

## 7. Outcome

- **Post:** the revised reply (`pr387-agui-response-draft-v2.md`) — accepts B1/B2/I1–I3 + nits, commits to the two-PR split, pushes back on R1–R6 with the proofs above.
- **Execute:** the remediation plan (`pr387-kiro-remediation-plan.md`) — Phases A–E for the Kiro agent.
- **Net effect:** the AG-UI core (#386's actual scope) merges on its verified merits; the A2A transport returns hardened; the six misattributed findings are corrected on the record without conceding false premises; and the one real defect the reviews missed gets fixed by us, proactively.
