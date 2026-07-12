# PR #387 — follow-up issues to file

The upstream reply (`pr387-agui-response-draft-v2.md`) commits to four
follow-ups. Ready-to-file issue bodies below; open them against
`awslabs/cli-agent-orchestrator` after PR-A merges and reference #386 / #387.

---

## 1. AG-UI stream: short-lived single-use ticket handshake

**Labels:** `enhancement`, `security`, `agui`

**Context.** `GET /agui/v1/stream` accepts the bearer token as a query parameter
because browser `EventSource` cannot set an `Authorization` header. PR-A scrubs
the token from access logs and recommends short TTLs, but the token still
appears in the URL. Reviewer @gutosantos82 (review 4632216702, item I2) flagged
this; we agreed the query-param pattern is the standard SSE workaround and
committed to a follow-up rather than blocking the core.

**Proposal.** Add a `POST /agui/v1/ticket` endpoint that authenticates with a
normal `Authorization` header and returns a single-use, short-lived (~30 s)
ticket. The stream then accepts `?ticket=<id>` instead of `?access_token=<jwt>`.
The ticket is consumed on first `EventSource` connect and cannot be replayed.

**Acceptance.** Ticket mints only with a valid bearer + `cao:read`; is single-use
and TTL-bounded; `?access_token=` remains supported (deprecated) for one release;
tests cover mint → connect → reuse-rejected and expiry.

---

## 2. AG-UI: `STATE_DELTA` debounce

**Labels:** `enhancement`, `performance`, `agui`

**Context.** Rapid backend state changes currently emit one `STATE_DELTA` per
change. Under bursty activity (many agents, fast tool loops) this can flood the
SSE stream and the client.

**Proposal.** Coalesce `STATE_DELTA` events within a small window (e.g. 50–100 ms)
into a single merged delta before emission, configurable via env. Preserve
ordering and last-writer-wins semantics per key.

**Acceptance.** A burst of N deltas within the window emits ≤1 merged event; the
merged delta is equivalent to applying the N deltas in order; debounce window is
configurable; a test asserts the coalescing boundary.

---

## 3. Generative UI: `emit_ui` rate limiting

**Labels:** `enhancement`, `security`, `agui`

**Context.** `emit_ui` (MCP tool + `POST /agui/v1/emit_ui`) lets a producer push
UI components onto the stream. There is no per-producer rate limit, so a
misbehaving or hostile producer could flood connected clients.

**Proposal.** Add a per-producer / per-connection token-bucket rate limit on
`emit_ui`, returning a clear throttling error (HTTP 429 for the REST path) when
exceeded. Defaults tunable via env.

**Acceptance.** Emits above the configured rate are rejected with 429 +
`Retry-After`; within-limit emits are unaffected; the allow-list refusal path is
unchanged; tests cover the throttle boundary and the 429 body.

---

## 4. Test hygiene: fixed-path `term-42.mcp.json` race

**Labels:** `test`, `flaky`, `tech-debt`

**Context.** A test writes/reads a fixed-path `term-42.mcp.json`. On parallel or
repeated runs this shared path can race, producing intermittent failures. Noted
during the #387 review cycle; deferred out of the core PR.

**Proposal.** Use a per-test temporary path (`tmp_path` fixture) or a unique
terminal id per test instead of the fixed `term-42` name, so runs are isolated.

**Acceptance.** No test depends on a fixed shared MCP-config path; the affected
test passes under `pytest -p xdist -n auto` / repeated runs without flakiness.

---

> Note: the two defects found during Phase-1 verification (the `:9890` listener
> socket leak and the tmux-gated in-process round-trip) are **already fixed** on
> `reconcile/pr387-a2a-hardened` — they do not need issues.
