# Requirements Document

## Introduction

This document specifies the requirements for **AG-UI Phase 2 — the L2 construct
library** (tracking issue awslabs/cli-agent-orchestrator #458). It supersedes the
initial draft after a grounding audit against **ag-ui main** (the protocol source of
truth) and **cli-agent-orchestrator main** (the merged L1 from PR #436); see
`audit.md` in this spec directory for finding-by-finding evidence.

The feature adds a small library of named, subclassable **L2 constructs** layered over
the already-merged **L1 AG-UI adapter**. Three constructs are pure folds over the
existing CAO AG-UI stream (`GET /agui/v1/stream`); one is a server-resident
human-in-the-loop construct wired to provider status transitions. The feature also
owns the **L1 cleanups** from #458 — completing the `TOOL_CALL_*` lifecycle,
hardening/documenting the replay contract — plus the piece the audit showed both the
stock-client demo (AC3) and the protocol interrupt mapping (AC5) require: a
**protocol-faithful run plane** (`POST /agui/v1/run`) that speaks the exact AG-UI wire
dialect stock clients implement, including the interrupt lifecycle
(`RUN_FINISHED.outcome` + `RunAgentInput.resume`) now first-class on ag-ui main.

**Out of scope (explicitly):** the Phase 3 / L3 reference dashboard application,
authenticated *team* mode, the AG-UI Dojo ecosystem listing, and A2A / Agent Card /
ACP protocol modules.

## Glossary

- **L1_Adapter**: the merged AG-UI adapter (`services/agui_stream.py`) mapping CAO's
  normalized event primitives to AG-UI-typed `(type, data)` frames.
- **Ambient_Stream**: the L1 endpoint `GET /agui/v1/stream` — CAO's AG-UI **dialect**
  (named SSE events with `id:` cursors, snake_case payloads, the non-spec
  `GENERATIVE_UI` type), consumed by CAO-aware clients and the L2 folding constructs.
- **Run_Plane**: the new endpoint `POST /agui/v1/run` — the **stock** AG-UI wire
  dialect (camelCase `data:`-only SSE, `type` in the payload, lifecycle-legal event
  ordering), consumed by unmodified AG-UI clients.
- **Emit_Path**: the L1 write surface (`POST /agui/v1/emit_ui` and its equivalent
  in-process event-log publish), subject to allow-list and size validation.
- **AguiConstruct**: the abstract base class for all L2 constructs; owns the single
  read seam (`handle_frame`) and single write seam (`emit`).
- **Stream_Reader**: `AguiStreamReader`, the one sanctioned L2 client utility that
  connects to the Ambient_Stream and yields `(event_id, agui_type, data)` frames,
  supporting `?since=` and `Last-Event-ID`.
- **Approval_Bridge**: the server-side component subscribing to internal
  `terminal.*.status` transitions and driving AgentHandoffWithApproval.
- **Interrupt**: the approval-lifecycle record aligned to ag-ui main's `Interrupt`
  type (`{id, reason, message, toolCallId?, responseSchema?, expiresAt?, metadata}`),
  with CAO states `open → resolved(outcome)`.
- **Reason_Classifier**: the total function `classify_reason(provider, raw_prompt)`
  returning a provider-namespaced reason string `<namespace>:<local_name>`.
- **Resume_Endpoint**: `POST /agui/v1/interrupts/{id}/resume`, the thin REST decision
  route (browser-simple path); the Run_Plane's `resume[]` is the protocol path.
- **Projection**: a JSON-serializable, metadata-only view a construct folds from frames.
- **Metadata_Only_Boundary**: the L1 privacy invariant — no message body, delta text,
  or terminal stdout on the wire or in any projection.
- **Seen_Set_Dedup**: the replay dedup contract — event ids are uuid4 (unordered);
  consumers skip a frame iff its id is already in the set of applied ids.
- **Supported_Providers**: `kiro_cli`, `claude_code`, `codex` (validation targets;
  constructs remain provider-agnostic).
- **Stock_Client**: an unmodified upstream AG-UI client (`@ag-ui/client` HttpAgent /
  CopilotKit / AG-UI Dojo) containing zero CAO-specific adapter, translation, or
  wire-decoding source.
- **AC5_Exit_Gate**: the acceptance gate defined in Requirement 15.

## Requirements

### Requirement 1: Subclassable base construct with single read and write seams

**User Story:** As an application author, I want a subclassable base construct that
owns the composition seam to L1, so that I implement domain folding without writing
any SSE wiring.

#### Acceptance Criteria

1. THE AguiConstruct SHALL expose exactly one read seam, `handle_frame(agui_type, data, event_id=None)`, through which every subclass receives AG-UI frames.
2. THE AguiConstruct SHALL expose exactly one write seam, `emit(component, props, terminal_id=None, session_name=None)`, that routes every published intent exclusively through the Emit_Path.
3. IF `handle_frame` receives a frame whose `agui_type` is not one the construct recognizes, THEN THE AguiConstruct SHALL leave the current projection unchanged and SHALL return without raising an exception.
4. THE AguiConstruct SHALL provide a `projection()` accessor that returns a JSON-serializable value and completes without raising an exception.
5. THE AguiConstruct SHALL NOT open a socket, add a route, or serialize SSE framing; the only L2 component that reads the wire SHALL be the Stream_Reader.
6. THE Stream_Reader SHALL connect to the Ambient_Stream, yield `(event_id, agui_type, data)` tuples, forward a caller-supplied `since` timestamp or `Last-Event-ID` cursor, and expose the last-seen event id so a caller can resume.
7. WHERE a construct is configured with a test emitter in place of a production emitter, THE AguiConstruct SHALL record each intent (`component`, `props`, `terminal_id`, `session_name`) and SHALL publish nothing through the Emit_Path.
8. THE production emitter SHALL exist in two interchangeable forms with identical validation: an in-process emitter (event-log append + bus publish, the same path `POST /agui/v1/emit_ui` uses) and an HTTP emitter (POSTing to `/agui/v1/emit_ui`).
9. WHILE the AG-UI surface is disabled, THE production emitter SHALL refuse `emit` calls with an error and SHALL publish nothing.

### Requirement 2: Emit refusal parity with the L1 emit surface

**User Story:** As a platform maintainer, I want the L2 write seam to enforce the same
validation as `emit_ui`, so that no construct can bypass the L1 safety guards.

#### Acceptance Criteria

1. WHEN `emit` is called with a `component` on the L1 generative-UI allow-list AND `props` that are JSON-serializable AND whose UTF-8-encoded JSON serialization is at most 8192 bytes, THE AguiConstruct SHALL publish exactly one intent through the Emit_Path.
2. IF `emit` is called with a `component` not on the L1 allow-list, THEN THE AguiConstruct SHALL refuse by raising `ValueError` and SHALL publish nothing.
3. IF `emit` is called with `props` that are not JSON-serializable, THEN THE AguiConstruct SHALL refuse by raising `ValueError` and SHALL publish nothing.
4. IF `emit` is called with `props` whose UTF-8-encoded JSON serialization exceeds 8192 bytes, THEN THE AguiConstruct SHALL refuse by raising `ValueError` and SHALL publish nothing.
5. WHEN `emit` is called, THE AguiConstruct SHALL leave the caller-supplied `props` mapping unmutated on both the publish and refusal paths.
6. THE AguiConstruct SHALL source the allow-list and size limit from the existing L1 constants (`GENERATIVE_UI_COMPONENTS`, the 8192-byte cap) and SHALL NOT duplicate the component set.

### Requirement 3: Metadata-only privacy boundary preserved through L2

**User Story:** As a security reviewer, I want the L1 privacy boundary preserved
through every construct, so that message bodies and terminal output never reach the
wire.

#### Acceptance Criteria

1. THE AguiConstruct SHALL ensure that every value returned by `projection()` contains no message-body field (message delta text, terminal stdout, or assistant message content).
2. WHEN any construct emits an intent, THE AguiConstruct SHALL ensure the emitted intent contains no message-body field.
3. WHEN a construct folds a `TEXT_MESSAGE_CONTENT` frame, THE construct SHALL NOT store the frame's `delta` value in its projection.
4. WHEN `assert_no_body(data)` is invoked with a frame carrying no message-body field, THE AguiConstruct SHALL return without raising.
5. IF `assert_no_body(data)` is invoked with a frame carrying a message-body field, THEN THE AguiConstruct SHALL raise, leave the projection unchanged, and publish nothing.

### Requirement 4: Supervisor dashboard projection from L1 state frames

**User Story:** As a supervisor operator, I want a folded session→terminal hierarchy
and a rolling supervisor snapshot, so that I can monitor the fleet without re-deriving
the wire protocol.

#### Acceptance Criteria

1. WHEN SupervisorDashboardStream receives a `STATE_SNAPSHOT` frame, THE SupervisorDashboardStream SHALL replace its projection with a deep copy of the snapshot contents.
2. WHEN SupervisorDashboardStream receives a `STATE_DELTA` frame, THE SupervisorDashboardStream SHALL apply the frame's RFC 6902 ops to its current projection atomically and in order.
3. IF a `STATE_DELTA` arrives before any `STATE_SNAPSHOT` baseline, OR its ops fail strict RFC 6902 application, THEN THE SupervisorDashboardStream SHALL leave the projection unchanged and return without raising (matching the stock client's apply-else-drop behavior).
4. WHEN folding id-bearing event frames across a reconnect replay, THE SupervisorDashboardStream SHALL apply Seen_Set_Dedup so that no id-bearing frame is folded twice; state frames (which carry no id and are synthesized per connection) SHALL be folded as received.
5. THE SupervisorDashboardStream SHALL expose a `hierarchy()` view mapping each session name to its status, its terminal-id list, and its terminal count, derived solely from folded frames.
6. THE SupervisorDashboardStream SHALL expose a `supervisor_snapshot()` rollup containing: active-session count (folded status not `terminated`), total session/terminal counts, per-provider terminal counts covering **every** provider observed in folded frames, the ids of terminals whose folded status is `waiting_user_answer`, and last-activity as the `(timestamp, event_id)` of the most recently folded frame.
7. THE SupervisorDashboardStream SHALL derive every projection field solely from folded frames and SHALL NOT fetch from any data source of its own.

### Requirement 5: Multi-agent handoff and delegation timeline

**User Story:** As a supervisor operator, I want a causally-ordered timeline of
handoffs, assignments, and message deliveries, so that I can follow how work moves
between agents.

#### Acceptance Criteria

1. WHEN MultiAgentSessionTimeline receives a `TOOL_CALL_START` frame whose `tool_call_id` matches no open entry, THE MultiAgentSessionTimeline SHALL append a delegation entry with status `open`, keyed by `tool_call_id`, recording `tool_call_name`, sender/receiver metadata, and `started_at` from the frame.
2. WHEN MultiAgentSessionTimeline receives a `TOOL_CALL_END` or `TOOL_CALL_RESULT` frame whose `tool_call_id` matches an open entry, THE MultiAgentSessionTimeline SHALL set that entry's status to `completed` (or `failed` when the frame carries a failure disposition) and record `ended_at`.
3. WHEN MultiAgentSessionTimeline receives a `TEXT_MESSAGE_CONTENT` frame carrying sender/receiver metadata (a message delivery), THE MultiAgentSessionTimeline SHALL append a `message` entry from the frame's metadata and SHALL NOT store the frame's `delta`.
4. IF a `TOOL_CALL_END` or `TOOL_CALL_RESULT` arrives whose `tool_call_id` matches no open entry, THEN THE MultiAgentSessionTimeline SHALL leave its entries unchanged.
5. IF a `TOOL_CALL_START` arrives whose `tool_call_id` matches an existing entry, THEN THE MultiAgentSessionTimeline SHALL NOT create a duplicate entry.
6. THE MultiAgentSessionTimeline SHALL append entries in arrival order and expose them ordered by `(started_at timestamp, entry id)` as a deterministic tiebreak; event ids SHALL be used for Seen_Set_Dedup, never for ordering.
7. THE MultiAgentSessionTimeline SHALL maintain the invariant that every `completed`/`failed` entry was previously `open`.
8. WHEN appending an entry would exceed the configured retention cap (default 1,000 entries — the construct's own bound), THE MultiAgentSessionTimeline SHALL evict oldest entries first until within the cap.

### Requirement 6: Complete the TOOL_CALL lifecycle in the L1 adapter (Cleanup A)

**User Story:** As a timeline consumer, I want orchestration dispatches to emit
matching completion frames, so that timeline entries close instead of remaining
perpetually open — aligning the adapter with the mapping table `docs/agui.md` already
publishes.

#### Acceptance Criteria

1. WHEN a fleet record of kind `handoff` carries `orchestration_type` `handoff` or `assign`, THE L1_Adapter SHALL map it to `TOOL_CALL_START` with `tool_call_id` = the record's event id, `tool_call_name` = the orchestration type, and metadata-only sender/receiver fields.
2. WHEN a fleet record of kind `handoff` carries `orchestration_type` `send_message` (or none), THE L1_Adapter SHALL continue to map it to `TEXT_MESSAGE_CONTENT` exactly as today (message delivery, metadata-only, empty delta).
3. WHEN a completion record arrives for the receiver terminal of an open orchestration `TOOL_CALL_START` (or the session ends), THE stream layer SHALL emit exactly one correlated `TOOL_CALL_END` carrying that same `tool_call_id` and a metadata-only disposition (`closed_by`: receiver completion vs. session end; failure indication where derivable) — no message text.
4. WHERE a record of kind `a2a_delegation` opens a `TOOL_CALL_START` (forward-provisioned; the kind has no producer today), THE stream layer SHALL additionally emit exactly one `TOOL_CALL_RESULT` with the same `tool_call_id` and metadata-only content when its correlated completion arrives.
5. IF a completion record correlates to no open `TOOL_CALL_START`, THEN THE stream layer SHALL NOT emit an orphan `TOOL_CALL_END` or `TOOL_CALL_RESULT`.
6. THE correlation state SHALL be bounded (evicting oldest open entries beyond a fixed cap) and deterministic, so that a `?since=`/`Last-Event-ID` replay of the same records synthesizes the same lifecycle frames.
7. THE L1_Adapter SHALL leave every non-orchestration mapping byte-identical to today's output, and `docs/agui.md`'s mapping table and the bundled EventSource viewer SHALL be updated in the same change to match the emitted lifecycle.

### Requirement 7: Replay contract hardening and documentation (Cleanup B)

**User Story:** As a construct maintainer, I want the replay contract documented as it
actually is, so that a reconnect leaves no gap and no double-applied frame.

#### Acceptance Criteria

1. THE Ambient_Stream SHALL continue to carry an `id:` cursor on every frame derived from a buffered event record, and no `id:` on per-connection state frames.
2. IF `?since=` is supplied and is not a parseable ISO-8601 timestamp, THEN THE Ambient_Stream SHALL reject the request with HTTP 400 before streaming begins.
3. WHEN both `?since=` and `Last-Event-ID` are supplied, THE Ambient_Stream SHALL use `?since=` and ignore `Last-Event-ID` (existing behavior, pinned by test).
4. WHEN a client reconnects with a `Last-Event-ID` that is unknown or already evicted from the ring buffer, THE Ambient_Stream SHALL over-deliver (replay all buffered records) rather than silently skip, and THE consuming construct SHALL drop duplicates via Seen_Set_Dedup.
5. WHEN a client reconnects, THE Ambient_Stream SHALL deliver replayed event frames first and exactly one fresh `STATE_SNAPSHOT` before any subsequent `STATE_DELTA` (existing behavior, pinned by regression test so the state projection can never tear).
6. THE feature SHALL document in `docs/agui.md`: the `?since=` ISO-8601-exclusive semantics, the `Last-Event-ID` uuid-cursor semantics, their precedence, the over-delivery rule, the Seen_Set_Dedup contract (ids are uuid4 — set membership, never ordering comparisons), and that this replay surface is a CAO extension consumed by CAO-aware clients (no stock AG-UI SDK implements stream resumption).

### Requirement 8: Provider-namespaced interrupt reason classification

**User Story:** As a client author, I want provider-namespaced interrupt reasons
following ag-ui's documented `<framework>:<name>` convention, so that I can switch on
prompt category exhaustively with a safe default.

#### Acceptance Criteria

1. WHEN the Reason_Classifier is called with any `provider` string and any `raw_prompt` string (including empty strings), THE Reason_Classifier SHALL return exactly one string `<namespace>:<local_name>` where the namespace matches `^[a-z0-9-]+$` and the local name matches `^[a-z0-9_]+$`, and SHALL never raise.
2. THE Reason_Classifier SHALL use the fixed namespace mapping `kiro_cli`→`kiro`, `claude_code`→`claude-code`, `codex`→`codex`, and a deterministic kebab-case transformation for any other provider; it SHALL never emit the ag-ui-reserved `core:` namespace.
3. THE Reason_Classifier SHALL be deterministic: equal `(provider, raw_prompt)` inputs yield equal outputs.
4. WHEN `provider` is `claude_code` and `raw_prompt` matches the tool-permission picker signature (the provider's `WAITING_USER_ANSWER` pattern with permission phrasing), THE Reason_Classifier SHALL return `claude-code:permission_request`; WHEN it matches the trust-folder prompt pattern, `claude-code:trust_prompt`.
5. WHEN `provider` is `kiro_cli` and `raw_prompt` matches the legacy `Allow this action?` or TUI permission patterns, THE Reason_Classifier SHALL return `kiro:permission_request`; WHEN it matches a trust prompt, `kiro:trust_prompt`.
6. WHEN `provider` is `codex` and `raw_prompt` matches the approval-gate pattern, THE Reason_Classifier SHALL return `codex:approval_request`; WHEN it matches the workspace-trust prompt, `codex:trust_prompt`.
7. IF `raw_prompt` matches no known pattern for its provider, THEN THE Reason_Classifier SHALL return `{resolved_namespace}:unknown_prompt`.
8. THE Reason_Classifier SHALL restrict each Supported_Provider to a closed local-name set with `unknown_prompt` as the safe default, and the classification patterns SHALL be derived from the providers' existing detection patterns rather than new terminal parsing.

### Requirement 9: Human-in-the-loop approval against a real provider prompt

**User Story:** As a human operator, I want to approve, deny, or edit a real provider
prompt from a browser, so that I can authorize agent actions in the loop.

#### Acceptance Criteria

1. THE Approval_Bridge SHALL subscribe to internal terminal status transitions and, WHEN a terminal transitions to `WAITING_USER_ANSWER`, SHALL capture the prompt context (provider id + rendered prompt tail), and invoke `AgentHandoffWithApproval.on_provider_waiting` — this bridge SHALL run only while the AG-UI surface is enabled.
2. WHEN `on_provider_waiting` is invoked, THE AgentHandoffWithApproval SHALL open exactly one Interrupt (fresh uuid id; provider-namespaced `reason` per Requirement 8; `metadata` carrying provider, terminal id, session name; originating event context) and emit exactly one `approval_card` intent through the Emit_Path.
3. WHEN AgentHandoffWithApproval emits an approval card or resolution intent, THE intent SHALL carry only the prompt category and a redacted summary of at most 256 characters, and SHALL NOT include raw prompt text beyond that summary.
4. WHEN `resume(interrupt_id, decision, edited_text=None)` is called with decision `approve`, `deny`, or `edit` on an open Interrupt, THE AgentHandoffWithApproval SHALL resolve it exactly once: translate the decision to the provider-specific answer (existing `/terminals/{id}/input` and `/terminals/{id}/key` paths), deliver it exactly once, set `outcome` to the decision, and emit exactly one resolution intent.
5. IF `decision` is `edit` AND `edited_text` is absent, empty, or longer than 4,000 characters, THEN THE AgentHandoffWithApproval SHALL reject with a validation error, deliver no keystrokes, and leave the Interrupt open.
6. IF the provider prompt category does not support the requested decision (e.g. `edit` against a fixed-choice picker), THEN THE AgentHandoffWithApproval SHALL reject with a validation error identifying the unsupported decision and leave the Interrupt open.
7. IF `resume` is called on an already-resolved Interrupt, THEN THE AgentHandoffWithApproval SHALL return the recorded Interrupt unchanged and deliver no further keystrokes (idempotent).
8. WHEN the terminal leaves `WAITING_USER_ANSWER` before any decision arrives, THE AgentHandoffWithApproval SHALL resolve the Interrupt with outcome `expired`, deliver **zero** keystrokes, and emit exactly one expiration resolution intent; a `resume` losing this race SHALL receive the recorded `expired` Interrupt.
9. THE AgentHandoffWithApproval SHALL evict resolved/expired Interrupts within 300 seconds, retain at most 1,000 Interrupts (evicting oldest resolved/expired first), and expose `pending()`.

### Requirement 10: Resume endpoint authorization and default-off gating

**User Story:** As a security reviewer, I want the resume route protected like the
emit route, so that resuming a provider prompt is a privileged, opt-in action.

#### Acceptance Criteria

1. THE Resume_Endpoint (`POST /agui/v1/interrupts/{id}/resume`) SHALL require the `cao:write` (or `cao:admin`) scope when auth is enabled.
2. WHILE the AG-UI surface is disabled, THE Resume_Endpoint SHALL respond with the surface-not-available error (404, matching the existing gate) and SHALL NOT invoke `resume`.
3. WHEN a well-formed authorized decision is POSTed with the surface enabled, THE Resume_Endpoint SHALL route the decision and any `edited_text` to `AgentHandoffWithApproval.resume` exactly once.
4. IF the interrupt id is unknown, THEN THE Resume_Endpoint SHALL respond 404 without invoking `resume`.
5. IF the decision is not one of `approve` / `deny` / `edit`, THEN THE Resume_Endpoint SHALL respond with a validation failure without invoking `resume`.

### Requirement 11: Cross-provider shared-state convergence

**User Story:** As a fleet operator, I want shared state to converge regardless of
which providers produced the events, so that every client sees one consistent fleet
view.

#### Acceptance Criteria

1. WHEN CrossProviderStateSync receives a `STATE_SNAPSHOT` frame, THE CrossProviderStateSync SHALL replace its shared state with a deep copy of the snapshot contents.
2. WHEN CrossProviderStateSync receives a `STATE_DELTA` frame, THE CrossProviderStateSync SHALL apply its RFC 6902 ops atomically (strict apply-else-drop, mirroring the stock client's patch semantics).
3. IF a `STATE_DELTA` arrives before any snapshot, OR fails strict application, THEN THE CrossProviderStateSync SHALL leave its shared state unchanged and SHALL NOT raise.
4. WHEN folding id-bearing frames across a reconnect, THE CrossProviderStateSync SHALL apply Seen_Set_Dedup; per-connection state frames SHALL be folded as received.
5. WHEN CrossProviderStateSync has folded an ordered stream (including any reconnect overlap) produced by a fleet whose terminals span any mix of providers, THE CrossProviderStateSync's shared state SHALL be deep-equal to `build_dashboard_snapshot` of the same fleet.
6. THE CrossProviderStateSync SHALL expose `shared_state()` and `converges_with(authoritative_snapshot)` returning true iff the folded state is deep-equal to the supplied snapshot.
7. THE CrossProviderStateSync SHALL surface the `provider` value already carried on each snapshot terminal entry, so validation can assert coverage across `kiro_cli`, `claude_code`, and `codex` without changing the wire shape.

### Requirement 12: Protocol-faithful run plane with the AG-UI interrupt lifecycle

**User Story:** As a stock-client user, I want CAO to expose a run endpoint speaking
the exact AG-UI wire dialect, so that unmodified clients render the fleet and drive
approvals through the protocol's own interrupt lifecycle.

#### Acceptance Criteria

1. THE Run_Plane SHALL accept `POST /agui/v1/run` with a `RunAgentInput` JSON body (camelCase: `threadId`, `runId`, `messages`, `tools`, `context`, `state`, `forwardedProps`, optional `resume[]`) and SHALL stream Server-Sent Events whose frames are `data:`-only lines of camelCase JSON carrying a `type` field (the stock encoder framing).
2. THE Run_Plane SHALL be gated and scoped exactly like the Ambient_Stream (default-off 404; `cao:read` floor when auth is enabled) and SHALL additionally require `cao:write`/`cao:admin` WHEN the request carries a non-empty `resume[]`.
3. WHEN a run starts, THE Run_Plane SHALL emit `RUN_STARTED` (echoing the client's `threadId`/`runId`) first, then a `STATE_SNAPSHOT` of the fleet, then a lifecycle-legal projection of live fleet activity (`STATE_DELTA`, `STEP_STARTED`/`STEP_FINISHED`, complete `TOOL_CALL_START`→`TOOL_CALL_END` sequences, and `CUSTOM` events for CAO-dialect-only frames such as generative-UI intents and message deliveries) such that the stock client verifier accepts the stream.
4. WHILE a run is streaming and an Interrupt opens, THE Run_Plane SHALL emit a `STATE_SNAPSHOT` and then end the run with `RUN_FINISHED` whose `outcome` is `{type:"interrupt", interrupts:[...]}` carrying every open Interrupt (id, namespaced reason, redacted ≤256-char message, `metadata` with provider/terminal/session).
5. WHEN a new run arrives with `resume[]` entries, THE Run_Plane SHALL resolve each referenced open Interrupt exactly once through the same idempotent path as the Resume_Endpoint, mapping payload `{approved:true}`→approve, `{approved:false}` or status `cancelled`→deny, `{approved:true, editedArgs:{...}}`→edit.
6. IF a run with pending open Interrupts arrives whose `resume[]` does not cover all of them, or references an expired Interrupt, THEN THE Run_Plane SHALL emit `RUN_ERROR` per the ag-ui interrupt contract.
7. THE Run_Plane's event models and SSE encoding SHALL come from the official `ag-ui-protocol` Python SDK (version-pinned optional dependency); IF the optional dependency is not installed, THEN THE Run_Plane SHALL respond 501 with an installation hint while the Ambient_Stream remains fully functional.

### Requirement 13: Stock-client zero-adapter live demo (AC3)

**User Story:** As a prospective adopter, I want a stock AG-UI client rendering a live
run, so that I can confirm no CAO-specific adapter code is required end to end.

#### Acceptance Criteria

1. THE feature SHALL provide a runnable example in which a Stock_Client renders frames served live by `cao-server` over the Run_Plane, where at least one rendered frame originates from server activity occurring after the client connected (demonstrably live, not a replay).
2. WHEN the example's `run.sh` is executed with no credentials/secrets/API keys, THE example SHALL start `cao-server` with the AG-UI surface enabled (driving fleet activity via the `mock_cli` provider) and point the Stock_Client at the Run_Plane.
3. THE example SHALL treat the surface as ready only after the endpoint accepts a connection within 30 seconds; IF readiness fails, THEN `run.sh` SHALL exit non-zero with an error identifying the startup failure and SHALL leave no orphaned `cao-server` process.
4. THE Stock_Client SHALL consist solely of pinned upstream AG-UI packages wired through their documented public APIs, with zero CAO-specific adapter, translation, or wire-decoding source files.

### Requirement 14: Documentation and runnable examples for every construct

**User Story:** As an application author, I want each construct documented with a
runnable example, so that I can adopt it by subclassing rather than reverse-engineering
the protocol.

#### Acceptance Criteria

1. THE feature SHALL document each construct (frames folded, projection accessors, subclass extension points) and the two-plane model (Ambient_Stream dialect vs. Run_Plane stock dialect) in `docs/agui.md` or construct docs linked from it.
2. THE feature SHALL provide exactly one runnable example per construct (four total) following the existing `examples/agui-*/` `run.sh` / `showcase.sh` convention, each running credentials-free (via `mock_cli`) to a success exit.
3. IF an example's preconditions are unmet (surface disabled, server unreachable), THEN the example SHALL exit non-zero with an error indication and leave no orphaned `cao-server` process.
4. THE AgentHandoffWithApproval example SHALL additionally document the live real-provider procedure: launching an approval-mode agent profile (e.g. claude_code with `permissionMode` left at provider default instead of CAO's auto-skip) so a genuine permission prompt occurs.
5. THE documentation for each construct SHALL show composition purely over the L2 seams (Stream_Reader + construct + emitter) and SHALL NOT depict bespoke SSE parsing, new routes, or wire serialization in application code.

### Requirement 15: AC5 exit gate

**User Story:** As a release manager, I want a single exit gate covering the four
constructs, the real-prompt approval, and cross-provider convergence, so that I can
confirm Phase 2 is complete.

#### Acceptance Criteria

1. THE AC5_Exit_Gate SHALL require all four constructs shipped with documentation and a runnable example per Requirement 14.
2. THE AC5_Exit_Gate SHALL require an automated CI demonstration (via the `mock_cli` scripted-prompt mode) of approve and deny decisions submitted from a browser-equivalent HTTP client through the Resume_Endpoint AND through the Run_Plane `resume[]` path, each observing exactly-once answer delivery to the live terminal.
3. THE AC5_Exit_Gate SHALL require a documented, reproducible live demonstration of approving or denying a **real** Supported_Provider permission prompt from a browser (approval-mode profile procedure per Requirement 14.4).
4. THE AC5_Exit_Gate SHALL require `CrossProviderStateSync.converges_with(...)` returning true over a fleet whose terminals span all three of `kiro_cli`, `claude_code`, and `codex`.
5. THE AC5_Exit_Gate SHALL require the Run_Plane stream to pass the stock client verification pipeline in the AC3 demo.
6. IF any gate condition fails, THEN THE AC5_Exit_Gate SHALL report not-complete and identify the failing condition.
