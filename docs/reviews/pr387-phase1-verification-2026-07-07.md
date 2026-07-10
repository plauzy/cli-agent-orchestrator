# PR #387 — Phase-1 independent verification record (2026-07-07)

Independent re-run of every gate the handoff (`pr387-kiro-handoff.md`) claims,
executed by the finishing author on a clean checkout (uv-managed **Python
3.10.20**, Node **v22.22.3**). Numbers here are the ones any PR body or the
upstream reply may cite; anything not reproduced locally is marked as such.

## `reconcile/pr387-agui-core` (#19) — head `3712571`

| Gate | Result | Handoff claim | Match |
|---|---|---|---|
| `pytest` | 3537 passed / 22 skipped / 0 failed (87% cov) | 3,537 P / 22 S / 0 F | ✅ |
| `mypy src/` | no issues, 132 files | mypy 132 | ✅ |
| `black --check` / `isort --check-only` | clean | — | ✅ |
| `cao_pwa` `tsc --noEmit` | clean | — | ✅ |
| `cao_pwa` `vitest run` | 24/24 passed | vitest 24 | ✅ |
| `cao_pwa` `vite build` | OK (154 KB js / 49.7 KB gz) | — | ✅ |
| Live Playwright e2e + `showcase.sh` 6-frame gate | **not run** — no Chromium, Playwright CDN blocked | live spec green | ⏸ rely on CI `Build, test & record` |

Load-bearing properties (code-level): `import cli_agent_orchestrator.a2a` and
`.agent_card` both raise `ImportError` (split is clean); `cao_pwa/src/api.ts`
closes and reopens `EventSource` with the `?since=` cursor ("Always take over
reconnection").

## `reconcile/pr387-a2a-hardened` (#20) — head `2d6a550` + 2 verification fixes

| Gate | Result | Handoff claim | Match |
|---|---|---|---|
| `pytest` | 3609 passed / 21 skipped / 0 failed | 3,609 P / 21 S / 0 F | ✅ (after fix — see below) |
| `mypy src/` | no issues, 142 files | mypy 142 | ✅ |
| `black --check` / `isort --check-only` | clean | — | ✅ |
| A2A e2e round-trip (`-m e2e`) | 2 passed (real JWTs, in-process) | 2 passed | ✅ (after fix — see below) |

Load-bearing properties (code-level): `rpc.py` authenticates before body parse;
store-full → `RESOURCE_EXHAUSTED` @ HTTP 429 + `Retry-After`; `task.send`
refuses an existing id.

### Two defects found and fixed on this branch (focused commits)

1. **`:9890` listener socket leak.** `AgentCardListener.stop()` set uvicorn's
   `should_exit` only; `Server.serve()` early-returns after `startup()` (which
   binds the socket) when `should_exit` is already set, skipping `shutdown()`.
   Result: a fast start→stop leaks the port until GC — a deterministic
   `EADDRINUSE` failure of
   `test_a2a_mount_guard::test_loopback_bind_without_auth_still_mounts` in the
   full run. Fix: close the bound sockets explicitly in `stop()`. Restores the
   claimed **0 failures** (before: 1 failed / 3608 passed).
2. **Spurious tmux skip on the in-process round-trip.** `test_a2a_roundtrip.py`
   overrode `require_cao_server` / `warmup_mcp_server_cache` but not the
   session-autouse `require_tmux`, so a pure-ASGI test skipped on tmux-less
   hosts. Fix: add the matching `require_tmux` override → 2 skipped becomes 2
   passed.

Patches: `docs/reviews/pr387-a2a-fixes/000{1,2}-*.patch` (apply with `git am`
onto `reconcile/pr387-a2a-hardened` to preserve the Claude-authored,
`f40933d`-stacked lineage).

## Scope / scale (re-confirmed for the reply)

157 changed files (+16,288 / −119); 0 deletions in the diff (117 A / 40 M on the
combined bundle); `q_cli` / `gemini_cli` were removed upstream in #353 (in the
merge base), not by this PR. Consistent with `pr387-agui-response-draft-v2.md`.
