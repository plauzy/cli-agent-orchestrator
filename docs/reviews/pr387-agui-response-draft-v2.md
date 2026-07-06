<!--
DRAFT v2 — NOT PUBLISHED. Internal working copy in the plauzy fork only.
Supersedes docs/reviews/pr387-agui-response-draft.md. Withdraws the two
false-premise concessions (this PR deletes nothing; q_cli/gemini_cli were
removed upstream in #353, already in the merge base) and adds the
evidence-based push-back. Do NOT post to the upstream CR until the fork
maintainer approves. Paste-ready as a single PR comment.
-->

# Draft response to PR #387 reviews (v2)

Thanks all — @gutosantos82 for the thorough multi-angle pass (the dynamic
verification of the AG-UI core is genuinely appreciated), @fanhongy for the
decomposition steer and for reproducing the A2A issue, and the Copilot reviewer
for the inline nits. Short version: **I agree with the decomposition and I'm
splitting this PR** — landing the verified AG-UI core first and holding A2A
until auth is wired. A few findings attach to pre-existing repo state rather
than this diff; I've called those out so the record stays accurate.

## Where we fully agree (fixing these)

- **A2A auth gap (blocking).** Correct and fair. The A2A routers mount on the
  `:9890` listener with no scope enforcement and the `rpc.py` docstring claims
  JWKS protection that isn't wired. Fix (in the split-out A2A PR): per-method
  scope enforcement inside the JSON-RPC handler via the existing
  `require_any_scope` / `is_auth_enabled` infra (`task.send`/`task.cancel` →
  `cao:write`, `task.get`/stream → `cao:read`), returning 401/403 with JSON-RPC
  error bodies; a fail-closed guard that refuses to mount the transport on a
  non-loopback bind when auth is disabled; truthful docstrings.
- **Unbounded task store.** Size cap + TTL eviction on `InMemoryTaskStore`,
  `task.send` refused with `RESOURCE_EXHAUSTED` when full. Note the remote
  exploitability is conditional on the auth gap above plus a non-default
  `CAO_AGENT_CARD_HOST=0.0.0.0` bind; fixing auth removes the remote vector and
  the bound is defense-in-depth. Both ship together in the A2A PR.
- **Token-parse exceptions → 500.** Wrapped the SSE + WS token paths
  (`except Exception → 401` / close `4401`) with tests. Fails closed either way;
  this is telemetry hygiene.
- **Description ↔ code mismatch.** Correct — polecat/Cedar/WAL/swarm/cache never
  existed in the code; that was PR-description overselling. The body is rewritten
  to list only what the diff contains (and the deletion claim is removed — see
  the correction below).
- **Copilot five.** Removed the stray `tests/__init__.py`; mypy `python_version`
  → `3.10`; W3C Trace Context citation (was RFC 9114); `InstancePicker` a11y
  (sibling buttons, no nested interactive control); `test_headless_ci` docstring.
- **Assorted:** dated generative-UI doc folded into `docs/pwa.md`; OTel SDK +
  exporter moved to an `[otel]` extra (the lightweight `opentelemetry-api` stays
  core so the telemetry helpers import as no-ops); `_agui_enabled()` docstring
  tightened (the `CAO_MCP_APPS_ENABLED` interaction is intentional — shared event
  source); `?since=` endpoint test de-stubbed; access-log token scrubbing.

## Decomposition (taking @fanhongy up on the offer)

Two PRs along the verified/blocked boundary:

1. **AG-UI core + generative UI + PWA + `mock_cli` + opt-in OTel** — the subset
   the review verified as default-off, metadata-only, allow-list-enforced. Lands
   first, with the hardening above + a runnable live demo, an `agui-author`
   skill, and a live-path Playwright recording.
2. **A2A JSON-RPC + signed Agent Card** — held until the auth gating, store
   bounds, docstring corrections, and the per-method 401/403 test matrix are in.

## Corrections for the record (with evidence)

- **Scale:** this PR is **157 changed files (+16,288 / −119)**, not ~400.
  Still too big — hence the split — but the scope argument should rest on the
  real number. (A couple of cited line refs, e.g. `ci.yml:361`, don't exist on
  the branch, suggesting part of the pass ran against a stale checkout.)
- **Provider "deletion":** this PR **deletes nothing** — the diff is 117 added /
  40 modified / **0 deleted**. `q_cli`/`gemini_cli` were removed by **#353**,
  already in this PR's merge base; `main` has no such providers today. There's no
  `### Removed` entry for *this* PR's CHANGELOG to carry (that belongs to #353's
  notes; happy to backfill separately). **What this PR *does* contain — and no
  review caught — is the inverse:** it *adds*
  `examples/cross-provider/data_analyst_gemini_cli.md` targeting the nonexistent
  `gemini_cli` provider. That dead example is retargeted to `antigravity_cli`.
- **Inclusive language:** happy to honor the convention, but the flagged files
  (`audit_log.py`, `memory_scoring.py`, `memory_service.py`, `docs/memory.md`,
  `docs/mcp-apps.md`) are untouched by this diff and the terms pre-date it on
  `main`. Fixing what this PR introduces; the pre-existing ones go to a separate
  hygiene PR so they don't gate this stack.
- **`npm ci` vs `npm install`:** the workflows this PR adds use `npm ci`; the
  `npm install` occurrences are in untouched `ci.yml`.
- **JWT in the query string:** agreed it shouldn't hit access logs — scrubbing
  `access_token`/`ticket` from uvicorn's access log + documenting short TTLs.
  On the mechanism: browser `EventSource` can't set an `Authorization` header,
  so a query-param token (or a short-lived ticket, filed as a follow-up) is the
  standard SSE pattern; and the path is only reachable with auth enabled *and*
  the loopback default overridden.
- **`.coverage-baseline.json`:** intentional ratchet-floor config; a one-line
  header note is added so it isn't mistaken for a stray artifact.

## Why keep pushing on AG-UI

One standard surface over N heterogeneous CLI agents — Kiro CLI, Claude Code,
Codex rendering uniformly in any stock AG-UI client with zero adapter code —
backed by real tmux processes, metadata-only, with the whole protocol dependency
bounded to one pinned, default-off module. Your own verification confirmed those
properties hold. Splitting serves that goal: the verified core reaches users now,
and the A2A transport returns hardened.
