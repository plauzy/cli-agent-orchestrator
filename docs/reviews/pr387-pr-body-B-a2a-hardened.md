# PR-B — A2A v1.0 transport + signed Agent Card, hardened (follow-up to PR-A)

> Draft PR body for `reconcile/pr387-a2a-hardened` (#20). Reconciles
> `claude/pr387-a2a-hardened` and `kiro/pr387-a2a-hardened`; both source
> implementations contributed. Stacked on `f40933d`; carries **no** `pyproject`
> / `uv.lock` diff by design (dependency + doc hygiene rides PR-A). Open after
> PR-A merges, then rebase onto the new head (mechanical — no dep diff).

## What this PR does

Returns the A2A transport that was split out of the AG-UI core, with every
blocking review item from 4632216702 / @fanhongy / 4638092590 addressed.

- **Per-method auth on the JSON-RPC route** — scopes are resolved *before* the
  body is parsed, inside the `rpc()` handler (JSON-RPC multiplexes methods over
  one route, so auth must be per-method after parse). `task.send` / `task.cancel`
  require `cao:write`; `task.get` requires `cao:read`. Failures return JSON-RPC
  error objects with matching HTTP status: **401** (missing/invalid token),
  **403** (insufficient scope) — no auth failure tunneled through a 200. Stream
  and REST reads use FastAPI `Depends` scope guards.
- **Fail-closed mount guard** — if auth is disabled *and* the effective bind
  host is non-loopback, the A2A routers are refused (logged); loopback + no-auth
  stays allowed for dev ergonomics.
- **Bounded task store** — `InMemoryTaskStore` is capped (`max_tasks`, default
  1000, `CAO_A2A_MAX_TASKS`) and TTL-swept (`ttl_seconds`, default 3600,
  `CAO_A2A_TASK_TTL`). On overflow the oldest *terminal* tasks are evicted
  first; when every stored task is still live, a new insert raises
  `TaskStoreFull` → **`RESOURCE_EXHAUSTED` at HTTP 429 + `Retry-After`**.
- **Idempotent-create task ids** — `task.send` with an existing id is refused
  (`already exists`) rather than silently upserting; an omitted id no longer
  raises. Closes the task-id upsert-injection must-fix and the `Task.from_dict`
  `KeyError` nit from review 4638092590.
- **Truthful docstrings** — `rpc.py` / `stream.py` now describe the enforcement
  that actually exists (the prior "authentication is enforced via the JWKS"
  claim was false on unguarded routes).

## Two fixes from independent verification (this branch)

Found while re-running the gates; committed here as focused commits:

1. **`fix(agent-card)`** — `AgentCardListener.stop()` only set uvicorn's
   `should_exit`, but `Server.serve()` returns right after `startup()` (which
   binds `:9890`) when `should_exit` is already set, *skipping* `shutdown()`. A
   fast start→stop therefore leaked the listening socket until GC — surfacing as
   a deterministic `EADDRINUSE` in the mount-guard tests. `stop()` now closes the
   bound sockets explicitly so the port is released deterministically.
2. **`test(a2a)`** — the in-process round-trip drives two ASGI peers and needs no
   tmux, but the session-autouse `require_tmux` fixture skipped it wholesale on
   tmux-less hosts. Overriding `require_tmux` locally keeps the real-JWT
   round-trip actually executing (2 passed) instead of silently skipping.

## Gates (independently re-run on this branch, Python 3.10)

- `pytest`: **3609 passed, 21 skipped, 0 failed** (after fix #1; before it, one
  mount-guard test failed on the port leak)
- `mypy src/`: **no issues in 142 source files**
- `black --check .` / `isort --check-only .`: clean
- A2A e2e round-trip (`pytest test/e2e/test_a2a_roundtrip.py -m e2e`): **2
  passed** with real JWTs, in-process ASGI (no tmux required after fix #2)

## Load-bearing properties (verified in code, not just tests)

- `rpc.py` authenticates before body parse.
- Store-full → 429 + JSON-RPC `RESOURCE_EXHAUSTED` body + `Retry-After`.
- `task.send` refuses an existing id.
