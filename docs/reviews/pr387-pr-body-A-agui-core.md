# PR-A — AG-UI protocol adapter + generative UI + standalone PWA (#386)

> Draft PR body for `reconcile/pr387-agui-core` (#19), and for upstream #387 at
> retarget time. Reconciles the two independent remediations of the #387 review
> (`claude/pr387-agui-core` and `kiro/pr387-agui-core`); see
> `docs/reviews/reconciliation-notes.md` for the per-change source map. Both
> source implementations contributed — credited neutrally there.

## What this PR does

This is the AG-UI **core** — the verified subset the collaborator asked to land
first (@fanhongy), with the A2A transport split out to a follow-up (PR-B,
`reconcile/pr387-a2a-hardened`).

- **AG-UI typed-event stream** — `GET /agui/v1/stream` (SSE) normalizes every
  CLI agent into the six-event AG-UI vocabulary. Metadata-only on the wire:
  message bodies and tool args are redacted by construction (asserted with a
  canary-secret test through both event shapes).
- **Generative UI** — the `emit_ui` MCP tool and `POST /agui/v1/emit_ui`, gated
  by a frozen component allow-list enforced at both the producer and adapter
  layers.
- **Standalone PWA** (`cao_pwa/`) — a stock `EventSource` client rendering the
  six components, with client-owned reconnection that resumes via `?since=`
  across dropped connections (native `EventSource` cannot resume, so `api.ts`
  closes and reopens with the cursor).
- **`mock_cli` provider** — deterministic provider used by the demo and CI.
- **Opt-in OpenTelemetry** — GenAI instrumentation behind the `[otel]` optional
  extra; absent the extra it degrades with an actionable warning (never a hard
  import error).
- **WebSocket auth** — `cao.bearer.<jwt>` subprotocol; close codes 4401
  (unauthenticated) / 4403 (insufficient scope). Token-parse failures map to
  401 (SSE) / 4401 (WS), and access logging is scrubbed of query-string
  credentials.
- **Review nits folded in** — the Copilot five (stray `tests/__init__.py`
  removed, mypy `python_version = "3.10"`, W3C Trace Context citation,
  `InstancePicker` nested-button restructure, `test_headless_ci` docstring), the
  dated generative-UI design log folded into `docs/pwa.md`, and the dead
  `data_analyst_gemini_cli.md` example retargeted to `antigravity_cli` (the
  provider `gemini_cli` was removed upstream in #353 and does not exist).

## Explicitly NOT in this PR

- **A2A v1.0 transport + signed Agent Card** — moved to PR-B, held until its
  auth gating, store bounds, and per-method 401/403 matrix land. No
  `src/.../a2a/` or `src/.../agent_card/` module is present here; importing
  either raises `ImportError`.
- No `authlib` / `python-multipart` dependency (those leave with PR-B).

## Default-off posture

With no env flags set, `GET /agui/v1/stream` and `POST /agui/v1/emit_ui` return
404, no extra listener binds, and the route table is byte-identical to `main`.
The stream is enabled by `CAO_AGUI_ENABLED` or, intentionally, by
`CAO_MCP_APPS_ENABLED` (the AG-UI SSE surface and the already-upstream MCP Apps
surface share one in-process event source — documented in `docs/pwa.md`).

## Gates (independently re-run on this branch, Python 3.10)

- `pytest`: **3537 passed, 22 skipped, 0 failed** (87% total coverage)
- `mypy src/`: **no issues in 132 source files**
- `black --check .` / `isort --check-only .`: clean
- `cao_pwa`: `tsc --noEmit` clean, **vitest 24/24**, `vite build` OK
- Live Playwright e2e (`npm run test:e2e:live`) + `showcase.sh` six-frame
  `GENERATIVE_UI` gate: green via the CI `Build, test & record` job (require a
  browser; not run in the reviewer sandbox).
