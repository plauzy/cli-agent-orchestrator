# Requirements Document

## Introduction

This spec covers a comprehensive remediation of the CHANGES_REQUESTED review
`pullrequestreview-5074181308` (@gutosantos82, 2026-09-01) on upstream
awslabs/cli-agent-orchestrator#584 — `feat(agent-plugins): Agent Plugins 1.0.0 support` (#573).

The authoritative plan is `HANDOFF-PR584-review-5074181308.md`, committed at
`61db2158219204f532fda87de97684d2b30cdf92` on plauzy/cli-agent-orchestrator PR #43. Every work
item in that handoff — 1×P1 (with sub-items and drift guards), 7 P2-level items, the 9-item P3
batch — is represented below as at least one requirement. One additional requirement (Requirement 1,
rebase) is user-requested and does not appear in the handoff.

**Decisions resolved.** All six items originally listed under Open Decisions, plus a seventh that
this spec surfaced and the review never asked (whether the Delivery_Seam consults the Ship_Gate),
have been decided by the plan author and recorded in the Rev 2 addendum to
`HANDOFF-PR584-review-5074181308.md` at plauzy/cli-agent-orchestrator PR #43 commit `b1be41b`
(decisions D1–D7 and corrections C1–C6). The requirements below state each chosen branch as settled
fact rather than as a branch to discover; alternatives that were considered and not chosen are
demoted to WHERE-clause criteria or to recorded notes, so that a maintainer who later disagrees has
the alternative and its cost written down. The Open Decisions section is retained as a decision
record and is marked RESOLVED throughout — nothing in it blocks the design or the implementation.
The one remaining conditional is an environment precondition, not a decision: whether the SSH
signing key is available to the executing session, which selects between Requirement 1's rebase path
and its no-rebase fallback.

**Grounding.** Every finding referenced below was re-verified against the PR branch
`feat/agent-plugins-573-upstream` at head `282839c1a189112db7dde5b9754a6e7102ef4068` while writing
this document. Verified facts:

- Six providers wire the delivery seam (`antigravity_cli`, `claude_code`, `codex`, `copilot_cli`,
  `cursor_cli`, `kimi_cli`); `grok_cli.py:420`, `minimax_code.py:360-361`, and `omp.py:176-177`
  read `profile.mcpServers` with no seam call.
- `PROVIDER_TRANSPORTS` (`mcp_mapping.py:100`) holds 10 entries and omits all three providers,
  while its own docstring asserts "Every provider CAO ships is entered explicitly."
- All three omitted serializers do carry URL transports: grok `_render_mcp_config` accepts
  `type` in `{"http","sse"}`, minimax `_serialize_server` accepts `{"streamable-http","sse"}` and
  translates `"http"`→`"streamable-http"`, omp `_write_extension_root` passes entries through.
- `README.md:148-152` claims "the HTTP API is available"; `CODEBASE.md` has zero `agent_plugins`
  mentions; `README.zh-CN.md` has zero `agent-plugins` mentions.
- `agent_plugins/provenance.py` has no importer in `src/`, `web/`, or `tui/`.
- `gate.py:33` `_TRUTHY = ("1","true","yes")` versus `settings_service.py:24`
  `_BOOL_TRUE_VALUES = frozenset({"1","true","yes","on"})`.
- `resolver.py` `_resolve_git` performs no scheme check, host allowlist, or credential-URL
  rejection; the sibling hardening to mirror is `install_service.py:139-215`.
- `uv.lock` differs from `main` by 51 lines (23 insertions, 28 deletions).
- The branch is **1 commit ahead and 3 commits behind** `main`, which is what makes Requirement 1
  live rather than hypothetical.

## Glossary

- **Remediation_Branch**: The git branch `feat/agent-plugins-573-upstream` on
  plauzy/cli-agent-orchestrator carrying PR #584.
- **Upstream_Main**: The default branch (`main`) of the canonical repository that PR #584 targets.
- **Delivery_Seam**: The function `with_plugin_mcp` in
  `src/cli_agent_orchestrator/agent_plugins/mcp_delivery.py`, which returns a loaded agent profile
  with installed plugins' MCP servers merged in.
- **Unwired_Provider**: One of the three provider modules that regenerate native MCP configuration
  from a launch-time profile read without calling the Delivery_Seam: `grok_cli`, `minimax_code`,
  `omp`.
- **Wired_Provider**: A provider module whose launch-time MCP configuration path passes its loaded
  profile through the Delivery_Seam.
- **Transport_Table**: The `PROVIDER_TRANSPORTS` mapping in
  `src/cli_agent_orchestrator/agent_plugins/mcp_mapping.py`.
- **Seam_Drift_Guard**: A test that walks `src/cli_agent_orchestrator/providers/*.py` and asserts
  each module reading `profile.mcpServers` either calls the Delivery_Seam or appears on an
  explicitly commented exemption allowlist.
- **Transport_Coverage_Guard**: A test asserting every Wired_Provider appears as an explicit
  Transport_Table key.
- **Tool_Resolver**: The function `resolve_allowed_tools` in
  `src/cli_agent_orchestrator/utils/tool_mapping.py`.
- **Plugin_Delivered_Server**: An MCP server entry present in a profile's `mcpServers` because the
  agent-plugin merge added the entry, as distinct from an entry declared in the profile source.
- **Profile_Declared_Server**: An MCP server entry present in a profile's source text before any
  agent-plugin merge.
- **Restricted_Profile**: An agent profile whose effective `allowedTools` does not contain `"*"`,
  where "effective" means the allowlist after profile → role → default resolution.
- **Ship_Gate**: The predicate `agent_plugins_surface_enabled` in
  `src/cli_agent_orchestrator/agent_plugins/gate.py`, read from the environment variable
  `CAO_AGENT_PLUGINS_ENABLED`, default off.
- **Canonical_Bool_Set**: The truthy string set `_BOOL_TRUE_VALUES` in
  `src/cli_agent_orchestrator/services/settings_service.py`, namely `{"1","true","yes","on"}`.
- **Mcp_Mapper**: The module `src/cli_agent_orchestrator/agent_plugins/mcp_mapping.py`, including
  its `_map_stdio` entry mapper.
- **Projection_Engine**: The module `src/cli_agent_orchestrator/agent_plugins/projection.py`,
  including `_materialize` and the sweep routine.
- **Git_Resolver**: The function `_resolve_git` in
  `src/cli_agent_orchestrator/agent_plugins/resolver.py`.
- **Http_Resolver_Hardening**: The existing SSRF controls at
  `src/cli_agent_orchestrator/services/install_service.py:139-215` — https-only scheme check, host
  allowlist with a `CAO_PROFILE_ALLOWED_HOSTS` override, rejection of userinfo/query/fragment, and
  redirect refusal.
- **Provenance_Module**: The file `src/cli_agent_orchestrator/agent_plugins/provenance.py`.
- **Web_App**: The web UI root component `web/src/App.tsx` and its flag module
  `web/src/featureFlags.ts`.
- **Docs_Set**: `README.md`, `README.zh-CN.md`, `CODEBASE.md`, and the files under `docs/`.
- **Backlog_Doc**: The repository document that records known issues and accepted deferrals.
- **Package_Dir**: The repository directory `agent-plugin/`, holding the `cao/` and
  `cao-contributor/` packages.
- **Verification_Suite**: The ordered command set in handoff §5 that gates a push.
- **Event_Plugin_Subsystem**: The distinct, pre-existing plugin subsystem documented in
  `docs/plugins.md`.
- **Remediation_Process**: The commit, push, and documentation discipline governing this work.

## Requirements

### Requirement 1: Rebase the branch onto current upstream main

**User Story:** As the PR author, I want the Remediation_Branch rebased onto the latest
Upstream_Main before the review fixes land, so that reviewers evaluate the remediation against
current upstream code rather than a three-commit-stale base.

This requirement is user-requested and is not in the handoff. It conditionally supersedes handoff
§0's instruction to base work on `282839c1`: WHERE the rebase runs, the base becomes the rebased
equivalent of that commit; WHERE the signing-key fallback applies, `282839c1` remains the base
unchanged.

**Decision (settled) — the shape is environment-conditional.** `282839c1` carries an SSH `gpgsig`,
and a plain rebase drops it; an unsigned rewrite of a signed commit must never be pushed. The branch
is MERGEABLE against Upstream_Main with zero conflicts on the probe, so the rebase is a nicety, not a
requirement. Therefore: WHERE the SSH signing key is available to the executing session, rebase with
signing and verify the signature survived; WHERE it is not available, do not rebase at all and land
the work items as ordered commits on top of the existing signed head. Choosing the fallback removes
"unsigned rewrite of a signed commit" as a failure mode outright, rather than routing that failure
mode to a human to catch. Recorded in the Rev 2 addendum's rebase/signature constraint at PR #43
`b1be41b`.

#### Acceptance Criteria

1. THE Remediation_Process SHALL determine, before the first work-item commit of Requirements 2
   through 21 and Requirement 25 is created, whether the SSH signing key that signed `282839c1` is
   available to the executing session, and SHALL record that determination in the PR description.
2. WHERE the signing key is available, THE Remediation_Process SHALL rebase the Remediation_Branch
   onto the Upstream_Main tip with commit signing enabled — `rebase -S` under `gpg.format=ssh` —
   before the first work-item commit of Requirements 2 through 21 and 25 is pushed.
3. WHERE the signing key is available, WHEN the rebase completes, THE Remediation_Process SHALL
   confirm the rewritten head is still signed by matching `^gpgsig` in the commit's raw object, and
   SHALL NOT rely on the `%G?` format placeholder, which is unreliable without an allowed-signers
   file.
4. WHERE the signing key is available, WHEN the rebase completes, THE Remediation_Branch SHALL
   report zero commits behind the Upstream_Main tip that the rebase targeted, SHALL retain every
   change of `282839c1` that no Upstream_Main commit supersedes, and SHALL retain the branch name
   `feat/agent-plugins-573-upstream`.
5. WHERE the signing key is available, IF the rebase produces a merge conflict, THEN THE
   Remediation_Process SHALL resolve the conflict in favor of preserving both the Upstream_Main
   change and the PR #584 change, and SHALL record each resolved file in the rebase commit body or
   the PR description.
6. WHERE the signing key is available, IF the `^gpgsig` check of criterion 3 does not match, THEN
   THE Remediation_Process SHALL discard the rewritten history, SHALL push nothing, and SHALL follow
   the fallback path of criteria 7 through 10.
7. WHERE the signing key is not available to the executing session, THE Remediation_Process SHALL
   NOT rebase the Remediation_Branch, and SHALL land the work items of Requirements 2 through 21 and
   Requirement 25 as ordered commits on top of the existing signed head `282839c1`.
8. WHERE the fallback path of criterion 7 is followed, THE Remediation_Process SHALL correct
   `uv.lock` to match the Upstream_Main copy in a normal work-item commit, SHALL verify that commit
   with `uv lock --check`, and SHALL keep Requirement 19's empty-diff criterion binding on it.
9. WHERE the fallback path of criterion 7 is followed, THE Remediation_Process SHALL leave signing
   of the new commits to the author's push, and SHALL make no change to `282839c1` itself.
10. WHERE the fallback path of criterion 7 is followed, THE Remediation_Process SHALL record in the
    PR description that the branch was not rebased, that it is mergeable against Upstream_Main with
    zero conflicts, and that the base commit's signature is intact.
11. WHEN the selected path completes, THE Verification_Suite SHALL run in full and report zero
    net-new failures compared to the Upstream_Main tip.
12. WHERE the Upstream_Main tip advances again before the remediation is pushed AND the signing key
    is available, THE Remediation_Process SHALL repeat the rebase and re-run the Verification_Suite.
13. THE Remediation_Process SHALL preserve one focused commit per work item on either path, so that
    `282839c1`'s content stays intact as commit 1, work items land as focused commits 2 through n,
    and reviewers' line anchors survive.

### Requirement 2: Deliver plugin MCP servers on the three unwired provider launch paths

**User Story:** As an operator who installed an agent plugin that ships an MCP server, I want that
server delivered to every provider I launch, so that a provider does not silently drop the server.

#### Acceptance Criteria

1. WHEN a launch-time profile read feeds MCP configuration generation in `grok_cli`, THE
   Delivery_Seam SHALL be applied to that profile with the provider key `"grok_cli"`.
2. WHEN a launch-time profile read feeds MCP configuration generation in `minimax_code`, THE
   Delivery_Seam SHALL be applied to that profile with the provider key `"minimax_code"`.
3. WHEN a launch-time profile read feeds MCP configuration generation in `omp`, THE Delivery_Seam
   SHALL be applied to that profile with the provider key `"omp"`.
4. THE Remediation_Process SHALL apply the Delivery_Seam by wrapping each existing
   `load_agent_profile` call rather than replacing that call, so that per-module test patches of
   `load_agent_profile` remain effective.
5. WHERE an Unwired_Provider loads a profile in more than one location, THE Remediation_Process
   SHALL apply the Delivery_Seam to each load that feeds MCP configuration generation, namely grok
   `_build_grok_command`/`_load_profile`, minimax `_prepare_runtime`, and the omp command build.
6. WHILE the Ship_Gate is off, THE Delivery_Seam SHALL leave each of the three providers' generated
   MCP artifacts identical to the artifacts generated before this change.
7. IF the Delivery_Seam raises an exception during a launch build, THEN THE provider SHALL continue
   the launch using the unmerged profile, preserving the existing never-raises contract.

### Requirement 3: Record the three providers' actual transport support explicitly

**User Story:** As a maintainer, I want each shipped provider's MCP transport support stated in the
Transport_Table, so that an undeliverable transport is a reported skip rather than a silent claim
of delivery.

#### Acceptance Criteria

1. THE Transport_Table SHALL contain an explicit entry for each of `grok_cli`, `minimax_code`, and
   `omp`.
2. THE Remediation_Process SHALL derive each of the three transport sets by reading that provider's
   serializer, namely grok `_render_mcp_config`, minimax `_serialize_server` and the
   `servers.mcp.json` schema, and omp `_write_extension_root`.
3. WHERE a provider serializer accepts a URL-based MCP entry, THE Transport_Table entry for that
   provider SHALL include the URL transports the serializer accepts.
4. WHERE a provider serializer names a transport differently from the canonical CAO transport
   vocabulary, THE Mcp_Mapper SHALL translate the canonical name to the serializer's name before
   the serializer receives the entry, so that grok receives `"http"` in place of the canonical
   `"streamable-http"` instead of raising a `ProviderError`.
5. THE Mcp_Mapper module docstring SHALL carry one bullet per newly added provider stating the
   evidence for that provider's transport set, in the format used by the existing `codex` and
   `antigravity_cli` bullets.
6. WHEN the Transport_Table is complete, THE Mcp_Mapper docstring claim that every shipped provider
   is entered explicitly SHALL be true.
7. THE Transport_Table SHALL retain `DEFAULT_TRANSPORTS` as the stdio-only fallback for
   providers added later.
8. THE canonical-to-native translation of criterion 4 SHALL be proven by the `grok_cli`
   launch-delivery test of Requirement 5, which asserts the translated native value in the generated
   `config.toml`, so that the translation is demonstrated at the artifact rather than only at the
   mapper.

### Requirement 4: Correct every prose enumeration of the wired providers

**User Story:** As a reader of the code and docs, I want the enumerated provider lists to match the
wiring, so that a stale count does not mislead the next reviewer.

#### Acceptance Criteria

1. THE `apply_plugin_mcp_servers` docstring SHALL state the current number of Wired_Providers in
   place of the phrase "the five providers".
2. THE `with_plugin_mcp` docstring SHALL name all nine Wired_Providers in place of the phrase
   "Claude Code, Codex, Kimi, Antigravity and Cursor".
3. WHERE `docs/agent-plugins.md` enumerates per-provider MCP delivery, THE Docs_Set SHALL list all
   nine Wired_Providers.
4. THE Remediation_Process SHALL record, in a code comment or a test, the rationale that
   `kiro_cli`, `hermes`, `opencode_cli`, and `mock_cli` need no Delivery_Seam because those modules
   perform no launch-time regeneration of MCP configuration from `profile.mcpServers`, and that
   `kiro_cli` and `opencode_cli` receive MCP configuration on the install path.

### Requirement 5: Prove launch delivery per provider with tests

**User Story:** As a maintainer, I want per-provider tests that assert the plugin MCP server lands
in each provider's native artifact, so that delivery is demonstrated rather than asserted in prose.

#### Acceptance Criteria

1. THE test suite SHALL install a fixture plugin declaring an MCP server, build the `grok_cli`
   launch configuration, and assert the plugin server appears in the generated `config.toml`.
2. THE test suite SHALL install a fixture plugin declaring an MCP server, build the `minimax_code`
   launch configuration, and assert the plugin server appears in the generated `servers.mcp.json`.
3. THE test suite SHALL install a fixture plugin declaring an MCP server, build the `omp` launch
   configuration, and assert the plugin server appears in the generated extension root MCP file.
4. WHILE the Ship_Gate is off, THE test suite SHALL assert that no plugin MCP server appears in any
   of the three providers' generated artifacts.
5. THE Remediation_Process SHALL model the three tests on the existing
   `test/agent_plugins/test_mcp_launch_delivery.py`.
6. WHEN the `grok_cli` test of criterion 1 builds the launch configuration for a plugin MCP server
   whose canonical transport is `streamable-http`, THE test SHALL assert that the generated
   `config.toml` carries the translated native value `http`, and SHALL fail if the file carries the
   canonical spelling `streamable-http`, because emitting the canonical value is the exact regression
   the `_render_mcp_config` transport check would turn into a launch abort.

### Requirement 6: Close the silent-drop bug class with structural guards

**User Story:** As a maintainer, I want a CI invariant that fails when a provider regenerates MCP
configuration without the Delivery_Seam, so that this review catch becomes a permanent guard.

#### Acceptance Criteria

1. THE Seam_Drift_Guard SHALL enumerate every module under
   `src/cli_agent_orchestrator/providers/` that reads `mcpServers` from a loaded profile.
2. IF an enumerated module neither calls the Delivery_Seam nor appears on the exemption allowlist,
   THEN THE Seam_Drift_Guard SHALL fail and SHALL name the offending module and line.
3. THE Seam_Drift_Guard exemption allowlist SHALL carry, per entry, a comment stating why that
   module needs no Delivery_Seam.
4. WHEN a Delivery_Seam call is removed from any single Wired_Provider, THE Seam_Drift_Guard SHALL
   fail, and THE Remediation_Process SHALL confirm that failure by temporarily reverting one wiring
   locally.
5. IF a Wired_Provider is absent from the Transport_Table, THEN THE Transport_Coverage_Guard SHALL
   fail and SHALL name the missing provider.

### Requirement 7: Stop plugin MCP servers from silently widening restricted roles

**User Story:** As an operator running a deliberately restricted reviewer or supervisor role, I want
installing a plugin to leave that role's tool allowlist unchanged unless I opt in, so that plugin
code does not gain tool access I did not grant.

**Decision (settled as an implementation default; policy sign-off still owed).** The default is
`OMIT` — no auto-grant of plugin-delivered MCP servers — with an explicit `pluginMcp` opt-in and
fail-closed classification, so that undeterminable provenance is treated as plugin-delivered. The
install path persists the widened allowlist into native agent files, so a wrong default is durable,
and restricted roles exist precisely so that tools are not gained implicitly. Reversal to
grant-plus-warning remains a one-constant change. Recorded in the Rev 2 addendum (D3) at PR #43
`b1be41b`. Two riders attach, stated as criteria 13 through 15: the omission must be surfaced and not
only the grant, and the posture stays on the handoff §4 maintainer sign-off list because an
implemented default is not settled policy.

#### Acceptance Criteria

1. THE Tool_Resolver SHALL accept the Plugin_Delivered_Server names as an input distinct from the
   Profile_Declared_Server names, where a Profile_Declared_Server is an `mcpServers` key present in
   the agent profile as authored before any plugin merge, and a Plugin_Delivered_Server is an
   `mcpServers` key introduced by the plugin merge.
2. WHEN a merged `mcpServers` mapping is passed to tool resolution, THE Remediation_Process SHALL
   supply the Plugin_Delivered_Server names from exactly one of two sources: the
   `McpDeliveryResult` produced by the delivery path, or an `mcp_server_names` list captured before
   the plugin merge.
3. WHILE the target profile is a Restricted_Profile, WHEN tool resolution runs, THE Tool_Resolver
   SHALL omit the `@<server>` grant for every Plugin_Delivered_Server that is not named by an
   opt-in setting, including the case where no opt-in setting is present.
4. WHERE a plugin-MCP opt-in setting is present on the profile or the role, THE Tool_Resolver SHALL
   append one `@<server>` grant for each Plugin_Delivered_Server named by that setting, using the
   profile-level setting in preference to the role-level setting when both are present.
5. WHERE a profile's effective allowlist contains `"*"`, THE Tool_Resolver SHALL return that
   allowlist with no `@<server>` entry appended for any Profile_Declared_Server or
   Plugin_Delivered_Server, unchanged from the current implementation.
6. WHEN a `@<server>` grant for a Plugin_Delivered_Server is appended to a Restricted_Profile's
   allowlist, THE Tool_Resolver SHALL emit exactly one log record at WARNING level per granted
   server per resolution call, naming the server and the profile, and SHALL emit no WARNING record
   for omitted servers.
7. WHEN an agent-plugin install or list command completes, THE agent-plugin CLI SHALL output, for
   each Plugin_Delivered_Server that affects a Restricted_Profile, the profile name and whether the
   `@<server>` grant was granted or omitted.
8. THE Docs_Set SHALL document the opt-in setting's location, accepted values, default value, and
   the omit-by-default behavior in both `docs/agent-profile.md` and `docs/agent-plugins.md`.
9. THE test suite SHALL include cases covering a Restricted_Profile with an installed plugin server
   (grant omitted), a `"*"` profile (allowlist unchanged), the opt-in path (grant appended and
   WARNING emitted), a server name declared by both the profile and a plugin, and an entry whose
   provenance cannot be determined.
10. WHILE the target profile is a Restricted_Profile, WHEN tool resolution runs, THE Tool_Resolver
    SHALL append exactly one `@<server>` grant for each Profile_Declared_Server not already present
    in the allowlist, SHALL treat a server name that is both Profile_Declared and Plugin_Delivered
    as a Profile_Declared_Server, and SHALL leave the non-MCP entries of the allowlist unchanged in
    count and order.
11. IF a plugin-MCP opt-in setting is present but its value is neither the literal `"*"` nor a list
    of server names, THEN THE Tool_Resolver SHALL omit every Plugin_Delivered_Server grant, emit one
    log record at WARNING level naming the profile and the rejected setting, and complete resolution
    without raising an error.
12. IF the provenance of a merged `mcpServers` entry cannot be determined — because neither an
    `McpDeliveryResult` nor a pre-merge `mcp_server_names` list is supplied, or because the entry
    still carries the `x-cao-pre-expanded` marker — THEN THE Tool_Resolver SHALL classify that entry
    as a Plugin_Delivered_Server.
13. WHEN a `@<server>` grant for a Plugin_Delivered_Server is omitted from a Restricted_Profile's
    allowlist, THE Tool_Resolver SHALL emit exactly one log record per omitted server per resolution
    call at a level below WARNING, naming the server, the profile, and the opt-in setting that would
    grant it, so that an operator report of "my plugin's MCP server is not available" is diagnosable
    from the log alone.
14. WHEN an agent-plugin install or list command completes, THE agent-plugin CLI SHALL name each
    omitted Plugin_Delivered_Server together with the profile it was omitted for and the opt-in
    setting that would grant it, so that the omission is visible on a management surface rather than
    only the grant.
15. THE Remediation_Process SHALL keep the cross-role auto-grant posture on the handoff §4 maintainer
    sign-off list required by Requirement 24, SHALL record in the PR description that an implemented
    default is not settled policy, and SHALL record that reversal to grant-plus-warning is a
    one-constant change.

### Requirement 8: Correct the README gate description

**User Story:** As a reader evaluating whether the feature is live, I want the README to state that
every surface is default-off, so that the README does not contradict the code.

#### Acceptance Criteria

1. THE Docs_Set SHALL state in `README.md` that the CLI, HTTP API, TUI, and web surfaces are each
   default-off behind `CAO_AGENT_PLUGINS_ENABLED`.
2. THE Docs_Set SHALL remove the claim "the HTTP API is available" from `README.md`.
3. THE `README.md` agent-plugins description SHALL agree with `docs/agent-plugins.md` on the gate
   posture.

### Requirement 9: Add the agent_plugins package to the package map

**User Story:** As a contributor navigating the codebase, I want the new package in `CODEBASE.md`,
so that the repository's documentation-maintenance rule holds.

#### Acceptance Criteria

1. THE Docs_Set SHALL add `src/cli_agent_orchestrator/agent_plugins/` to the `CODEBASE.md` package
   map in that file's established format.
2. THE `CODEBASE.md` entry SHALL list each module of the package with a one-line responsibility,
   covering `containment`, `gate`, `installer`, `mcp_delivery`, `mcp_mapping`, `models`,
   `projection`, `provenance`, `resolver`, `store`, and `validation`.
3. THE `CODEBASE.md` entry SHALL list `provenance` unconditionally, because Requirement 11 retains
   and wires the Provenance_Module, and the `provenance` line SHALL name the three consumers that
   read it.
4. WHERE the `CODEBASE.md` map covers package directories and test directories, THE Docs_Set SHALL
   add the Package_Dir and `test/agent_plugins/`.

### Requirement 10: Remove the stale permanent-exemption count from the repository

**User Story:** As a reviewer checking the AC6 narrative, I want no in-repository text claiming two
permanent vocabulary exemptions, so that the narrative matches the three-entry guard.

#### Acceptance Criteria

1. THE Remediation_Process SHALL search the repository for the phrases "exactly two" and "two
   permanent exemptions" in the context of vocabulary exemptions.
2. IF an in-repository occurrence describes the vocabulary exemption count, THEN THE Docs_Set SHALL
   correct that occurrence to match the three entries of `_VOCABULARY_BACKLOG_DOCS`.
3. IF the search finds no in-repository occurrence describing the vocabulary exemption count, THEN
   THE Remediation_Process SHALL record that result in the work item's commit body, because the
   remaining claim is in the PR body and is a human edit under Requirement 24.
4. THE Remediation_Process SHALL leave `test/agent_plugins/test_naming_migration.py` behavior
   unchanged, because the guard is already correct.

### Requirement 11: Wire the provenance module to its documented consumers

**User Story:** As an operator whose system prompt can contain plugin-contributed skill content, I
want to see which plugin contributed each skill, so that the documented prompt-injection mitigation
is reachable from a surface rather than only from library code.

**Decision (settled) — RETAIN AND WIRE, not remove.** The original "removal is smaller and safer"
call rested on a grep that excluded `test/`. `provenance.owning_plugin` is the collision-rule oracle
at 14 assertion sites in `test/agent_plugins/test_projection.py` and
`test/agent_plugins/test_installer_property.py`, and the module is the prompt-injection mitigation of
record — the operator's only "which plugin put this in my system prompt" affordance. All three
consumers sit behind the existing default-off Ship_Gate, so wiring them widens no shipped surface,
and wiring satisfies the reviewer's "remove or wire up" on the "wire up" branch. Recorded in the Rev 2
addendum (D1) at PR #43 `b1be41b`.

#### Acceptance Criteria

1. THE Remediation_Process SHALL retain the Provenance_Module and SHALL import it from each consumer
   its docstring names, namely `cao plugin list`, the `cao skills list` annotation, and the
   `/plugins` payload together with the web panel that renders that payload.
2. THE Remediation_Process SHALL place each of the three wired consumers behind the existing
   Ship_Gate, so that the extent of the shipped default-off surface is unchanged.
3. THE test suite SHALL contain one test per wired consumer, asserting that the consumer reports the
   owning plugin of a skill contributed by an installed fixture plugin.
4. THE Remediation_Process SHALL leave the 14 existing `owning_plugin` assertions in
   `test/agent_plugins/test_projection.py` and `test/agent_plugins/test_installer_property.py`
   unchanged, because those assertions are the collision-rule oracle.
5. WHILE the Ship_Gate is off, THE three wired consumers SHALL produce output identical to the output
   they produce before this change.
6. THE Docs_Set SHALL state that the Provenance_Module is the prompt-injection mitigation of record
   and SHALL name the three surfaces through which owning-plugin attribution is visible.
7. THE Docs_Set SHALL list `provenance` in the `CODEBASE.md` package-map entry required by
   Requirement 9.
8. WHERE a maintainer later directs that the Provenance_Module be removed instead, THE
   Remediation_Process SHALL remove the module together with any test that only exercises the module,
   SHALL leave no reference to a `provenance` symbol from the agent-plugins package in the `src/`,
   `web/`, and `tui/` trees, SHALL state in the commit body that the removal is deliberate and that
   the module may return alongside a consumer, and SHALL first replace the 14 oracle assertions of
   criterion 4 with an equivalent collision-rule oracle.

### Requirement 12: Enforce the web plugins-tab gate in a rendering test

**User Story:** As a maintainer, I want the web half of the ship gate tested at the app level, so
that gate enforcement is verified rather than only the flag's default value.

#### Acceptance Criteria

1. WHILE the plugins-tab flag is false, THE test suite SHALL render the Web_App and assert the
   Plugins tab and its route are absent.
2. WHILE the plugins-tab flag is mocked true, THE test suite SHALL render the Web_App and assert
   the Plugins tab is present.
3. THE test SHALL exercise `web/src/App.tsx` rather than only the `web/src/featureFlags.ts`
   constant.
4. THE Remediation_Process SHALL keep the shipped default value of `PLUGINS_TAB_ENABLED` false.

### Requirement 13: Align the ship gate's truthy spellings with the canonical set

**User Story:** As an operator setting the gate to `on`, I want that spelling accepted, so that the
gate's documented parity with the other CAO boolean surfaces holds.

**Decision (settled).** Add `"on"` by reusing the Canonical_Bool_Set rather than by extending
`gate.py`'s private `_TRUTHY` tuple, so that the parity claim cannot drift from the canonical
definition. Recorded in the Rev 2 addendum (D5) at PR #43 `b1be41b`. The alternative — keeping the
narrow three-value set and dropping the parity claim — was considered and not chosen; it is recorded
here for the review record only and generates no work item.

#### Acceptance Criteria

1. THE Ship_Gate SHALL treat each member of the Canonical_Bool_Set as truthy, including `"on"`, and
   SHALL read that set from its canonical definition rather than from a duplicate literal in
   `gate.py`.
2. THE Ship_Gate SHALL remain off when the environment variable is unset, empty, or a value outside
   the Canonical_Bool_Set.
3. THE Remediation_Process SHALL update `test/agent_plugins/test_ship_gate.py` to cover the added
   spelling.
4. THE Ship_Gate docstring and the Docs_Set SHALL state the parity claim in terms of the
   Canonical_Bool_Set rather than by enumerating spellings, so that a later change to that set cannot
   leave the claim false.

### Requirement 14: Delete the dead reserved-env branch and correct the isolation claim

**User Story:** As a maintainer, I want no unreachable branch in `_map_stdio` and no false per-entry
isolation claim, so that the mapper's documented behavior matches the vendored schema's contract.

**Decision (settled) — Option B.** The reproduction is complete and the outcome is confirmed fact,
not a branch to discover: the vendored schema rejects reserved env keys through
`env.propertyNames.not.enum`, and `map_mcp_config` early-returns on `_schema_errors` at
`mcp_mapping.py:280`. A two-entry fixture whose first entry declares a reserved key therefore yields
`valid=False`, `servers=[]`, and `findings=["mcp.invalid"]`, and the `_map_stdio` reserved-env branch
never executes. Option B is chosen: delete the dead branch, correct the per-entry-isolation claim, and
keep the fixture as a regression test. Whole-document rejection is the vendored-schema contract;
Option A, restoring per-entry isolation, would be a validation-semantics change whose blast radius
covers every whole-document rejection plus conformance-corpus drift risk, and does not belong in a
remediation PR. Recorded in the Rev 2 addendum (C1, D2) at PR #43 `b1be41b`.

#### Acceptance Criteria

1. THE Mcp_Mapper SHALL contain no reserved-env-key handling branch in `_map_stdio`, because
   `map_mcp_config` returns on `_schema_errors` at `mcp_mapping.py:280` before that branch can
   execute.
2. THE `_map_stdio` docstring and the Docs_Set SHALL contain no statement that a reserved env key
   causes only the individual entry to be skipped, and SHALL state instead that a reserved env key
   invalidates the whole MCP configuration document at schema validation.
3. THE test suite SHALL retain, as an automated regression test, a fixture MCP configuration
   containing exactly two stdio server entries, where the first entry declares an env map containing
   exactly one reserved key (`PLUGIN_ROOT` or `PLUGIN_DATA`) and the second entry is schema-valid and
   declares no reserved key.
4. WHEN the fixture of criterion 3 is mapped in a single mapping invocation, THE regression test
   SHALL assert that `valid` is false, that the mapped server set is empty, and that the emitted
   finding codes are exactly `["mcp.invalid"]`, and SHALL fail when any of those three observations
   changes.
5. THE Remediation_Process SHALL record the reproduction evidence — the schema construct
   `env.propertyNames.not.enum` and the early return at `mcp_mapping.py:280` — in the work item's
   commit body.
6. THE Remediation_Process SHALL leave the vendored schema unchanged and SHALL leave the
   whole-document rejection semantics of `map_mcp_config` unchanged.
7. WHERE a maintainer later directs that per-entry leniency be restored, THE Remediation_Process SHALL
   treat that as a separate change carrying its own review, because it alters validation semantics for
   every whole-document rejection and requires a conformance-corpus assessment.

### Requirement 15: Make projection ownership checks symmetric

**User Story:** As an operator who edited a projected skill out of band, I want materialization and
sweep to agree on ownership, so that an out-of-band edit produces one consistent outcome.

This item is reviewer-reported and unverified; the work begins with reproduction.

#### Acceptance Criteria

1. THE Remediation_Process SHALL produce a reproduction that, for each of at least the following
   three out-of-band edit classes applied to a projected skill between a first and a second install —
   content modified with ownership metadata left intact, ownership metadata removed or altered with
   content intact, and the projected file deleted — records for both the `_materialize` path and the
   sweep path: which ownership signals each path reads, the ownership classification each path
   derives (owned, user-modified, not-owned, or undeterminable), and the resulting action each path
   takes (overwrite, preserve, remove, or skip).
2. IF the reproduction shows that, for the same edit class and the same on-disk and stored state,
   `_materialize` and the sweep derive different ownership classifications or take different actions,
   THEN THE Projection_Engine SHALL be changed so that both paths read the same ownership signal set,
   derive the same classification, and take actions that agree on whether the projected file is
   retained or replaced or removed.
3. THE test suite SHALL retain the reproduction as a regression test that, for each of the three edit
   classes in criterion 1, asserts the classification and the retained, replaced, or removed outcome
   of both paths, and fails if the two paths diverge on any class.
4. IF the reproduction shows both paths already deriving the same classification and taking agreeing
   actions for all three edit classes, THEN THE Remediation_Process SHALL record that finding,
   including the observed classification and action per edit class, in the work item's commit body,
   and SHALL still add the reproduction as the regression test required by criterion 3.
5. IF a projected skill is classified user-modified, THEN THE Projection_Engine SHALL preserve the
   existing file content byte-for-byte in both the `_materialize` path and the sweep path, SHALL NOT
   overwrite or delete it, and SHALL emit a message identifying the skill and indicating that it was
   skipped because it was modified outside projection.
6. IF the ownership signals for a projected skill are conflicting or unreadable so that the
   classification is undeterminable, THEN THE Projection_Engine SHALL classify it as not-owned in
   both paths, SHALL leave the file and its stored projection record unchanged, and SHALL emit a
   warning identifying the skill and indicating that ownership could not be determined, without
   aborting projection of the remaining skills.

### Requirement 16: Harden the git plugin source resolver against SSRF

**User Story:** As an operator installing a plugin from a git URL, I want the same host and scheme
controls the HTTP source path applies, so that a crafted git URL cannot reach an internal service.

#### Acceptance Criteria

1. THE Git_Resolver SHALL reject a source URL whose scheme is outside an explicit scheme allowlist
   containing `https`.
2. WHERE `ssh` is included in the scheme allowlist, THE Docs_Set SHALL state the additional trust
   that inclusion grants.
3. THE Git_Resolver SHALL reject a source URL whose host is outside a host allowlist consistent with
   the Http_Resolver_Hardening host allowlist, and SHALL name the rejected host in the error.
4. THE Git_Resolver SHALL reject a source URL carrying userinfo credentials.
5. WHERE an operator sets the host-allowlist override environment variable, THE Git_Resolver SHALL
   use the override hosts, following the comma-separated pattern of
   `CAO_PROFILE_ALLOWED_HOSTS`.
6. THE test suite SHALL cover a blocked host, a blocked scheme, and a credential-bearing URL.
7. THE Git_Resolver SHALL preserve the existing non-behaviors of skipping submodules and skipping
   tags.

### Requirement 17: Document the credential-shaped env value trust model

**User Story:** As an operator whose plugin declares a credential-shaped env value, I want CAO's
handling documented, so that the trust model is explicit rather than implied by a warning.

**Decision (settled).** Warn-only, with no code change. Refusing the entry produces false positives on
long base64 configuration values, and redacting the value breaks authentication silently. The trust
model is therefore documented rather than enforced. Recorded in the Rev 2 addendum (D4) at PR #43
`b1be41b`.

#### Acceptance Criteria

1. THE Mcp_Mapper SHALL retain its existing warning-only handling of a credential-shaped env value,
   with no change to mapper behavior.
2. THE Docs_Set SHALL document the trust model in `docs/agent-plugins.md`, stating that a
   credential-shaped env value is written to provider configuration in cleartext, that the warning is
   the only control, and that environment-variable indirection — a `${VAR}` reference or a value
   supplied through `cao env` — is the supported path for a real secret.
3. THE Docs_Set SHALL state that the maintainers chose warning-only over refusing the entry and over
   redacting the value, and SHALL name and date that decision, citing the Rev 2 addendum (D4,
   2026-09-06) at PR #43 `b1be41b`.
4. THE Remediation_Process SHALL add no test asserting refusal or redaction, because neither behavior
   is implemented.

### Requirement 18: Add the agent-plugins entry to the Chinese README

**User Story:** As a reader of `README.zh-CN.md`, I want the agent-plugins entry present, so that
the translated README does not omit a shipped subsystem.

#### Acceptance Criteria

1. THE Docs_Set SHALL add an agent-plugins entry to `README.zh-CN.md`.
2. THE `README.zh-CN.md` entry SHALL mirror the corrected English text of Requirement 8, including
   the statement that every surface is default-off.

### Requirement 19: Minimize the lockfile diff

**User Story:** As a reviewer reading the diff, I want `uv.lock` to change only where a dependency
change requires, so that 51 lines of reordering churn do not obscure the review.

#### Acceptance Criteria

1. THE Remediation_Process SHALL regenerate `uv.lock` starting from the Upstream_Main copy of
   `uv.lock` and re-running the lock command against the Remediation_Branch `pyproject.toml`.
2. WHERE the Remediation_Branch adds no Python dependency, THE `uv.lock` diff against Upstream_Main
   SHALL be empty.
3. WHERE the Remediation_Branch adds a Python dependency, THE `uv.lock` diff against Upstream_Main
   SHALL contain only hunks that dependency change requires.

### Requirement 20: Record the singular package directory name as accepted

**User Story:** As a contributor, I want the singular directory name recorded as accepted, so that a
P3 naming preference does not add churn to an already large PR under review.

**Decision (settled).** Skip the rename and record the singular name as accepted naming. The measured
cost is 60 occurrences across 11 files, 23 file moves, plus the `Makefile` and CI targets — churn
introduced mid-review for a P3 nit, which fails the churn test. The historical design record must not
be retro-edited to match a name that was never adopted. Recorded in the Rev 2 addendum (D6) at PR #43
`b1be41b`.

#### Acceptance Criteria

1. THE Remediation_Process SHALL record the measured change surface of renaming the Package_Dir to
   `agent-plugins/`, namely 60 occurrences across 11 files, 23 file moves, and the `Makefile` and
   `.github/workflows/ci.yml` targets.
2. THE Remediation_Process SHALL skip the rename and SHALL leave the Package_Dir named
   `agent-plugin/`.
3. THE Remediation_Process SHALL record the singular name as accepted naming in the PR body, together
   with the measured cost of criterion 1 and the reason the rename was declined.
4. THE Remediation_Process SHALL leave the `Makefile` targets `check-agent-plugin` and `agent-plugin`,
   the CI steps in `.github/workflows/ci.yml`, `test/agent_plugins/test_packages.py`, and
   `test/test_agent_plugins_docs.py` unchanged.
5. THE Remediation_Process SHALL make no retro-edit to the historical design record for the sake of
   the declined rename, so that documents written against the singular name stay as written.

### Requirement 21: Track the OpenCode shared-file name clash

**User Story:** As a maintainer, I want the OpenCode profile-name-clash sub-case tracked, so that a
known pre-existing issue is recorded rather than lost.

#### Acceptance Criteria

1. THE Backlog_Doc SHALL contain an entry describing the OpenCode shared-file profile-name-clash
   sub-case on the install path.
2. THE Backlog_Doc entry SHALL state that the issue is a pre-existing class and is out of scope for
   PR #584.
3. THE Remediation_Process SHALL make no code change to the OpenCode install path for this item.

### Requirement 22: Hold the non-negotiable process constraints

**User Story:** As a maintainer, I want the gate posture, push discipline, commit format, and
documentation rule held throughout, so that the remediation does not introduce a new review finding.

#### Acceptance Criteria

1. THE Ship_Gate SHALL remain default-off, and no requirement in this spec SHALL change the default
   to on.
2. THE Remediation_Process SHALL push without the `--no-verify` flag.
3. IF a pre-push hook fails on files this remediation did not change, THEN THE Remediation_Process
   SHALL fix or scope that hook in a separate commit rather than bypassing the hook.
4. THE Remediation_Process SHALL format every commit message as a Conventional Commit and SHALL
   produce one focused commit per work item.
5. WHEN a commit changes a package or module, THE same commit SHALL update `CODEBASE.md` and the
   affected `docs/*.md` files.
6. THE Remediation_Process SHALL leave the Event_Plugin_Subsystem code unchanged.

### Requirement 23: Pass the verification suite under both gate states

**User Story:** As a maintainer, I want the full gate set green with the feature off and on, so that
neither state regresses.

#### Acceptance Criteria

1. THE Verification_Suite SHALL run `make check-agent-plugins-schemas`, `make check-agent-plugin`,
   `uv run pytest test/agent_plugins/ test/services/ test/utils/ test/api/ -q`, `uv run pytest -q`,
   and the web suite, in that order.
2. THE Verification_Suite SHALL pass with `CAO_AGENT_PLUGINS_ENABLED` unset.
3. THE Verification_Suite SHALL pass with `CAO_AGENT_PLUGINS_ENABLED` set to `1`.
4. THE full pytest run SHALL report zero net-new failures compared to a pristine Upstream_Main
   checkout.
5. THE spot-check `grep -rn "with_plugin_mcp" src/cli_agent_orchestrator/providers/` SHALL list
   `grok_cli`, `minimax_code`, and `omp` alongside the original six providers.
6. THE spot-check `grep -n "grok_cli\|minimax_code\|omp"
   src/cli_agent_orchestrator/agent_plugins/mcp_mapping.py` SHALL show an explicit transport entry
   for each of the three providers.
7. THE spot-check `grep -c agent_plugins CODEBASE.md` SHALL return a count of at least 1, and
   `grep -c "agent-plugins" README.zh-CN.md` SHALL return a count of at least 1.
8. THE spot-check `grep -rn "HTTP API is available" README.md` SHALL return no match.
9. THE spot-check `git diff main...HEAD -- uv.lock` SHALL return an empty diff or a
   dependency-only diff.
10. WHEN one Delivery_Seam wiring is temporarily reverted, THE Seam_Drift_Guard SHALL fail.

### Requirement 24: Exclude human process items from implementation scope

**User Story:** As the implementing agent, I want the handoff's human actions marked out of scope, so
that no commit claims to resolve items only a person can complete.

#### Acceptance Criteria

1. THE Remediation_Process SHALL treat the following handoff §4 items as out of scope for
   implementation: re-requesting review from @haofeif and @fanhongy; obtaining M1 and AC6 maintainer
   sign-off; editing the PR body narrative; and pre-push hook hygiene on the author's account.
2. THE Remediation_Process SHALL record each out-of-scope item as a handoff obligation in the PR
   description or a handoff note, naming the person who must act.
3. THE Remediation_Process SHALL produce no commit message claiming to resolve review
   `pullrequestreview-5074181308`.
4. THE Remediation_Process SHALL list the PR-body narrative corrections for the author, namely the
   "22 cases" count, the "its diff is empty" claim about `docs/plugins.md`, the stale `==2.4.1` pin,
   the "exactly two permanent exemptions" claim, and the refreshed count of Wired_Providers.
5. THE Remediation_Process SHALL rework none of the 13 prior findings from @haofeif and @fanhongy,
   because the new review verified each as substantively addressed.

### Requirement 25: Keep the delivery seam ungated

**User Story:** As a maintainer, I want the Delivery_Seam to remain free of a Ship_Gate check, so that
the gate stays a management-surface release gate rather than becoming a data-path switch.

**Decision (settled).** This is the seventh decision — a question the review never asked and the first
draft of this spec left implicit. The Delivery_Seam does not consult the Ship_Gate, by design.
Gate-off protection holds derivatively: gate off implies no install path, which implies an empty
plugin store, which implies no delivery. Gating the seam would change six wired providers and their
existing tests for no security gain. Recorded in the Rev 2 addendum (D7) at PR #43 `b1be41b`.

#### Acceptance Criteria

1. THE Delivery_Seam SHALL contain no Ship_Gate check, and THE Remediation_Process SHALL add no guard
   clause to `with_plugin_mcp`.
2. THE Remediation_Process SHALL verify gate-off protection through the derivation that a disabled
   Ship_Gate leaves no install path, which leaves the plugin store empty, which leaves the
   Delivery_Seam with nothing to merge, rather than through a check inside the seam.
3. THE test suite SHALL assert the gate-off outcome at the artifact level, per Requirement 2
   criterion 6 and Requirement 5 criterion 4, and SHALL NOT assert that the Delivery_Seam reads the
   Ship_Gate.
4. THE Docs_Set SHALL state that the Ship_Gate is a management-surface release gate and not a
   data-path switch, and SHALL state the gate-off derivation of criterion 2.
5. WHERE a maintainer later directs that the Delivery_Seam consult the Ship_Gate, THE
   Remediation_Process SHALL treat that as a change of roughly fifteen lines across the seam, the six
   original Wired_Provider call sites, and their existing tests, and SHALL record that the change
   yields no security gain over the derivation of criterion 2.

## Correctness Properties

These properties are stated for property-based testing. Each names the requirement it verifies.

1. **Delivered-set union** (R2, R5): For every provider module that generates native MCP
   configuration from a launch-time profile read, and for every combination of profile-declared
   servers and installed plugin servers, the generated artifact contains exactly the union of the
   Profile_Declared_Servers and the gate-enabled Plugin_Delivered_Servers.
2. **Gate-off byte identity** (R2, R5, R23): For every profile and every installed plugin set, with
   the Ship_Gate off, each provider's generated MCP artifact is byte-identical to the artifact
   generated from the same profile with no plugins installed.
3. **Allowlist widening is opt-in** (R7): For every profile and every installed plugin set, the
   Tool_Resolver output contains an `@<server>` grant for a Plugin_Delivered_Server only when the
   profile's effective allowlist contains `"*"` or an explicit plugin-MCP opt-in setting names that
   server; an entry whose provenance cannot be determined is treated as a Plugin_Delivered_Server.
4. **Grant monotonicity for declared servers** (R7): For every profile, the set of `@<server>`
   grants derived from Profile_Declared_Servers is unchanged by installing or removing any plugin.
5. **Seam-guard soundness** (R6): For every provider module in the tree, the Seam_Drift_Guard
   passes if and only if that module calls the Delivery_Seam or appears on the commented exemption
   allowlist.
6. **Transport-table totality** (R3, R6): For every Wired_Provider, the Transport_Table contains an
   explicit key, so no first-party provider resolves through `DEFAULT_TRANSPORTS`.
7. **Transport round trip** (R3): For every MCP entry whose transport a provider serializer
   accepts, mapping the entry to that provider's native format and reading the transport back
   yields the transport the entry declared, modulo the documented canonical-to-native name
   translation.
8. **Gate truthiness** (R13): For every string, the Ship_Gate returns true if and only if the
   string's stripped lowercase form is a member of the Canonical_Bool_Set.
9. **Reserved env key invalidates the whole configuration** (R14): RETRACTED as originally stated —
   "per-entry mapping isolation" does not hold and is not the vendored schema's contract. Replaced by
   its negation at the configuration level: for every MCP configuration containing at least one entry
   whose env map declares a reserved key, mapping the configuration yields `valid=False`, an empty
   mapped-server set, and the finding code `mcp.invalid`, regardless of how many other entries are
   schema-valid. The two-entry fixture of Requirement 14 criterion 3 pins this outcome.
10. **Projection idempotence and symmetry** (R15): For every projected skill set, running
    materialization twice with no intervening change produces the same on-disk result as running it
    once, and materialization and sweep classify the ownership of any given out-of-band edit
    identically.
11. **Resolver rejection closure** (R16): For every URL whose scheme is outside the scheme
    allowlist, whose host is outside the host allowlist, or which carries userinfo, the Git_Resolver
    raises before any network or filesystem write occurs.
12. **Lockfile determinism** (R19): Regenerating `uv.lock` from the same `pyproject.toml` and the
    same starting lock produces a byte-identical file.

## Decision Record — all Open Decisions RESOLVED

This section was the spec's Open Decisions list. Every entry has been decided by the plan author and
is retained here as a decision record, not as a blocker. Each entry names the chosen branch, the
deciding rationale, and the citation. All citations are to the Rev 2 addendum of
`HANDOFF-PR584-review-5074181308.md` at plauzy/cli-agent-orchestrator PR #43 commit `b1be41b`
(2026-09-06). Nothing below blocks the design or the implementation.

1. **Cross-role auto-grant posture** (R7) — **RESOLVED: default `OMIT`, explicit `pluginMcp` opt-in,
   fail-closed classification.** Deciding rationale: the install path persists the widened allowlist
   into native agent files, so a wrong default is durable rather than transient, and restricted roles
   exist precisely so that tools are not gained implicitly; undeterminable provenance is therefore
   treated as plugin-delivered. Two riders: the omission must be surfaced through both a log record
   and the plugin-list output, and the posture stays on the handoff §4 maintainer sign-off list because
   an implemented default is not settled policy. Reversal to grant-plus-warning remains a one-constant
   change. Citation: addendum D3.
2. **Provenance module disposition** (R11) — **RESOLVED: RETAIN AND WIRE, not remove.** Deciding
   rationale: the earlier removal call rested on a grep that excluded `test/`;
   `provenance.owning_plugin` is the collision-rule oracle at 14 assertion sites and the module is the
   prompt-injection mitigation of record, being the operator's only "which plugin put this in my
   system prompt" affordance. All three consumers sit behind the existing default-off gate, so wiring
   widens no shipped surface. Removal is demoted to R11 criterion 8, available if a maintainer later
   directs it. Citation: addendum D1.
3. **Gate truthy set** (R13) — **RESOLVED: add `"on"` by reusing the Canonical_Bool_Set.** Deciding
   rationale: reusing the canonical set makes the parity claim structurally true rather than
   coincidentally true, so a later change to that set cannot leave the docstring false. The narrow
   three-value alternative is recorded as considered and not chosen. Citation: addendum D5.
4. **Credential-shaped env values** (R17) — **RESOLVED: warn-only, no code change, trust model
   documented.** Deciding rationale: refusal produces false positives on long base64 configuration
   values, and redaction breaks authentication silently; the honest control is documentation plus
   `${VAR}` / `cao env` indirection as the supported path for a real secret. The decision is named and
   dated in the Docs_Set per R17 criterion 3. Citation: addendum D4.
5. **Package directory rename** (R20) — **RESOLVED: skip the rename, record the singular name as
   accepted naming.** Deciding rationale: 60 occurrences across 11 files and 23 file moves, plus
   `Makefile` and CI targets, is churn introduced mid-review for a P3 nit; and the historical design
   record must not be retro-edited to a name that was never adopted. Citation: addendum D6.
6. **M1 and AC6 sign-off** (R24) — **RESOLVED as out of scope for implementation.** This is not a
   decision the plan author can make: it is a maintainer obligation. It stays on the handoff §4 list
   alongside entry 1's policy sign-off, is recorded as a named human obligation under R24 criteria 1
   and 2, and generates no work item. Citation: addendum §4 carry-over.
7. **Delivery-seam gating** (R25) — **RESOLVED: the seam stays ungated, by design.** This is the
   seventh decision, recording a question the review never asked. Deciding rationale: the Ship_Gate is
   a management-surface release gate, not a data-path switch; gate-off protection holds derivatively
   because gate off implies no install path, which implies an empty store, which implies no delivery.
   Adding a guard clause to `with_plugin_mcp` would touch six wired providers and their tests — roughly
   fifteen lines — for no security gain. Citation: addendum D7.

### Environment precondition (not a decision)

**SSH signing-key availability** (R1): whether the key that signed `282839c1` is available to the
executing session is a property of the execution environment, discovered rather than decided. It
selects between R1's rebase path (criteria 2 through 6) and R1's no-rebase fallback (criteria 7
through 10). Because the branch is mergeable against Upstream_Main with zero conflicts, the fallback
loses nothing, and choosing it removes "unsigned rewrite of a signed commit" as a failure mode rather
than routing that failure mode to a human. Citation: addendum rebase/signature constraint.
