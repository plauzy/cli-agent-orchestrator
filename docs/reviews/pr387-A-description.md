<!--
DRAFT PR-A description — fork-only working copy. This is the proposed body for
the reshaped PR #387 (AG-UI core) once the maintainer approves landing it. It
describes ONLY what this branch's diff contains after the A2A/Agent-Card surface
was split out. Do not post upstream until approved.
-->

# feat: AG-UI protocol adapter + generative UI + dashboard PWA (#386)

Implements the **AG-UI (Agent–User Interaction) Protocol L1 adapter** proposed in
#386 — the read-only Phase 0–1 scope — plus the generative-UI producer and the
standalone dashboard that consume it. Everything here is **strictly additive and
default-off**: with no flags set, `cao-server` behaviour is byte-identical (no new
route responds, no new listener binds).

> **Scope note.** This is the decomposition the reviewers asked for. The A2A
> JSON-RPC transport + signed Agent Card listener that were bundled in the
> original PR are **split into a follow-up PR** and held until per-method auth is
> wired and the task store is bounded — they are not in this diff.

## What's in this PR

- **AG-UI typed-event stream** — `GET /agui/v1/stream` (SSE) maps CAO's
  normalized six-primitive fleet events to AG-UI typed events (`RUN_*`, `STEP_*`,
  `TEXT_MESSAGE_CONTENT`, `TOOL_CALL_*`, `STATE_SNAPSHOT`, `STATE_DELTA`,
  `GENERATIVE_UI`, `RUN_ERROR`), emits a `STATE_SNAPSHOT` on connect + RFC-6902
  `STATE_DELTA` patches thereafter, and supports `?since=` history replay.
  Default-off via `CAO_AGUI_ENABLED` (or the pre-existing `CAO_MCP_APPS_ENABLED`,
  since both surfaces share one in-process event source). Metadata-only by
  construction — message bodies never reach the wire.
- **Generative UI** — agents author a closed allow-list of named components
  (`approval_card`, `choice_prompt`, `diff_summary`, `progress`, `metric`,
  `agent_card`) with JSON props via the `emit_ui` MCP tool / `POST
  /agui/v1/emit_ui`. Validated server-side (no HTML/script/eval/iframe);
  off-list components are refused at the adapter, the React component, and the
  replay artifact. See [docs/pwa.md#generative-ui](../pwa.md#generative-ui).
- **Standalone dashboard PWA** (`cao_pwa/`) — consumes the AG-UI stream from any
  browser (no MCP host), auto-reconnects via `?since=`.
- **`mock_cli` provider** — credentials-free deterministic provider for CI.
- **OpenTelemetry GenAI instrumentation** — opt-in traces/metrics. The
  lightweight `opentelemetry-api` is in the base install (zero-overhead no-op
  when disabled); the SDK + OTLP exporter are an opt-in extra
  (`pip install cli-agent-orchestrator[otel]`).
- **WebSocket auth** on `/terminals/{id}/ws` (`cao.bearer.<jwt>` subprotocol,
  `4401`/`4403` close codes, read-only viewers' input dropped) — default-off
  preserves the byte-identical no-auth localhost contract.

## Hardening applied from the review

- **Token-parse failures fail closed cleanly.** Malformed/expired JWTs on the
  SSE `?access_token=` path now return `401` (not an opaque `500`); the WS scope
  extractor returns `None` → `4401` on any bad token. Tests added.
- **Query-token log hygiene.** `cao-server` installs a filter that scrubs
  `?access_token=` / `?ticket=` from uvicorn's access log (browser `EventSource`
  can't send an `Authorization` header, so a query token is the standard SSE
  pattern; the fix is not writing it to disk). Short-TTL guidance + a planned
  single-use ticket handshake are documented as a follow-up.
- **`?since=` replay** is now exercised end-to-end (the endpoint test no longer
  stubs the `since` boundary).
- **Docs/consistency:** `_agui_enabled()` documents the two intentional enable
  flags; the dated generative-UI design log is folded into `docs/pwa.md`; mypy
  `python_version` matches `requires-python` (`3.10`); W3C Trace Context is cited
  correctly (was RFC 9114); a nested-interactive-button a11y issue in the PWA is
  fixed; a stray second test root (`tests/`) is removed; and a cross-provider
  example that referenced the removed `gemini_cli` provider is retargeted to
  `antigravity_cli`.

## Testing

- Backend: the AG-UI adapter/endpoint/`emit_ui` suites pass, plus new
  malformed-token (SSE 401 / WS 4401), `?since=` include/exclude, `_agui_enabled`
  two-path, and access-log-redaction tests.
- Frontend: `cao_pwa` vitest suite (incl. the generative-UI safety-refusal
  assertions).
- Default-off regression: with no flags, `GET /agui/v1/stream` and
  `POST /agui/v1/emit_ui` → 404 and no extra listener binds.

## Follow-up PRs

1. **A2A JSON-RPC + signed Agent Card** — with per-method scope enforcement
   (`require_any_scope`), a fail-closed mount guard, a bounded task store, and
   the per-method 401/403 test matrix.
2. **Goodwill hygiene** (small, separate) — pre-existing inclusive-language terms
   (`whitelist` → `allowlist`, "Master switch" → "Primary switch"), the
   `deliver_pending()` doc references, a `### Removed` CHANGELOG backfill for
   #353, and a one-line note marking `.coverage-baseline.json` as ratchet config.
3. **Bidirectional generative UI**, **`STATE_DELTA` debounce**, and the
   **single-use ticket handshake** for the stream.

Implements #386 (read-only Phase 0–1).
