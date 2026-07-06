# PR #387 remediation — Kiro implementation notes (finding → resolution map)

Purpose: a navigable map of how this (Kiro-authored) implementation of the
PR #387 review remediation resolves each finding, for the head-to-head
comparison against the Claude-authored branches (`claude/pr387-agui-core`,
`claude/pr387-a2a-hardened`). Fork-only; not for the upstream CR.

## Branches (both stacked on the PR head `f40933d`, base `feat/agentic-protocols-generative-ui`)

| Branch | Shape | Base commit |
|---|---|---|
| `kiro/pr387-agui-core` | PR-A: A2A subtracted, accepted review fixes, + demos/skill/live-recording | `c2a0c9d` (reshape+hardening) + a 1C commit |
| `kiro/pr387-a2a-hardened` | PR-B: A2A/Agent-Card auth + bounded store + truthful docs + auth matrix | `a708259` |

## Blocking findings → resolution

| Finding | Where | Resolution |
|---|---|---|
| A2A auth bypass (anonymous `task.send` → 200 with auth on) | `a2a/rpc.py`, `a2a/stream.py`, `api/main.py` (PR-B) | Per-method scope enforced in the RPC handler before dispatch (`_authorize`): missing/invalid → 401 `UNAUTHENTICATED`, insufficient → 403 `PERMISSION_DENIED`; `task.send`/`task.cancel` → `cao:write`, `task.get` → `cao:read` (`cao:admin` any; write⇒read). Stream/REST reads gated by `Depends(require_any_scope)`. Fail-closed `_should_mount_a2a()` guard: non-loopback bind + auth off ⇒ transport not mounted (Agent Card still published). |
| Unbounded `InMemoryTaskStore` DoS | `a2a/store.py`, `a2a/types.py` (PR-B) | Bounded (`CAO_A2A_MAX_TASKS`, default 1000) + TTL-evicting (`CAO_A2A_TASK_TTL`, default 3600s); lazy sweep under the lock; evict oldest terminal first; full-of-live ⇒ `task.send` refused `RESOURCE_EXHAUSTED` (429). |

## Important findings → resolution (PR-A unless noted)

| Finding | Resolution |
|---|---|
| PR description oversells (polecat/Cedar/WAL/swarm/cache) | Doc-only: PR-A body lists only what the diff contains; claims removed. |
| Token-parse → opaque 500 | `api/main.py`: SSE `?access_token=` path wraps `extract_scopes_from_token` → clean 401; `_extract_ws_scopes` broadened to `except Exception → None` (→ 4401). Tests added. |
| JWT in query string → access logs | `utils/logging.py::RedactQueryTokenFilter` + `install_access_log_redaction()` masks `access_token`/`ticket` in uvicorn access logs; `docs/pwa.md` documents short TTLs + a ticket-handshake follow-up. |
| `?since=` endpoint test stubbed | `test/api/test_agui_stream_endpoint.py`: `_FakeLog.history` honors `since`; include/exclude assertions exercise the replay wiring. |
| `_agui_enabled()` wording | Docstring + `docs/pwa.md` state the intentional `CAO_MCP_APPS_ENABLED` shared-event-source path; parametrized both-paths test. |

## Rejected / corrected findings (with evidence)

| Finding | Verdict | Evidence |
|---|---|---|
| "PR deletes q_cli/gemini_cli; missing `### Removed`" | Reject — misattributed | `git diff --name-status f40933d…` = 0 deletions; removed upstream in #353 (in the merge base). Counter: PR-A *retargets* the newly-added dead `data_analyst_gemini_cli.md` → `antigravity_cli`. |
| Inclusive-language "introduced" | Reject attribution | flagged files untouched by the diff; terms pre-date on `main`. Fix rides a separate hygiene PR. |
| `npm install` in new CI job | Reject | new workflows use `npm ci`; `npm install` is in untouched `ci.yml`. |
| "~400 files" | Correct | 157 changed files. |

## Copilot five (PR-A)

`tests/__init__.py` removed; mypy `python_version` 3.11→3.10; RFC 9114 → W3C Trace
Context (`plugins/events.py`); `InstancePicker.tsx` nested-button a11y →
sibling buttons; `test_headless_ci.py` docstring.

## Kiro-specific decisions (differences worth weighing vs Claude)

1. **OTel deps (PR-A):** kept `opentelemetry-api` core (the span/context helpers
   import it eagerly via `main.py`), moved only the heavy **SDK + OTLP exporter**
   to an `[otel]` extra; hardened `init_telemetry` to no-op if the extra is
   absent. (Claude's branch may split all three — a legitimate contrast.)
2. **No `[a2a]` extra (PR-B):** `authlib`/`python-multipart` are **not imported
   by `src/`** (the Agent Card signer uses `cryptography` via `pyjwt[crypto]`),
   so no A2A runtime extra was invented — that would be a false claim. Dep
   hygiene (authlib→dev, drop multipart) rides PR-A. (Claude folds the dep
   hygiene into the A2A branch — reasonable either way.)
3. **Live proof:** `examples/agui-dashboard/showcase.sh` proves the live path
   **headlessly** (6× `emit_ui` 200 + `iframe` 400 + real `GENERATIVE_UI`
   frames) — runnable in this sandbox with no browser. The browser `.webm` is
   produced by the `live-dashboard` CI job; no canned/placeholder video is
   committed.
4. **Skill shipped:** `agui-author` added to `SHIPPED_SKILLS` so `cao init` seeds
   it; byte-identical two-tree mirror; parity tests pass.

## Verification (local)

- **PR-A:** black/isort clean; `mypy src/` Success; full non-e2e suite green
  (AG-UI + redaction + emit_ui + logging + a11y); `cao_pwa` tsc + vitest 18/18 +
  build; AC1 default-off probe 404/404; `showcase.sh` live PASS.
- **PR-B:** black/isort clean; `mypy src/` Success (142 files); 3596 passed / 21
  skipped incl. 28 new auth-matrix tests + 92 existing A2A/agent-card; default-off
  unchanged.
- Environment limits: Playwright Chromium CDN blocked (video is CI-only); `tmux`
  absent (A2A e2e roundtrip gated in-sandbox, runs in CI; the same auth path is
  fully covered by `test/a2a/test_auth.py` via `TestClient`).
