# Grounding Audit: AG-UI L2 Construct Spec vs. Source of Truth

> Audit date: 2026-07-17. Baseline audited: `spec/agui-l2-constructs` @ `ec89dfb`
> (requirements.md / design.md / tasks.md as committed in `aa5a40a`).
> Ground truth: **ag-ui main @ `b646b46`** (protocol source of truth) and
> **cli-agent-orchestrator main @ `1b00753`** (merged L1 from PR #436).
> Scope: issue awslabs/cli-agent-orchestrator **#458**.
> Re-audit: 2026-07-18 against ag-ui `3a7433e` / CAO `41c8ce7` — no cited surface
> changed; see the addendum at the end of this document.
>
> Verdicts: ✅ **Grounded** (claim matches code) · ❌ **Contradicted** (claim is
> wrong vs. code) · ⚠️ **Gap** (real prerequisite the spec does not cover) ·
> 🔧 **Reframed** (claim needs re-anchoring to what actually exists).

## Headline findings (what changed in the revision)

### F1 — ❌→🔧 AG-UI *does* define an interrupt lifecycle on main — and the spec doesn't use it

The audited design treats "AG-UI's interrupt lifecycle" as a CAO-local invention
(an `Interrupt` dataclass + `approval_card` generative-UI frames + a bespoke REST
resume route). As of ag-ui main, interrupts are **first-class protocol surface**:

- `RunFinishedEvent.outcome: {type:"interrupt", interrupts: Interrupt[]}` —
  `sdks/typescript/packages/core/src/events.ts:233-262`, `sdks/python/ag_ui/core/events.py:276-291`.
- `Interrupt = {id, reason, message?, toolCallId?, responseSchema?, expiresAt?, metadata?}` —
  `core/src/types.ts:193-201`.
- Resumption via `RunAgentInput.resume: [{interruptId, status: "resolved"|"cancelled", payload?}]` —
  `core/src/types.ts:203-219`.
- Client support: `AbstractAgent.pendingInterrupts`, resume-coverage validation,
  `buildResumeArray` — `client/src/agent/agent.ts:61-64,396-412`.
- **Custom reasons are namespaced `<framework>:<name>`** (`docs/concepts/interrupts.mdx:159-183`,
  `core:` reserved) — the issue's `claude-code:permission_request` scheme is the
  documented convention, verbatim.
- Approve-with-edits payload convention `{approved: boolean, editedArgs?}` —
  `interrupts.mdx:185-219`; capability flags `humanInTheLoop.interrupts` /
  `humanInTheLoop.approveWithEdits` (`core/src/capabilities.ts:189-207`).

The lifecycle is **run-scoped**: interrupts ride on `RUN_FINISHED` and resume rides
on the next `RunAgentInput`. CAO's ambient `GET /agui/v1/stream` has no
`RunAgentInput` round-trip, so honouring "#458: map prompts onto AG-UI's interrupt
lifecycle" requires the protocol-plane run endpoint (F2). **Revision**: keep the
thin REST resume route as the simple browser path, and additionally carry the
*real* interrupt lifecycle (outcome/resume, namespaced reasons, approve-with-edits
payloads) on the new `POST /agui/v1/run` plane. Both paths converge on one
idempotent resolution.

### F2 — ❌ A stock AG-UI client cannot consume `GET /agui/v1/stream`; the AC3 demo as specified is unimplementable

The audited Requirement 12 points "an unmodified upstream AG-UI client (Dojo /
CopilotKit)" at `/agui/v1/stream` with "zero adapter code". Ground truth says no
stock client can parse that stream, for three independent reasons:

1. **Framing**: the stock SSE parser processes only `data:` lines and explicitly
   ignores `event:`, `id:`, and `retry:` fields (`client/src/transform/sse.ts:5-12,66-89`).
   CAO puts the event type in the SSE `event:` line and omits it from the payload
   (`api/main.py:966-970`), so every frame is invisible or unparseable.
2. **Payload shape**: wire JSON must be camelCase and carry `type`
   (`EventSchemas.parse`, `transform/http.ts:33-81`; Python models dump
   `by_alias=True` — `ag_ui/encoder/encoder.py:9-32`). CAO payloads are snake_case
   with no `type` field (`services/agui_stream.py:113-211`).
3. **Transport direction**: `HttpAgent` only issues `POST` with a `RunAgentInput`
   body (`client/src/agent/http.ts:14-84`); it never opens a bare GET stream.
   PR #436's own description concedes this ("run-endpoint shim … rewrites CAO's
   named SSE frames into the stock AG-UI wire format").

Additionally the stream is not lifecycle-legal for the client verifier
(`client/src/verify/verify.ts`): bare `TEXT_MESSAGE_CONTENT` without START/END,
`TOOL_CALL_START` without END, events outside an active run, and the non-spec
`GENERATIVE_UI` type would all error. **Revision**: add a protocol-faithful
`POST /agui/v1/run` endpoint (server-side, default-off, same gating) that speaks
the stock wire dialect and is lifecycle-legal; the stock-client demo targets it.
The ambient stream stays as-is (documented as the CAO dialect for CAO-aware
consumers, which is what the L2 folding constructs are).

### F3 — ❌ Event ids are uuid4, not monotonic; `?since=` is a timestamp, not an id cursor

The audited Requirement 7 mandates "a monotonically-ordered `id` cursor" and
client dedup by "skip frames whose `id` is ≤ the highest `id` already applied".
Ground truth: `EventLog` ids are `str(uuid.uuid4())` (`services/event_log_service.py:64-71`)
— unordered — and `?since=` is an **ISO-8601 timestamp**, exclusive lower bound
(`api/main.py:862-869`), while the id cursor travels as `Last-Event-ID`
(`after_id`, over-delivering when the id is unknown/evicted,
`event_log_service.py:150-178`). `?since=` beats `Last-Event-ID` when both are
present (`api/main.py:996-999`). **Revision**: the dedup contract is a
**seen-id-set**, never an ordering comparison; requirements rewritten accordingly.

### F4 — ❌ STATE frames carry no `id:` and need no dedup; snapshot-then-delta is already torn-proof per connection

The audited Requirements 4.4/7.3/11.4 demand event-id dedup of `STATE_DELTA`
frames and "exactly one STATE_SNAPSHOT before any subsequent STATE_DELTA" as new
work. Ground truth: state frames are synthesized per connection *after* replay —
snapshot first, then per-event recomputed deltas (`api/main.py:1010-1049`) — and
carry no `id:` (`main.py:1017,1046`). The state channel cannot tear and cannot
duplicate across a reconnect by construction; only id-bearing event frames need
the seen-set. **Revision**: requirements now separate the two channels; the
snapshot-then-delta ordering is asserted as a preserved invariant (regression
test), not built.

### F5 — ❌ `TOOL_CALL_START` today fires only for `a2a_delegation` — a kind with **no producer**; all real traffic normalizes to `handoff`

Ground truth: `normalize_kind` maps `post_send_message` to `a2a_delegation` only
when `orchestration_type` contains `"a2a"` — and no producer ever sets that;
`handoff`, `assign`, and `send_message` all arrive as kind `handoff`
(`services/event_primitives.py:40-72`, grep-verified no `a2a` producer). The
audited timeline keys delegations off `TOOL_CALL_START` frames that never occur
in practice, and treats **every** `TEXT_MESSAGE_CONTENT` as a handoff.
**Revision**: Cleanup A discriminates by `detail.orchestration_type` — `handoff`
/ `assign` dispatches map to `TOOL_CALL_START` (+ correlated `TOOL_CALL_END`),
`send_message` stays `TEXT_MESSAGE_CONTENT` (message delivery, metadata-only) —
exactly matching the already-published mapping table in `docs/agui.md:33-41`
("handoff / delegation → TOOL_CALL_START / TOOL_CALL_END"; "message delivery →
TEXT_MESSAGE_CONTENT"). The timeline folds both, discriminated by
`tool_call_name` / `orchestration_type` metadata.

### F6 — ⚠️ Nothing publishes `WAITING_USER_ANSWER` onto the fleet stream; the approval construct has no trigger without a new bridge

Status transitions live only on the internal EventBus topic `terminal.{id}.status`
(`services/status_monitor.py:222`) and never reach `EventLog`/AG-UI. The audited
design's sequence diagram assumes "StatusMonitor → AgentHandoffWithApproval" but
no task creates that wiring, no component owns prompt-context capture, and
nothing detects the prompt disappearing. **Revision**: a new server-side
`ApprovalBridge` (EventBus subscriber, registered in the FastAPI lifespan behind
the AG-UI flag) triggers `on_provider_waiting` / expiry, and is an explicit
requirement + task.

### F7 — ⚠️ CAO launches providers in auto-approve mode; a "real provider permission prompt" needs a deliberate approval-mode launch

`claude_code` launches with `--dangerously-skip-permissions` unless the agent
profile sets `permissionMode` (`providers/claude_code.py:219-240`), kiro_cli with
`--trust-all-tools` (`kiro_cli.py:267-302`), codex with `--yolo`
(`codex.py:256-276`), and startup trust prompts are auto-answered. The audited
spec never mentions this, so its AC5 exit gate cannot be exercised as written.
**Revision**: the approval example ships an approval-mode agent profile (e.g.
claude_code with `permissionMode` unset-to-default) and documents the live
procedure; CI uses a `mock_cli` scripted-prompt extension (mock_cli today never
returns `WAITING_USER_ANSWER` — `providers/mock_cli.py:79-96`).

### F8 — 🔧 "Any ordering consistent with per-key causal order" over RFC-6902 ops is not a sound convergence claim

JSON Patch application is order-sensitive; the stream is a single totally-ordered
sequence per connection (snapshot, then deltas diffed against the previous
snapshot — `ui_state_service.diff_snapshot` with whole-key replace for
`sessions`/`terminals`, per-key for `counts`/`scopes`). **Revision**: the
convergence property quantifies over **the ordered fold** (with reconnect
overlap/dedup), asserting deep-equality with `build_dashboard_snapshot` of the
same fleet — matching what the wire actually guarantees. Patch application is
atomic apply-else-drop, mirroring the stock client (`fast-json-patch` with
`validate=true`; on failure warn + drop, run continues —
`client/src/apply/default.ts:537-568`).

## Secondary findings

| # | Verdict | Audited claim | Ground truth | Resolution |
|---|---|---|---|---|
| F9 | ✅ | `?since=`/`Last-Event-ID` replay, register-before-replay, server-side overlap dedup already exist | `api/main.py:972-1008`; tests `test/api/test_agui_stream_reconnect.py`, `test_agui_stream_overflow.py` | Cleanup B is documentation + a 400 on malformed `?since=` (today a bad cursor is silently swallowed by the failure-isolated replay block, `main.py:994-1008`) + the client-side seen-set contract |
| F10 | ✅ | Allow-list, 8 KiB props cap, `ValueError`/400 refusal parity | `GENERATIVE_UI_COMPONENTS` (6 components incl. `approval_card`) `services/agui_stream.py:89-98`; `_MAX_GENERATIVE_PROPS_BYTES = 8*1024` (:102); HTTP 400s `api/main.py:1085-1103` | Kept verbatim; `approval_card` needs **no** allow-list change |
| F11 | ✅ | `cao:write` scope guard for resume parity with `emit_ui` | `require_any_scope(SCOPE_WRITE, SCOPE_ADMIN)` on emit (`main.py:1068`); scopes in `security/auth.py` | Kept |
| F12 | ✅ | `WAITING_USER_ANSWER` status + programmatic answer path exist | `TerminalStatus` `models/terminal.py:13-21`; `answer_user_prompt` `mcp_server/server.py:1243-1258` → `POST /terminals/{id}/input` (`main.py:1659`) and `/key` (`main.py:1693`, keys `Up/Down/Enter/y/n/t…`) | Resume reuses these exact paths; keystroke tables per provider grounded in `claude_code.py:79-83`, `kiro_cli.py:123-126,183`, `codex.py:60,80` |
| F13 | ❌ | "Timeline cap 1,000 mirrors `RING_CAPACITY`" | `RING_CAPACITY = 500` (`event_log_service.py:23`) | Cap is the construct's own documented bound (default 1,000, configurable); no false mirroring claim |
| F14 | ❌ | Interrupt `id` "== originating event id" but pseudocode uses `newId()` | Internal inconsistency in the audited design | Interrupt id = fresh uuid4; originating event id kept in `metadata` |
| F15 | 🔧 | Expiry path "invokes `send_input` at most once" | Sending keystrokes to a terminal that already left `WAITING_USER_ANSWER` types into a live agent session | Expiry sends **zero** keystrokes; only a resume that loses the race gets the recorded `expired` outcome |
| F16 | 🔧 | Per-provider counts "scoped to Supported_Providers" | Snapshot terminals carry `provider` for **all** providers (`ui_state_service.py:81-95`); CAO has 10 provider ids (`models/provider.py:4-17`) | Rollups count every observed provider; the ≥3-provider *validation* asserts coverage of `kiro_cli`/`claude_code`/`codex` |
| F17 | ✅ | Hypothesis property tests "match the existing suite" | `hypothesis>=6.0` already a dev dependency (`pyproject.toml:116`) | Kept |
| F18 | ⚠️ | Constructs "never open sockets" — but every example then hand-rolls SSE parsing | The audited examples call an undefined `client_frames()` | L2 ships one sanctioned `AguiStreamReader` (stdlib/`requests`-based, `since`/`Last-Event-ID` aware) so app authors never re-derive the wire; constructs themselves stay pure |
| F19 | ⚠️ | No statement of who instantiates/feeds server-side constructs | Routes are flat `@app` decorators; state must be app-scoped (`api/main.py`, lifespan :476-597) | Approval registry + bridge are lifespan-owned singletons behind the flag; wiring is an explicit task |
| F20 | 🔧 | Edit text "≤ 8 KiB serialized" | Existing answer path caps at 4,000 chars (`mcp_server/server.py:49`) | Edit text cap aligned to 4,000 chars for parity with `answer_user_prompt` |
| F21 | ⚠️ | Reconnect/replay treated as an AG-UI feature | No AG-UI SDK implements resumption: Python encoder emits no `id:` (`encoder.py:24-32`); TS parser ignores `id:`; `TransportCapabilities.resumable` is a flag with no implementation | `?since=`/`Last-Event-ID` documented as a **CAO extension** consumed by CAO-aware clients (the constructs); protocol-plane recovery is snapshot re-sync, per `docs/concepts/state.mdx:47-56` |
| F22 | 🔧 | `kiro:trust_prompt` as kiro's primary reason | Kiro's detected prompts are permission gates (`Allow this action? [y/n/t]`, TUI `Yes / No / Always allow` — `kiro_cli.py:123-126,183`) | Closed sets per provider: `claude-code:{permission_request,trust_prompt}`, `kiro:{permission_request,trust_prompt}`, `codex:{approval_request,trust_prompt}`, `{ns}:unknown_prompt` default |

## What the audited spec got right (preserved)

- The **L2 contract** (constructs fold frames / write only through the emit path;
  no new SSE plumbing per construct) — sound and kept.
- **Emit refusal parity** (allow-list, JSON-serializability, 8 KiB, refuse-before-
  publish, props never mutated) — grounded and kept verbatim.
- **Privacy boundary through L2** (`assert_no_body`, no `delta` storage, metadata-
  only projections) — kept; matches the shipped privacy tests.
- **EARS requirement style, property-based testing with Hypothesis, run.sh /
  showcase.sh example convention, default-off gating** — all kept.
- Module placement `services/agui/`, tests under `test/services/agui/` +
  `test/api/` — kept.

## Source-of-truth reference pins

| Fact | Where |
|---|---|
| AG-UI EventType enum (33 values, TS = Py) | `ag-ui/sdks/typescript/packages/core/src/events.ts:12-61`; `ag-ui/sdks/python/ag_ui/core/events.py:42-78` |
| Interrupt lifecycle spec | `ag-ui/docs/concepts/interrupts.mdx` (rules :112-133; state-before-finish :135-145; reasons :159-183; tool-bound + editedArgs :185-219) |
| Stock client transport | `client/src/agent/http.ts:14-84` (POST-only); `client/src/transform/sse.ts:5-12,66-89` (`data:`-only parsing) |
| Lifecycle legality rules | `client/src/verify/verify.ts` (RUN_STARTED first :67-71; no events after finish :52-64; START/END bracketing :92-193; no finish with open entities :228-263) |
| Python encoder framing | `ag-ui/sdks/python/ag_ui/encoder/encoder.py:9-32` (`data:` only, camelCase `by_alias`) |
| State delta client semantics | `client/src/apply/default.ts:537-568` (atomic apply-else-drop) |
| CAO six-kind vocabulary + normalization | `services/event_primitives.py:23-72` |
| CAO adapter mapping | `services/agui_stream.py:108-211` |
| CAO stream endpoint (replay/snapshot/delta) | `api/main.py:860-1053` |
| CAO status detection + answer paths | `services/status_monitor.py`, `providers/{claude_code,kiro_cli,codex}.py`, `mcp_server/server.py:319-429,1243-1258`, `api/main.py:1659-1719` |

## Re-audit addendum (2026-07-18) — pins refreshed to ag-ui `3a7433e` / CAO `41c8ce7`

Both fork mains advanced after the original audit; every file in each delta was
compared against the claims above.

**ag-ui `b646b46..3a7433e`** (5 commits): GitHub-Actions chores (`094c6da`,
`bc0a2c1`); `3b370a5` fix(security) — integration **example servers** no longer
combine `allow_credentials=True` with a wildcard CORS origin (adk, aws-strands,
claude-agent-sdk, langroid; new `CORS_ALLOW_ORIGINS` env pattern, credentials only
for explicit non-wildcard origins); `691dae8` — langroid registers `/health` at the
root path. **No change** to the core event schemas, the client
(verify/sse/http/apply), the encoder, `docs/concepts/*`, CONTRIBUTING.md,
`apps/dojo/*`, or `render.yaml` — every F1–F22 pin above remains valid verbatim at
`3a7433e`.

**CAO `1b00753..41c8ce7`** (3 commits): `a614f32` (inline jinja autoescape),
`8b552bb` (run_agent_step inherits the supervisor working directory server-side),
`41c8ce7` (CodeQL path-guard colocation) — touching `agent_scaffold.py`,
`agent_step.py`, `workflow_spec_service.py`, and tests only. **No change** to
`services/agui_stream.py`, the `/agui/v1/*` routes,
`event_log_service`/`sse_bus`/`event_primitives`/`ui_state_service`, the providers'
status patterns, `emit_ui`, `terminal_service.send_input`, or `docs/agui.md`.
`8b552bb` alters handoff *working-directory* semantics only — no effect on the
event mapping, statuses, or approval paths this spec relies on. CAO's own CORS
remains an explicit-origin list + credentials (`constants.py:310-319`,
`api/main.py:644-650`) — not the wildcard pattern upstream fixed.

**Spec deltas applied in this re-audit:** grounding pins refreshed across all spec
documents; the dojo example-server design adopts the two new upstream conventions
(no credentialed wildcard CORS via the `CORS_ALLOW_ORIGINS` pattern; `/health` at
the root path).
