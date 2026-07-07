<!--
DRAFT v2 — NOT PUBLISHED. Internal working copy in the plauzy fork only.
Supersedes docs/reviews/pr387-agui-response-draft.md (baf9d45). Changes vs v1:
  - WITHDRAWN: the "### Removed" CHANGELOG concession and the dedicated
    provider-removal PR offer — both rested on a false premise (this PR deletes
    nothing; q_cli/gemini_cli were removed upstream in #353, which is in the
    merge base).
  - ADDED: the evidence-based correction on the deletion claim, plus the
    counter-offer (we found and are fixing the dead gemini example this PR
    actually adds).
  - ADDED: evidence (not hedge) on the inclusive-language attribution; ci.yml /
    npm-install correction folded in.
  - KEPT from v1: everything else (B1/B2 acceptance, decomposition, 157-not-400,
    EventSource pushback, fails-closed framing, Copilot five, closing value case).
Do NOT post to the upstream CR until reviewed by the maintainer of this fork.
Paste-ready as a single PR comment when approved.
-->

# Draft response to PR #387 reviews (v2)

Thanks all — @gutosantos82 for the thorough multi-angle pass (the dynamic
verification of the AG-UI core is genuinely appreciated), @fanhongy for the
decomposition steer and for reproducing the A2A issue, and the Copilot reviewer
for the inline nits. Short version: **I agree with the decomposition and I'm
splitting this PR** — landing the verified AG-UI core first and holding A2A
until auth is wired. I'm also correcting a few findings below that attach to
pre-existing repo state rather than this diff, so the record stays accurate.

## Where we fully agree (fixing these)

- **A2A auth gap (blocking).** Correct and fair catch. The A2A routers mount on
  the `:9890` listener with no scope enforcement, and the `rpc.py` docstring
  claims JWKS protection that isn't wired — worse than silence. Fix (in the
  split-out A2A PR): per-method scope enforcement inside the JSON-RPC handler
  using the existing `require_any_scope` / `is_auth_enabled` infra
  (`task.send`/`task.cancel` → `cao:write`; `task.get`/stream → `cao:read`),
  returning 401/403 with JSON-RPC error bodies; plus a fail-closed guard that
  refuses to mount the A2A routers on a non-loopback bind when auth is
  unavailable; plus truthful docstrings.
- **Unbounded task store.** Adding a size cap + TTL eviction to
  `InMemoryTaskStore` (env-tunable), with `task.send` rejected when full of
  non-terminal tasks. One note for severity calibration: remote exploitability
  is conditional on the auth gap above *plus* the non-default
  `CAO_AGENT_CARD_HOST=0.0.0.0` opt-in — fixing auth removes the remote vector
  and the bound is defense-in-depth. Both ship together in the A2A PR.
- **Token-parse exceptions → 500.** Agreed. Wrapping the SSE and WS token paths
  (`except Exception → 401` / close `4401`) and adding the missing
  malformed/expired-bearer tests. It already fails closed (no data served), so
  this is auth-telemetry hygiene rather than a bypass — but worth doing.
- **Description ↔ code mismatch.** You're right that
  polecat/Cedar/WAL/swarm/policy-queue/cache don't exist in the tree — they were
  never in this PR's code. That's overselling in the PR *description*, and the
  fix is prose: I'm rewriting the body to list exactly what the diff contains,
  nothing more. (The same rewrite also removes the body's provider-deletion
  claim — see the correction below.)
- **Copilot nits (all five).** Removing the stray `tests/__init__.py`; setting
  mypy `python_version = "3.10"` to match `requires-python` (this PR had already
  fixed the corrupt `"2.1.1"` value on main); citing W3C Trace Context instead
  of RFC 9114 in `plugins/events.py`; fixing the nested-interactive-button a11y
  issue in `InstancePicker.tsx`; updating the stale `test_headless_ci.py`
  docstring.
- **Assorted:** folding the dated `generative-ui-implementation-2026-07-04.md`
  into `docs/pwa.md`; moving the OTel deps under an `[otel]` optional extra —
  and on the other two flagged deps: `authlib` moves to the dev group (only the
  JWT/JWKS test fixtures import it) and `python-multipart` is removed outright
  (nothing imports it), so no `[a2a]` runtime extra is invented — the A2A
  runtime itself needs neither (its verification path is `pyjwt[crypto]`);
  tightening the `_agui_enabled()` docs — the `CAO_MCP_APPS_ENABLED`
  interaction is intentional (the two surfaces share one in-process event
  source) but the wording will say so explicitly; de-stubbing the `?since=`
  boundary in the endpoint test so the replay wiring is exercised end-to-end;
  stripping the unrelated README/CODEBASE reformatting.

## Decomposition plan (taking @fanhongy up on the offer)

Two PRs, structured exactly along the verified/blocked boundary:

1. **PR-A — AG-UI core + generative UI + PWA + `mock_cli` + opt-in OTel**
   (this PR, reshaped in place; ≈13k lines incl. the PWA and fixtures). This is
   the subset the review already verified: default-off (404s, no extra
   listener), metadata-only redaction by construction, allow-list refusal at
   both layers, 99% adapter coverage. Lands first, with the hardening items
   above.
2. **PR-B — A2A JSON-RPC + signed Agent Card listener** (≈3.4k lines, 25
   files, new branch) — held until the auth gating, store bounds, docstring
   corrections, and the per-method 401/403 test matrix are in. A full store of
   live tasks refuses `task.send` with `RESOURCE_EXHAUSTED` at **HTTP 429**
   (with a `Retry-After` hint) so HTTP-native retry middleware backs off
   without understanding A2A error codes — domain errors still ride 200 as
   JSON-RPC error bodies.

**Proof layer shipping with PR-A** (beyond the review's asks): a live-path
Playwright recording — a real `cao-server` + the real dashboard driving all
six generative-UI components, the off-list refusal, and `?since=` recovery
from a **hard server restart** (an event emitted during the outage arrives via
replay) — plus a runnable `examples/agui-dashboard/` quick start whose
`showcase.sh` doubles as a deployment smoke test, and an `agui-author` skill
teaching agents the component vocabulary. The recording regenerates in CI on
every relevant change; the committed copy can be dropped in favor of the CI
artifact if you'd prefer no binary in the tree.

## Reply to review 4638092590 (@anilkmr-a2z)

Thanks — all five land as follows. The auth-enforcement and unbounded-store
must-fixes are the same B1/B2 above, fixed in PR-B (per-method scope table +
cap/TTL exactly along the lines you sketched, including reusing the
`WORKFLOW_OUTPUT_STORE_MAX_ENTRIES` precedent's shape). Your task-`id`
injection catch is real and was in neither of our earlier fix sets: PR-B now
rejects a `task.send` whose `id` already exists with `INVALID_PARAMS`
(idempotent-create, your option (b) — peers keep client-generated ids, but an
id can never overwrite another task), and `Task.from_dict` uses
`data.get("id", "")` so an omitted id takes the server-generated-UUID path
instead of raising `KeyError`. `authlib` moves to the dev dependency group in
PR-A (your read matches ours: only the test fixtures import it).

## Corrections for the record (with evidence)

- **Scale:** this PR is **157 changed files (+16,288 / −119)**, not ~400 —
  GitHub's Files tab and the Copilot review header ("150 of 157") both show it.
  Still too big, hence the split — but the scope argument should rest on the
  real number. (A few cited locations — `ci.yml:361,427`, `CHANGELOG:773-807` —
  don't exist on this branch, so part of the pass may have run against a stale
  or stacked checkout.)
- **Provider "deletion":** this PR **deletes nothing** — the diff has zero
  removed files (117 added / 40 modified / 0 deleted). `q_cli` and `gemini_cli`
  were removed by **#353**, which is already in this PR's merge base; `main` has
  no such providers today. So there's no `### Removed` entry for this PR's
  CHANGELOG to carry — that entry belongs to #353's release notes, and I'm happy
  to backfill it there in a separate docs PR. My earlier PR body wrongly claimed
  the deletion too; that claim is being removed in the rewrite. **What this PR
  *does* contain — and no review caught — is the inverse bug:** it *adds*
  `examples/cross-provider/data_analyst_gemini_cli.md` pointing at the
  now-nonexistent `gemini_cli` provider. That example is dead configuration and
  I'm retargeting it to `antigravity_cli` (the documented successor, upstream
  since #323) in PR-A.
- **Inclusive language:** happy to honor the allowlist/denylist/primary
  convention, but the flagged occurrences are not introduced here —
  `audit_log.py` (`AUDIT_EVENT_WHITELIST`), `memory_scoring.py`,
  `memory_service.py`, `docs/memory.md`, `docs/mcp-apps.md` are all untouched by
  this diff and the terms exist on `main` today. I'll fix them in a small
  separate hygiene PR (together with the `deliver_pending()` rename references
  in `docs/inbox-delivery.md`, which likewise pre-date this PR) so they don't
  gate this stack.
- **`npm ci` vs `npm install`:** the two workflows this PR *adds* both use
  `npm ci`; the `npm install` occurrences are in `ci.yml`, which this PR doesn't
  touch. Also happy to fix those in the hygiene PR.
- **JWT in the query string:** agreed the token shouldn't land in access logs,
  and I'm scrubbing/disabling access logging on that route (the `:9890` listener
  already sets `access_log=False`; the main app didn't) plus documenting short
  token TTLs. On the mechanism itself: browser `EventSource` cannot set an
  `Authorization` header, so a query-param credential (or short-lived ticket) is
  the standard SSE pattern — I've filed the single-use ticket handshake as a
  follow-up rather than removing query auth. This path is also only reachable
  when auth is enabled *and* the operator has opted out of the loopback default.
- **`.coverage-baseline.json`:** intentional — it's the ratchet-floor config the
  coverage script reads (as your conventions reviewer concluded). It pre-dates
  this PR; I'll add a one-line header comment in the hygiene PR so it isn't
  mistaken for a stray artifact.

## Why keep pushing on AG-UI

The core value is one standard surface over N heterogeneous CLI agents — Kiro
CLI, Claude Code, and Codex rendering uniformly in any stock AG-UI client with
zero custom adapter code — backed by real tmux process lifecycle, with a
metadata-only privacy boundary, and the entire protocol dependency bounded to a
single pinned, default-off module. Your own verification confirmed those
properties hold. Splitting the PR serves that goal: the verified core reaches
users now, and the A2A transport returns hardened.

I'll push the reshaped PR-A shortly and link PR-B here when it's ready for
review.
