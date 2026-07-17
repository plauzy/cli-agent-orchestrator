# Requirements Document

## Introduction

This document specifies the requirements for **AG-UI Phase 2 — the L2 construct
library** (tracking issue awslabs/cli-agent-orchestrator #458). The requirements are
derived from the approved design (`design.md`) and describe *what* the L2 layer must do;
implementation detail lives in the design.

The feature adds a small library of named, subclassable **L2 constructs** layered over
the already-merged **L1 AG-UI adapter**. Each construct composes purely over the L1
surface (`GET /agui/v1/stream` and `POST /agui/v1/emit_ui`): it either reads AG-UI frames
and folds them into a projection, writes through the existing emit path, or both. No
construct opens its own socket, serializes SSE framing, or widens the L1 privacy
boundary.

Four constructs are in scope, each shipping with documentation and a runnable example:
`SupervisorDashboardStream`, `MultiAgentSessionTimeline`, `AgentHandoffWithApproval`, and
`CrossProviderStateSync`. The feature also owns three narrowly-scoped **L1 cleanups** the
constructs depend on: completing the `TOOL_CALL_*` lifecycle, hardening the `?since=`
replay contract with client-side dedup, and adding a stock-client zero-adapter live demo.

**Out of scope (explicitly):** the Phase 3 / L3 reference dashboard application,
authenticated *team* mode, the AG-UI Dojo ecosystem listing, and A2A / Agent Card / ACP
protocol modules.

## Glossary

- **L1_Adapter**: the merged, unchanged AG-UI adapter that maps the fleet's six normalized
  event primitives to AG-UI typed `(type, data)` frames and exposes them on the default-off
  SSE surface.
- **Agui_Stream**: the L1 HTTP endpoint `GET /agui/v1/stream` that serves AG-UI frames over
  Server-Sent Events, including `?since=` / `Last-Event-ID` replay.
- **Emit_Path**: the L1 write surface `POST /agui/v1/emit_ui` together with the event-bus
  publish path it drives, subject to allow-list and size validation.
- **AguiConstruct**: the abstract base class for all L2 constructs; owns the single read
  seam (`handle_frame`) and single write seam (`emit`).
- **SupervisorDashboardStream**: the L2 construct that folds `STATE_SNAPSHOT`/`STATE_DELTA`
  frames into a session→terminal hierarchy and a rolling supervisor snapshot.
- **MultiAgentSessionTimeline**: the L2 construct that folds `TOOL_CALL_*` and
  `TEXT_MESSAGE_CONTENT` frames into an ordered handoff/delegation timeline.
- **AgentHandoffWithApproval**: the L2 construct that maps a real provider permission/trust
  prompt onto AG-UI's interrupt lifecycle and resumes the live provider from a browser
  decision.
- **CrossProviderStateSync**: the L2 construct that folds shared fleet state and validates
  convergence across heterogeneous providers.
- **Reason_Classifier**: the total function `classify_reason(provider, raw_prompt)` that
  maps a provider prompt to a provider-namespaced reason string.
- **Resume_Endpoint**: the thin route `POST /agui/v1/interrupts/{id}/resume` that wires a
  browser decision to `AgentHandoffWithApproval.resume`.
- **Interrupt**: the approval-lifecycle record with states `open` and `resolved`, carrying a
  provider-namespaced `reason` and, when resolved, an `outcome`.
- **Projection**: a JSON-serializable, metadata-only view a construct folds from frames.
- **Metadata_Only_Boundary**: the L1 privacy invariant that no message body, delta text, or
  terminal stdout appears on the wire or in any projection.
- **RFC_6902_Ops**: JSON Patch operations carried by a `STATE_DELTA` frame.
- **Supported_Providers**: the provider identities `kiro_cli`, `claude_code`, and `codex`.
- **Stock_Client**: an unmodified AG-UI client (AG-UI Dojo / CopilotKit) that renders the
  stream with zero CAO-specific adapter code.
- **AC5_Exit_Gate**: the acceptance gate requiring all four constructs to ship with docs and
  a runnable example, `AgentHandoffWithApproval` to approve/deny a real provider prompt from
  a browser, and `CrossProviderStateSync` to be validated across at least three providers.

## Requirements

### Requirement 1: Subclassable base construct with single read and write seams

**User Story:** As an application author, I want a subclassable base construct that owns the
composition seam to L1, so that I implement domain folding without writing any SSE wiring.

#### Acceptance Criteria

1. THE AguiConstruct SHALL expose exactly one read seam, `handle_frame(agui_type, data)`, through which every subclass receives AG-UI frames.
2. THE AguiConstruct SHALL expose exactly one write seam, `emit(component, props, terminal_id, session_name)`, that routes every published intent exclusively through the Emit_Path.
3. WHEN a subclass produces output, THE AguiConstruct SHALL publish that output solely through the `emit` write seam.
4. THE AguiConstruct SHALL NOT open a socket, add a route, or serialize SSE framing in the application layer.
5. IF `handle_frame` receives a frame whose `agui_type` is not one it recognizes, THEN THE AguiConstruct SHALL leave the current projection unchanged.
6. IF `handle_frame` receives a frame whose `agui_type` is not one it recognizes, THEN THE AguiConstruct SHALL return without raising an exception.
7. THE AguiConstruct SHALL provide a `projection()` accessor that returns a JSON-serializable value and completes without raising an exception.
8. WHERE a construct is configured with a test emitter in place of the production emitter, THE AguiConstruct SHALL record each `emit` intent, including `component`, `props`, `terminal_id`, and `session_name`, for later inspection and SHALL publish nothing through the Emit_Path.

### Requirement 2: Emit refusal parity with the L1 emit surface

**User Story:** As a platform maintainer, I want the L2 write seam to enforce the same
validation as `emit_ui`, so that no construct can bypass the L1 safety guards.

#### Acceptance Criteria

1. WHEN `emit` is called with a `component` on the L1 generative-UI allow-list AND `props` that are JSON-serializable AND the serialized `props` are at most 8 KiB (where 8 KiB is 8192 bytes, measured as the length in bytes of the UTF-8-encoded JSON serialization of `props`), THE AguiConstruct SHALL publish exactly one intent through the Emit_Path.
2. IF `emit` is called with a `component` that is not on the L1 allow-list, THEN THE AguiConstruct SHALL refuse the call by raising a `ValueError` and SHALL publish nothing.
3. IF `emit` is called with `props` that are not JSON-serializable, THEN THE AguiConstruct SHALL refuse the call by raising a `ValueError` and SHALL publish nothing.
4. IF `emit` is called with `props` whose UTF-8-encoded JSON serialization exceeds 8192 bytes, THEN THE AguiConstruct SHALL refuse the call by raising a `ValueError` and SHALL publish nothing.
5. WHEN `emit` is called, THE AguiConstruct SHALL leave the caller-supplied `props` mapping unmutated, whether the call publishes an intent or refuses with a `ValueError`.

### Requirement 3: Metadata-only privacy boundary preserved through L2

**User Story:** As a security reviewer, I want the L1 privacy boundary preserved through
every construct, so that message bodies and terminal output never reach the wire.

#### Acceptance Criteria

1. THE AguiConstruct SHALL ensure that every value returned by `projection()` contains no message-body field, where a message-body field is any field carrying message delta text, terminal stdout, or assistant message content.
2. WHEN any construct emits an intent, THE AguiConstruct SHALL ensure the emitted intent contains no message-body field (message delta text, terminal stdout, or assistant message content).
3. WHEN a construct folds a `TEXT_MESSAGE_CONTENT` frame, THE construct SHALL NOT store the frame's `delta` content in its projection.
4. WHEN `assert_no_body(data)` is invoked with a frame carrying no message-body field, THE AguiConstruct SHALL return without raising.
5. IF `assert_no_body(data)` is invoked with a frame carrying a message-body field (message delta text, terminal stdout, or assistant message content), THEN THE AguiConstruct SHALL reject the frame by raising an exception, SHALL leave the projection unchanged, and SHALL publish nothing.

### Requirement 4: Supervisor dashboard projection from L1 state frames

**User Story:** As a supervisor operator, I want a folded session→terminal hierarchy and a
rolling supervisor snapshot, so that I can monitor the fleet without re-deriving the wire
protocol.

#### Acceptance Criteria

1. WHEN SupervisorDashboardStream receives a `STATE_SNAPSHOT` frame, THE SupervisorDashboardStream SHALL replace its projection with the snapshot contents.
2. WHEN SupervisorDashboardStream receives a `STATE_DELTA` frame, THE SupervisorDashboardStream SHALL apply the frame's RFC_6902_Ops to its current projection in the order they appear.
3. IF SupervisorDashboardStream receives a `STATE_DELTA` frame before any `STATE_SNAPSHOT` baseline, OR whose RFC_6902_Ops reference an absent path, THEN THE SupervisorDashboardStream SHALL leave the projection unchanged and SHALL return without raising.
4. WHEN a client reconnects and replayed frames are folded, THE SupervisorDashboardStream SHALL deduplicate by event id so that no frame is applied twice.
5. THE SupervisorDashboardStream SHALL expose a `hierarchy()` view mapping each session to (a) its terminal identifiers list, (b) its session status derived from folded frames, and (c) the count of terminals in that session.
6. THE SupervisorDashboardStream SHALL expose a `supervisor_snapshot()` rollup containing the active session count (sessions whose folded status is not terminated or closed), per-provider terminal counts scoped to Supported_Providers, and last-activity given as the event id of the most recently folded frame, all derived only from folded frames.
7. THE SupervisorDashboardStream SHALL derive every projection field solely from folded frames and SHALL NOT fetch from any data source of its own.

### Requirement 5: Multi-agent handoff and delegation timeline

**User Story:** As a supervisor operator, I want a causally-ordered timeline of handoffs and
delegations, so that I can follow how work moves between agents.

#### Acceptance Criteria

1. WHEN MultiAgentSessionTimeline receives a `TOOL_CALL_START` frame whose `tool_call_id` matches no open entry, THE MultiAgentSessionTimeline SHALL append a delegation entry with status `open` keyed by the frame's `tool_call_id` and SHALL record its `started_at` from the frame's timestamp.
2. WHEN MultiAgentSessionTimeline receives a `TOOL_CALL_END` or `TOOL_CALL_RESULT` frame whose `tool_call_id` matches an open entry, THE MultiAgentSessionTimeline SHALL set that entry's status to `completed` and record its `ended_at` from the frame's timestamp.
3. WHEN MultiAgentSessionTimeline receives a `TEXT_MESSAGE_CONTENT` frame, THE MultiAgentSessionTimeline SHALL append a handoff entry recording its `started_at` from the frame's timestamp and SHALL NOT store the frame's `delta` content.
4. IF MultiAgentSessionTimeline receives a `TOOL_CALL_END` or `TOOL_CALL_RESULT` frame whose `tool_call_id` matches no open entry, THEN THE MultiAgentSessionTimeline SHALL leave its entries unchanged.
5. IF MultiAgentSessionTimeline receives a `TOOL_CALL_START` frame whose `tool_call_id` matches an existing open entry, THEN THE MultiAgentSessionTimeline SHALL leave its entries unchanged and SHALL NOT create a duplicate entry.
6. THE MultiAgentSessionTimeline SHALL keep entries ordered by their `(timestamp, id)` pair.
7. THE MultiAgentSessionTimeline SHALL ensure that the count of `completed` entries never exceeds the count of opened entries and that no entry becomes `completed` without first being `open`.
8. WHEN appending an entry would cause the retained entry count to exceed 1,000, THE MultiAgentSessionTimeline SHALL evict the oldest entries by `(timestamp, id)` order until at most 1,000 entries remain.

### Requirement 6: Complete the TOOL_CALL lifecycle in the L1 adapter

**User Story:** As a timeline consumer, I want delegations to emit matching completion
frames, so that timeline entries close instead of remaining perpetually open.

#### Acceptance Criteria

1. WHEN a completion primitive correlated by `tool_call_id` to a prior `TOOL_CALL_START` occurs, THE L1_Adapter SHALL emit exactly one `TOOL_CALL_END` frame carrying that same `tool_call_id`.
2. WHERE a completed delegation that originated a `TOOL_CALL_START` carries a result payload, THE L1_Adapter SHALL emit exactly one `TOOL_CALL_RESULT` frame carrying the same `tool_call_id` as that originating `TOOL_CALL_START`.
3. IF a completion primitive has no matching prior `TOOL_CALL_START`, THEN THE L1_Adapter SHALL NOT emit an orphan `TOOL_CALL_END` or `TOOL_CALL_RESULT` frame.
4. WHEN a correlated delegation terminates in failure, THE L1_Adapter SHALL emit a `TOOL_CALL_END` frame with a metadata failure indication and no exact message text, closing the timeline entry.
5. THE L1_Adapter SHALL ensure every emitted `TOOL_CALL_END` and `TOOL_CALL_RESULT` frame carries metadata only and no message-body field.
6. THE L1_Adapter SHALL emit the same frames as before this change for primitive mappings that do not correspond to a delegation lifecycle.

### Requirement 7: Replay contract hardening with client-side deduplication

**User Story:** As a construct maintainer, I want a documented `?since=` replay contract with
event-id dedup, so that a reconnect leaves no gap and no double-applied delta.

#### Acceptance Criteria

1. WHEN the Agui_Stream replays buffered frames over the `?since=` replay path, THE Agui_Stream SHALL include a monotonically-ordered `id` cursor on each replayed frame.
2. WHEN a client reconnects across a fresh connection using `?since=`, THE construct folding the replayed frames SHALL skip frames whose `id` is less than or equal to the highest `id` already applied so that no frame is applied twice.
3. WHEN a client reconnects, THE Agui_Stream SHALL deliver exactly one `STATE_SNAPSHOT` before any subsequent `STATE_DELTA` so the client's projection is never torn.
4. WHEN both `?since=` and `Last-Event-ID` are supplied for the AG-UI frame path, THE Agui_Stream SHALL use `?since=` and SHALL ignore `Last-Event-ID`.
5. IF a `?since=` cursor references frames already evicted from the replay buffer, THEN THE Agui_Stream SHALL deliver a full `STATE_SNAPSHOT` baseline.
6. IF a supplied cursor is malformed or non-existent, THEN THE Agui_Stream SHALL reject the request with an invalid-cursor error and SHALL perform no replay.
7. THE feature SHALL document the client-side dedup-by-event-id contract in `docs/agui.md`.

### Requirement 8: Provider-namespaced interrupt reason classification

**User Story:** As a client author, I want provider-namespaced interrupt reasons, so that I
can switch on prompt category exhaustively with a safe default.

#### Acceptance Criteria

1. WHEN the Reason_Classifier is called with any `provider` string and any `raw_prompt` string, including empty-string inputs, THE Reason_Classifier SHALL return exactly one string of the form `<namespace>:<local_name>` where the namespace matches `^[a-z0-9-]+$` and the local name matches `^[a-z0-9_]+$`.
2. THE Reason_Classifier SHALL derive the namespace by a fixed mapping for Supported_Providers (`kiro_cli`→`kiro`, `claude_code`→`claude-code`, `codex`→`codex`) and by a deterministic kebab-case transformation of the `provider` string for any unsupported provider.
3. THE Reason_Classifier SHALL return the same reason for the same `(provider, raw_prompt)` inputs on every invocation.
4. IF a `raw_prompt` matches no known local-name pattern for its provider, THEN THE Reason_Classifier SHALL return `"{resolved_namespace}:unknown_prompt"`.
5. WHEN the Reason_Classifier is called with `provider` `claude_code` AND a `raw_prompt` matching the claude_code WAITING_USER_ANSWER/approval-gate prompt pattern, THE Reason_Classifier SHALL return `claude-code:permission_request`.
6. WHEN the Reason_Classifier is called with `provider` `kiro_cli` AND a `raw_prompt` matching the kiro_cli WAITING_USER_ANSWER/approval-gate prompt pattern, THE Reason_Classifier SHALL return `kiro:trust_prompt`.
7. WHEN the Reason_Classifier is called with `provider` `codex` AND a `raw_prompt` matching the codex WAITING_USER_ANSWER/approval-gate prompt pattern, THE Reason_Classifier SHALL return `codex:approval_request`.
8. THE Reason_Classifier SHALL restrict each Supported_Provider's local names to a closed set, using `unknown_prompt` as the safe default for that provider.
9. THE Reason_Classifier SHALL return a reason for every input without raising an exception.

### Requirement 9: Human-in-the-loop approval against a real provider prompt

**User Story:** As a human operator, I want to approve, deny, or edit a real provider prompt
from a browser, so that I can authorize agent actions in the loop.

#### Acceptance Criteria

1. WHEN a provider transitions to `WAITING_USER_ANSWER`, THE AgentHandoffWithApproval SHALL open an Interrupt with a provider-namespaced `reason` matching the pattern `^[a-z0-9-]+:[a-z0-9_]+$` and emit exactly one `approval_card` generative-UI intent through the Emit_Path.
2. WHEN AgentHandoffWithApproval emits an approval card, THE AgentHandoffWithApproval SHALL include only the prompt category and a redacted summary of at most 256 characters, and SHALL NOT include raw sensitive command text unless the provider marks that text safe.
3. WHEN AgentHandoffWithApproval resolves an open Interrupt with a decision of `approve`, `deny`, or `edit`, THE AgentHandoffWithApproval SHALL set the Interrupt to `resolved` with `outcome` equal to the decision, send the corresponding provider keystrokes to the live terminal exactly once via `send_input`, and emit exactly one resolution frame.
4. IF `resume` is called with a decision of `edit` AND `edited_text` is absent or empty, THEN THE AgentHandoffWithApproval SHALL reject the call with a validation error indicating that edited text is required, SHALL NOT invoke `send_input`, and SHALL leave the Interrupt `open`; otherwise the supplied `edited_text` SHALL be at most 8 KiB when serialized.
5. IF `resume` is called on an already-resolved Interrupt, THEN THE AgentHandoffWithApproval SHALL return the recorded Interrupt unchanged and SHALL NOT send further keystrokes.
6. IF `resume` is called with an interrupt id that identifies no known Interrupt, THEN THE Resume_Endpoint SHALL respond with HTTP 404.
7. IF the terminal leaves `WAITING_USER_ANSWER` before a decision arrives, THEN THE AgentHandoffWithApproval SHALL set the Interrupt to `resolved` with `outcome` equal to `expired`, invoke `send_input` at most once, catch any `send_input` failure without propagating an exception to the stream, and emit exactly one resolution frame whose `outcome` indicates expiration.
8. THE AgentHandoffWithApproval SHALL evict each Interrupt from its registry within 300 seconds of that Interrupt becoming `resolved` or `expired`, and SHALL retain at most 1000 Interrupts in the registry, evicting the oldest resolved or expired entries first when the limit is reached.

### Requirement 10: Resume endpoint authorization and default-off gating

**User Story:** As a security reviewer, I want the resume route protected like the emit route,
so that resuming a provider prompt is a privileged, opt-in action.

#### Acceptance Criteria

1. THE Resume_Endpoint SHALL require the `cao:write` authorization scope.
2. WHILE the AG-UI surface is disabled, THE Resume_Endpoint SHALL reject requests with a surface-not-available response, SHALL NOT invoke `AgentHandoffWithApproval.resume`, and SHALL leave the Interrupt unchanged.
3. WHEN a browser POSTs a well-formed decision to `POST /agui/v1/interrupts/{id}/resume` with the `cao:write` scope present and the AG-UI surface enabled, THE Resume_Endpoint SHALL route both the decision and any `edited_text` to `AgentHandoffWithApproval.resume` exactly once.
4. IF a request lacks the `cao:write` scope, THEN THE Resume_Endpoint SHALL respond with an authorization-failure, SHALL NOT invoke `AgentHandoffWithApproval.resume`, and SHALL leave the Interrupt unchanged.
5. IF the decision value is not one of `approve`, `deny`, or `edit`, THEN THE Resume_Endpoint SHALL respond with a validation-failure, SHALL NOT invoke `AgentHandoffWithApproval.resume`, and SHALL leave the Interrupt unchanged.

### Requirement 11: Cross-provider shared-state convergence

**User Story:** As a fleet operator, I want shared state to converge regardless of which
providers produced the events, so that every client sees one consistent fleet view.

#### Acceptance Criteria

1. WHEN CrossProviderStateSync receives a `STATE_SNAPSHOT` frame, THE CrossProviderStateSync SHALL replace its entire shared state with a deep copy of the snapshot contents.
2. WHEN CrossProviderStateSync receives a `STATE_DELTA` frame that carries a valid RFC 6902 patch, THE CrossProviderStateSync SHALL apply the frame's RFC_6902_Ops to its shared state.
3. IF CrossProviderStateSync receives a `STATE_DELTA` frame before any `STATE_SNAPSHOT`, OR carrying invalid RFC_6902_Ops, THEN THE CrossProviderStateSync SHALL leave its shared state unchanged and SHALL NOT raise.
4. WHEN a client reconnects, THE CrossProviderStateSync SHALL ignore frames whose `id` cursor was already folded so that no delta is applied twice.
5. WHEN CrossProviderStateSync has folded a frame set produced by any mix of Supported_Providers in any ordering consistent with per-key causal order, THE CrossProviderStateSync SHALL produce a shared state that is deep-equal to the authoritative `build_dashboard_snapshot` of the same fleet.
6. THE CrossProviderStateSync SHALL expose a `converges_with(authoritative_snapshot)` accessor that returns true if and only if its folded shared state is deep-equal to the supplied authoritative snapshot.
7. THE CrossProviderStateSync SHALL carry a `provider` tag on each per-terminal entry whose value is exactly one of the Supported_Providers (`kiro_cli`, `claude_code`, `codex`), so that coverage across all three providers can be asserted without changing the wire shape.

### Requirement 12: Stock-client zero-adapter live demo

**User Story:** As a prospective adopter, I want a stock AG-UI client rendering a live run,
so that I can confirm no CAO-specific adapter code is required end to end.

#### Acceptance Criteria

1. THE feature SHALL provide a runnable example in which a Stock_Client renders AG-UI frames served by a live `cao-server` over the Agui_Stream, where at least one rendered frame originates from `cao-server` activity that occurs after the Stock_Client has connected, so that the run is demonstrably live rather than a recorded or file-backed replay.
2. WHEN the example's `run.sh` is executed with no credentials, secrets, or API keys supplied, THE example SHALL start `cao-server` with the AG-UI surface enabled and SHALL point the Stock_Client at the `/agui/v1/stream` endpoint of that running `cao-server`.
3. WHEN `run.sh` starts `cao-server`, THE example SHALL treat the AG-UI surface as ready only after `/agui/v1/stream` accepts a client connection within 30 seconds, before pointing the Stock_Client at the endpoint.
4. THE Stock_Client used by the example SHALL consist solely of an unmodified upstream AG-UI client (AG-UI Dojo / CopilotKit) and SHALL contain zero CAO-specific adapter, translation, or wire-decoding source files, such that removing all CAO-authored code from the client leaves the live rendering behavior unchanged.
5. IF `cao-server` fails to expose a connectable `/agui/v1/stream` within the 30-second readiness window, THEN `run.sh` SHALL terminate with a non-zero exit status and SHALL surface an error indication identifying the startup failure, without leaving an orphaned `cao-server` process running.

### Requirement 13: Documentation and runnable examples for every construct

**User Story:** As an application author, I want each construct documented with a runnable
example, so that I can adopt it by subclassing rather than reverse-engineering the protocol.

#### Acceptance Criteria

1. THE feature SHALL provide documentation for each of SupervisorDashboardStream, MultiAgentSessionTimeline, AgentHandoffWithApproval, and CrossProviderStateSync that identifies the AG-UI frame types the construct folds and the projection accessor methods it exposes.
2. THE feature SHALL provide exactly one runnable example per construct (four total) following the existing `run.sh` / `showcase.sh` convention.
3. WHEN a construct's example is run credentials-free, THE example SHALL execute to completion and exit with a success status.
4. IF an example's preconditions are unmet (the AG-UI surface is disabled or `cao-server` is unreachable), THEN THE example SHALL exit with a non-success status, surface an error indication, and leave no orphaned `cao-server` process running.
5. THE documentation for each construct SHALL include a code example obtaining the construct by subclassing AguiConstruct and composing over the L1 surface (Agui_Stream + Emit_Path), and SHALL NOT depict opening a socket, adding a route, or serializing SSE framing.

### Requirement 14: AC5 exit gate

**User Story:** As a release manager, I want a single exit gate covering the four constructs,
the real-prompt approval, and cross-provider convergence, so that I can confirm Phase 2 is
complete.

#### Acceptance Criteria

1. THE AC5_Exit_Gate SHALL require that all four constructs — SupervisorDashboardStream, MultiAgentSessionTimeline, AgentHandoffWithApproval, and CrossProviderStateSync — ship with documentation and a runnable example following the `run.sh` / `showcase.sh` convention.
2. WHEN AgentHandoffWithApproval is exercised for the exit gate, THE AC5_Exit_Gate SHALL demonstrate approve or deny decisions for a real prompt from a Supported_Provider submitted through the Resume_Endpoint from a browser.
3. THE AC5_Exit_Gate SHALL observe the live terminal advancing via exactly-once `send_input` after the browser decision.
4. WHEN CrossProviderStateSync is exercised for the exit gate, THE AC5_Exit_Gate SHALL demonstrate convergence validated via `converges_with` returning true (deep-equal to the authoritative `build_dashboard_snapshot`) across all three named providers (`kiro_cli`, `claude_code`, `codex`).
5. THE AC5_Exit_Gate SHALL report Phase 2 as complete only when all gate conditions hold.
6. IF any gate condition fails, THEN THE AC5_Exit_Gate SHALL report not-complete and indicate which condition failed.
