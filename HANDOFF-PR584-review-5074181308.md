# Handoff: resolve PR #584 review `pullrequestreview-5074181308` — for Kiro CLI

> **Rev 2 (2026-09-06):** the Addendum at the end records seven decisions and six corrections
> from the Kiro implementation session's independent verification. Where the Addendum conflicts
> with a section below, the Addendum wins.

**Target PR:** awslabs/cli-agent-orchestrator#584 — `feat(agent-plugins): Agent Plugins 1.0.0 support` (#573)
**PR head at review time:** `282839c1a189112db7dde5b9754a6e7102ef4068` (single signed commit; branch `feat/agent-plugins-573-upstream` on `plauzy/cli-agent-orchestrator`)
**Review:** @gutosantos82, 2026-09-01, verdict **CHANGES_REQUESTED**. Full verbatim review text is in the Appendix.
**Prior reviews:** @haofeif (7 findings) and @fanhongy (3×P1 + 3×P2) — the new reviewer verified all 13 as substantively addressed at head `282839c1`. Do **not** rework those; they only need re-review (process item, see §4).

Every finding below was independently re-verified against a checkout of `282839c1` before this handoff was written. Items marked **[verified]** were confirmed at the exact cited lines; items marked **[reviewer-reported]** were not independently reproduced — verify them first, then fix.

---

## 0. Ground rules for the fix session

- Base your work on `feat/agent-plugins-573-upstream` at `282839c1`. One focused commit per work item (or one commit per section) — Conventional Commits format, e.g. `fix(agent-plugins): deliver plugin MCP servers on grok/minimax/omp launch paths`.
- **Never push with `--no-verify`.** The reviewer flagged the previous `--no-verify` push (mis-scoped hook). If a hook misfires on files you didn't touch, fix or scope the hook in a separate commit instead.
- Gates that must pass before any push: `make check-agent-plugins-schemas`, `make check-agent-plugin`, `uv run pytest test/agent_plugins/ test/services/ test/utils/ test/api/`, plus the web suite (`cd web && npm test`) for §2.7 and full repo suite before finishing.
- The repo has a documentation-maintenance rule: any package/module change must be reflected in `CODEBASE.md` and relevant `docs/*.md`. Apply it to every item below, in the same commit as the code change.
- Do not touch event-plugin code (`docs/plugins.md` machinery); "agent plugins" and "event plugins" are distinct subsystems.
- The feature is default-off behind `CAO_AGENT_PLUGINS_ENABLED` (`src/cli_agent_orchestrator/agent_plugins/gate.py`). Nothing you do may weaken that default.

---

## 1. P1 — must fix

### 1.1 Launch-time MCP delivery misses three providers **[verified]**

**Finding:** Installed plugins' MCP servers are delivered by wrapping the launch-time profile read in `with_plugin_mcp(...)` (`src/cli_agent_orchestrator/agent_plugins/mcp_delivery.py:383`). Exactly six providers are wired: `antigravity_cli`, `claude_code`, `codex`, `copilot_cli`, `cursor_cli`, `kimi_cli`. Three providers re-read the profile at launch and regenerate native MCP config directly from `profile.mcpServers` **without** the merge, so plugin MCP servers are silently dropped — the same silent-failure class review 1 was supposed to have eliminated:

- `src/cli_agent_orchestrator/providers/grok_cli.py:419-421` — `_build_grok_command` does `mcp_servers = profile.mcpServers ...` then `_prepare_grok_home(mcp_servers)` → `_render_mcp_config` writes `config.toml`.
- `src/cli_agent_orchestrator/providers/minimax_code.py:345,360-361` — `_prepare_runtime` loads the profile and calls `self._write_plugin(data_dir, profile.mcpServers)`.
- `src/cli_agent_orchestrator/providers/omp.py:176-177` — command build does `self._write_extension_root(profile.mcpServers)`.

**Fix:**
1. In each of the three providers, import the seam the six wired providers use (`from cli_agent_orchestrator.agent_plugins.mcp_delivery import with_plugin_mcp as _with_plugin_mcp`) and wrap the profile that feeds MCP config generation: `profile = _with_plugin_mcp(load_agent_profile(...), "<provider_key>")` with provider keys `"grok_cli"`, `"minimax_code"`, `"omp"`. Follow the existing call shape (wrap the `load_agent_profile` call, don't replace it — provider tests patch `load_agent_profile` per module; see the design note in `mcp_delivery.py:405-410`). Note grok/minimax/omp load the profile in more than one place; wrap the load that feeds MCP config (grok `_build_grok_command`/`_load_profile`, minimax `_prepare_runtime`, omp's command build), and make sure a second unwrapped read cannot be reintroduced for MCP purposes.
2. Add the three providers to `PROVIDER_TRANSPORTS` in `src/cli_agent_orchestrator/agent_plugins/mcp_mapping.py:100` with their **actual** transport support (read each provider's serializer first: grok `_render_mcp_config` TOML, minimax `servers.mcp.json` schema, omp extension `mcpServers` JSON). Today they silently fall to `DEFAULT_TRANSPORTS = _STDIO_ONLY`; make the support explicit and add a module-docstring bullet for each, like the existing `codex`/`antigravity_cli` entries at `mcp_mapping.py:78-98`.
3. Update every prose enumeration of the wired providers so it can't drift again: `mcp_delivery.py` docstrings (`apply_plugin_mcp_servers` — "the five providers", and `with_plugin_mcp` — "Claude Code, Codex, Kimi, Antigravity and Cursor…"), and `docs/agent-plugins.md` if it lists per-provider delivery.
4. Confirm (and record in a test or comment) that the remaining providers genuinely need no seam: `kiro_cli`, `hermes`, `opencode_cli`, `mock_cli` have no launch-time `profile.mcpServers` regeneration (verified by grep at `282839c1`); kiro/opencode receive MCP config on the install path.

**Tests (required for "for good"):**
- Per-provider launch-delivery tests mirroring `test/agent_plugins/test_mcp_launch_delivery.py`: install a fixture plugin with an MCP server, launch-build each of the three providers, assert the plugin server lands in the provider's native artifact (grok `config.toml`, minimax `servers.mcp.json`, omp extension root) and that gate-off ⇒ no delivery.
- **A structural drift guard** so the class of bug is closed permanently: a test that walks `src/cli_agent_orchestrator/providers/*.py` and asserts every module that reads `profile.mcpServers` (or `.mcpServers` on a loaded profile) either calls `with_plugin_mcp` or is on an explicit allowlist with a comment saying why (e.g. `base.py`, `mock_cli.py` if exempt). This converts the reviewer's "exact silent-failure class" from a review catch into a CI invariant.
- A companion guard that every provider named in that seam appears in `PROVIDER_TRANSPORTS` (no silent `DEFAULT_TRANSPORTS` fallback for first-party providers).

### 1.2 Standing CHANGES_REQUESTED from maintainers — process, not code

Not fixable by this session. See §4 (human actions). No commits should claim to "resolve" the review; the fixes here plus re-review requests are the path.

---

## 2. P2 — should fix

### 2.1 Cross-role uniform MCP auto-grant **[verified]**

**Finding:** `src/cli_agent_orchestrator/utils/tool_mapping.py:161-165` (`resolve_allowed_tools`) appends `@<server>` for **every** `mcp_server_names` entry to any non-`"*"` allowlist. Because plugin MCP servers are merged into `profile.mcpServers` on the install path (`install_service.py:534-535`) and launch paths (`terminal_service.py:468-503`, `cli/commands/launch.py:191-212`), installing a plugin silently widens deliberately-restricted roles (reviewer, supervisor) to include arbitrary plugin-supplied servers.

**Fix (recommended shape — final posture needs maintainer sign-off, see §4):**
1. Make the grant distinguish profile-declared servers from plugin-delivered ones. The delivery result already knows which entries came from plugins (`McpDeliveryResult` in `mcp_delivery.py`; entries carry the `x-cao-pre-expanded` marker until stripped) — thread that set through to `resolve_allowed_tools` callers, or compute `mcp_server_names` from the profile **before** the plugin merge.
2. Default: plugin-delivered servers are auto-granted only to profiles/roles with `"*"` or an explicit opt-in (e.g. a profile-level `pluginMcp: "allow"` field or role setting — pick whichever fits the settings schema; document it in `docs/agent-profile.md` and `docs/agent-plugins.md`).
3. Whatever the default, **surface the widening**: log at WARNING when a plugin server is added to a restricted profile's allowlist, and show it in `cao plugin list` / install output.
4. Tests: restricted-role profile + installed plugin ⇒ no silent `@server` grant (or grant + surfaced warning, per chosen posture); `"*"` profile unchanged; opt-in path grants.

### 2.2 README gate description is false **[verified]**

`README.md:148-152` says CLI/TUI/web "are built but gated off … **the HTTP API is available**." All four `/plugins*` routes 404 by default behind the same gate. Rewrite the bullet: every surface (CLI, HTTP API, TUI, web) is default-off behind `CAO_AGENT_PLUGINS_ENABLED`, pending the naming decision (M1). Keep it consistent with `docs/agent-plugins.md`.

### 2.3 CODEBASE.md omits the new package **[verified]**

`CODEBASE.md` has zero mentions of `agent_plugins`. Add the `src/cli_agent_orchestrator/agent_plugins/` package to the package map with its modules (`containment, gate, installer, mcp_delivery, mcp_mapping, models, projection, provenance*, resolver, store, validation` — \*subject to §2.5) and one-line responsibilities, in the file's established format. Also add the `agent-plugin/` packages directory and `test/agent_plugins/` if the map covers those areas.

### 2.4 "Exactly two permanent exemptions" claim is stale **[verified]**

`test/agent_plugins/test_naming_migration.py:106-110` — `_VOCABULARY_BACKLOG_DOCS` has **three** entries (`cursor-cli.md`, `opencode-cli.md`, `minimax-code.md`). The guard is correct; the narrative isn't. Grep the repo for "exactly two"/"two permanent exemptions" and fix any in-repo occurrence (docs, comments). The PR **body** also makes the claim — that's a human edit, listed in §4.

### 2.5 `provenance.py` is dead production code **[verified]**

`src/cli_agent_orchestrator/agent_plugins/provenance.py` has no importers anywhere in `src/`, `web/`, or `tui/` (verified), while its docstring names consumers (`cao plugin list`, web panel, `cao skills list`) that don't use it. Choose one, per the reviewer: **remove it** (plus any tests that only exercise it), or **wire it** into the named consumers with tests. Removing is the smaller, safer diff for this PR; wiring is feature work. Recommend: remove, and note the intent in the commit body so it can return with a consumer.

### 2.6 Naming collision / gated-closed dormancy — advisory only

No code change. Feeds the M1 decision (§4).

### 2.7 Web gate enforcement untested **[verified — reviewer's tests finding, promoted here because it guards a P-level gate]**

`web/src/featureFlags.ts` exports `PLUGINS_TAB_ENABLED = false`; only the constant's default is asserted (`web/src/test/feature-flags.test.ts`). Add an `App.tsx`-level test: with the flag false the Plugins tab/route is absent from the rendered app; flag true (mocked module) ⇒ present. This makes the web half of the ship gate enforceable, not just declared.

---

## 3. P3 — nits and notes (fix the cheap ones, verify-then-fix the rest)

Code fixes, in the same PR:

1. **Gate truthy parity** **[verified]**: `agent_plugins/gate.py:33` uses `("1","true","yes")` and its docstring claims the "same truthy" behavior as the AG-UI gate — but the AG-UI surface is also enabled via the MCP-Apps ConfigService path, whose canonical bool set `settings_service.py:24` `_BOOL_TRUE_VALUES` includes `"on"`. Align: reuse/mirror the canonical set (add `"on"`), update `test/agent_plugins/test_ship_gate.py` accordingly, or — if the maintainers prefer the narrow set — correct the docstring and docs instead. Prefer adding `"on"`.
2. **`mcp_mapping._map_stdio` reserved-env branch** **[reviewer-reported]** (`mcp_mapping.py:~402-470`): reportedly unreachable because schema validation rejects the whole file first, and the "per-entry isolation" claim is therefore inaccurate. Verify with a fixture (mcp.json with a reserved env key on one of two servers); then either make the branch reachable (per-entry isolation, as documented) or delete it and fix the doc claim. Add the fixture as a regression test either way.
3. **`projection.py` `_materialize` ownership asymmetry vs `_sweep` on out-of-band edits** **[reviewer-reported]** (`projection.py:411` vs the sweep at `:625-737`): reproduce with an out-of-band edit to a projected skill between installs; make the two checks symmetric; add the reproduction as a test.
4. **`resolver.py` `_resolve_git` hardening** **[verified: no allowlist/SSRF handling exists anywhere in `agent_plugins/`]** (`resolver.py:123`): the reviewer says its HTTP sibling has host-allowlist/SSRF hardening — that hardening lives outside this package (find it: grep the repo for the HTTP fetch path used by plugin sources) and mirror it for git URLs: scheme allowlist (`https`, optionally `ssh` with care), host allowlist consistent with the HTTP path, no credential-bearing URLs, and tests for a blocked host/scheme.
5. **Credential-shaped env values written cleartext with only a warning** **[reviewer-reported]** (`mcp_mapping.py` `_CREDENTIAL_VALUE_RE` at `:133`): decide with maintainers — refuse, redact, or keep warn-only; if warn-only stands, document the trust model in `docs/agent-plugins.md`. (Reviewer accepts this as the inherent MCP trust model; a documented decision closes it.)
6. **`README.zh-CN.md` drift** **[verified: zero agent-plugins mentions]**: add the translated agent-plugins entry mirroring §2.2's corrected English text.
7. **`uv.lock` pure churn** **[verified: reordering/removal churn, 51 lines]**: regenerate to minimize the diff against `main` (start from `main`'s `uv.lock`, re-run `uv lock` with this branch's `pyproject.toml`; keep only hunks this PR's dependency changes actually require — if the PR adds no Python deps, the lock diff should be empty).
8. **Singular `agent-plugin/` directory name**: rename to `agent-plugins/` only if cheap (it holds two packages: `cao/`, `cao-contributor/`); update `Makefile` (`check-agent-plugin`, `agent-plugin` targets), CI (`.github/workflows/ci.yml:57,63`), tests (`test_packages.py`, `test_agent_plugins_docs.py`), and docs. If churn is large, record it as accepted naming and skip.
9. **OpenCode shared-file profile-name-clash sub-case** **[reviewer-reported, pre-existing class]** (`install_service.py` OpenCode path): out of scope to fix here per the reviewer; add it to the repo's known-issues/backlog doc so it's tracked, not lost.

PR-body / narrative corrections (human edits, gather into one PR-description update — see §4): "22 cases" (16 corpus rows vs 22 collected items), "its diff is empty" for `docs/plugins.md` (it has an 18-line retitle/banner diff), stale `==2.4.1` pin (committed is `==2.5.0`), "exactly two permanent exemptions" (§2.4), and — after §1.1 lands — refresh the "every launch passes through the seam" claim to name all nine wired providers.

---

## 4. Process items — not fixable by Kiro; for the PR author

1. **Re-request review** from @haofeif and @fanhongy once §1–§3 land (their CHANGES_REQUESTED is binding until they re-review or dismiss; all 13 prior findings are already fixed at `282839c1` per the new review).
2. **M1 / AC6 sign-off**: get an explicit maintainer decision that "gated closed" satisfies "naming decision recorded and applied before any public surface ships" — or the naming decision itself. Also the §2.1 auto-grant posture decision.
3. **Edit the PR body** with the narrative corrections listed at the end of §3.
4. **Hook hygiene**: fix the mis-scoped pre-push hook that motivated the earlier `--no-verify` push (fork branch `fix/pre-push-gate-regressions` may already carry this), so it never recurs.

---

## 5. Definition of done / verification

Run at the end, in order; everything must be green with `CAO_AGENT_PLUGINS_ENABLED` **unset** and again with it set to `1`:

```bash
make check-agent-plugins-schemas
make check-agent-plugin
uv run pytest test/agent_plugins/ test/services/ test/utils/ test/api/ -q
uv run pytest -q                      # full suite; compare failures to pristine main, must be zero net-new
cd web && npm test                    # includes the new App.tsx gate test (§2.7)
```

Spot-checks:
- `grep -rn "with_plugin_mcp" src/cli_agent_orchestrator/providers/` lists grok_cli, minimax_code, omp alongside the original six.
- `grep -n "grok_cli\|minimax_code\|omp" src/cli_agent_orchestrator/agent_plugins/mcp_mapping.py` shows explicit transport entries.
- `grep -c agent_plugins CODEBASE.md` ≥ 1; `grep -c "agent-plugins" README.zh-CN.md` ≥ 1.
- `grep -rn "HTTP API is available" README.md` returns nothing.
- `git diff main...HEAD -- uv.lock` is empty or dependency-only.
- New structural drift-guard test (§1.1) fails if a provider reads `profile.mcpServers` without the seam — verify by temporarily reverting one wiring locally.

---

## Appendix — verbatim review (gutosantos82, 2026-09-01, CHANGES_REQUESTED)

> # PR #584 review @ 282839c1
>
> **Scope:** 194 files, +27556/−124. Single signed commit. reviewDecision=CHANGES_REQUESTED, mergeable=MERGEABLE.
> Seven-angle review (correctness, security, tests, conventions, consistency, conversation, vision) against a local worktree at the PR head; diff exceeded the GitHub API limit and was generated locally from merge-base fb4cc817.
>
> ## Verdict rationale
>
> No P0 anywhere. The core machinery — loader, gate, containment, collision rule, placeholder expansion, store atomicity, OpenCode ownership/disable — was verified against the code and behaves as the PR body claims. However:
>
> 1. A **P1 implementation gap** contradicts a central PR claim: three current providers never receive plugin MCP servers at launch.
> 2. The standing **CHANGES_REQUESTED** from two MEMBER maintainers is procedurally binding until they re-review; an approve from us cannot clear it and would conflict with it.
> 3. AC6/M1: whether "gated closed" satisfies "naming decision recorded and applied before any public surface ships" is a maintainer judgment nobody has signed.
>
> ## P1 — must fix / must resolve
>
> - **[consistency] providers/grok_cli.py:419-421, minimax_code.py:360-361, omp.py:176-177 — launch-time MCP delivery seam does not cover three providers.** Each re-reads the agent profile at launch and regenerates native MCP config from `profile.mcpServers` without calling `with_plugin_mcp`, so installed plugins' MCP servers are silently dropped — the exact silent-failure class the PR says review 1 eliminated ("the merge now happens on the read seam that every launch passes through"). Only the six enumerated providers (antigravity, claude_code, codex, copilot, cursor, kimi) are wired. Mitigated today by the default-off gate, but the delivery seam itself is ungated.
> - **[conversation] Binding human block.** haofeif (@36ccabd) and fanhongy (@74750967) both hold CHANGES_REQUESTED; fixes landed after those reviews and GitHub does not auto-dismiss. All 13 of their findings were verified as substantively addressed at head 282839c1 (fanhongy 3×P1 + 3×P2; haofeif 7×P2 — each fix site confirmed in the worktree), but neither has re-reviewed. Merge requires their re-review/dismissal plus an explicit M1 sign-off (or accepted gated-closed interpretation of AC6).
>
> ## P2 — should fix
>
> - **[security] utils/tool_mapping.py:158-165 (+ install_service.py:534, terminal_service.py:470/500, launch.py:204) — cross-role uniform auto-grant.** Plugin MCP servers merge into EVERY managed agent's profile and `resolve_allowed_tools` appends `@<server>` to any non-`"*"` profile, silently widening deliberately-restricted roles (reviewer/supervisor) to include arbitrary plugin code. Needs per-profile opt-out or operator surfacing before M1 opens the surface.
> - **[conventions] README.md:149 — false claim "the HTTP API is available."** All four /plugins* routes 404 by default behind the same gate; README contradicts code and commit message.
> - **[conventions] CODEBASE.md — package map omits the new `agent_plugins/` package** (13 modules), violating the repo's own documentation-maintenance rule.
> - **[consistency] test/agent_plugins/test_naming_migration.py:~104-110 — AC6 drift:** PR body says "exactly two permanent exemptions" but `_VOCABULARY_BACKLOG_DOCS` has three (adds minimax-code.md). Guard is correct; narrative isn't.
> - **[consistency] agent_plugins/provenance.py:27,41 — dead production code** with a docstring naming consumers (`cao plugin list`, web panel, `cao skills list`) that don't use it. Remove or wire up.
> - **[vision] Naming collision + gated-closed surface** (advisory): "event plugins" vs "agent plugins" is a permanent comprehension tax, and ~27k gated-closed lines are a dormant maintenance cost if M1 stalls. Honestly disclosed; schedule risk, not architectural.
>
> ## P3 — nits / notes
>
> - [correctness] mcp_mapping.py `_map_stdio` reserved-env branch unreachable (schema rejects whole file first); per-entry-isolation claim inaccurate. Gate truthy spellings omit "on" despite claiming parity with CAO_AGUI_ENABLED. projection.py `_materialize` ownership check asymmetric vs sweep on out-of-band edits. install_service.py OpenCode shared-file profile-name-clash sub-case remains open (pre-existing class).
> - [security] resolver.py `_resolve_git` lacks the host allowlist/SSRF hardening its HTTP sibling has; non-`./` plugin MCP commands spawn verbatim (inherent MCP trust model); credential-shaped env values written cleartext with only a warning; GET /plugins is the broadest read-floor disclosure (double-gated, pinned by test).
> - [tests] Web gate enforcement in App.tsx untested (only the constant's default is asserted); "22 cases" conflates 16 corpus rows with 22 collected items; runtime pass-count claims unverifiable locally (numpy build blocked on old GCC — confirm via CI).
> - [conventions] README.zh-CN.md drift (no agent-plugins entry); singular `agent-plugin/` dir name; uv.lock 51-line pure-churn diff worth reverting.
> - [consistency] "its diff is empty" is false for docs/plugins.md itself (18-line retitle/banner); PR body's `==2.4.1` pin is stale vs committed `==2.5.0`.
> - [conversation] Self-disclosed: final push used `--no-verify` (mis-scoped hook); earlier "61 pre-existing failures" claim corrected by author.
>
> ## Verified sound (spot-checked, no findings)
>
> Single shared gate predicate on CLI group + all four routes (404 before body/auth, default-off confirmed empirically); realpath containment total across every boundary; deterministic lexicographic collision rule; single-pass values-only placeholder expansion with `x-cao-pre-expanded` stripped before provider writes; flock-based transactional store with backup-preserving error paths; OpenCode real-boolean disable + store-resolved ownership; schema PIN sha256s match vendored bytes with socket-blocked offline validation; Claude overlay generated and drift-guarded; conformance corpus exact-match and non-tautological; event-plugin code untouched; CI gates wired (check-agent-plugins-schemas, check-agent-plugin, dogfood recording job); inclusive language clean; Conventional Commit valid.
>
> ## Vision
>
> **strong-fit.** Publishing CAO as installable Agent Plugins inverts integration economics from O(N) client guides to O(1) publish-once, on a standard co-governed by the providers CAO orchestrates; the author-side win is live now and decoupled from the M1 gate.
>
> ## Recommended path to merge
>
> 1. Wire `with_plugin_mcp` into grok_cli, minimax_code, omp launch paths (+ tests).
> 2. Fix README.md gate description, CODEBASE.md package map, "exactly two" exemption claim; remove or wire provenance.py.
> 3. Decide the cross-role auto-grant posture before M1 opens surfaces.
> 4. Request re-review from haofeif and fanhongy; get explicit M1/AC6 sign-off.

---

## Addendum (Rev 2, 2026-09-06) — decisions and corrections from implementation verification

The Kiro implementation session (spec `pr584-review-remediation`) independently re-verified every
work item against `feat/agent-plugins-573-upstream` @ `282839c1`. Six corrections to this doc were
confirmed by re-checking the code; seven decisions follow. These supersede the sections they touch.

### Corrections (all re-verified against the worktree)

- **C1 supersedes §3.2's "verify":** verified — reserved env keys are rejected by the vendored
  schema (`env.propertyNames.not.enum`) and `map_mcp_config` early-returns on `_schema_errors`
  (`mcp_mapping.py:280`), so `_map_stdio`'s reserved-env branch is dead and the per-entry-isolation
  claim is false. Resolution is decision D2 below.
- **C2 supersedes §2.1's caller list:** only `install_service.py:526→535` feeds
  `resolve_allowed_tools` a plugin-merged map — and it persists the widened allowlist.
  `terminal_service.py:471/:501`, `cli/commands/launch.py:206`, and a fourth caller this doc
  missed, `mcp_server/server.py:154`, all read raw (un-merged) profiles. R7 is therefore a
  one-site plumbing change plus a guard test pinning the raw-profile asymmetry at the other
  three callers.
- **C3 supersedes §2.4's grep instruction:** "exactly two permanent exemptions" appears nowhere
  in the repo (10 unrelated hits); the stale claim lives only in the PR body. §2.4 collapses to
  the §4 human-edit item; the spec records the negative search result.
- **C4 adds a §1.1 ordering constraint:** `grok_cli._render_mcp_config` (`grok_cli.py:281`)
  raises `ProviderError` on any URL transport outside `{"http","sse"}`. Wiring grok's seam before
  its `PROVIDER_TRANSPORTS` entry + a canonical→native translation (`streamable-http` → grok
  `"http"`) would convert today's silent drop into a launch abort. Transport entries and the
  translation land **before** the provider wiring. Minimax already maps internally; omp passes
  through.
- **C5 answers §3.4's "find the sibling":** the SSRF hardening to mirror is
  `install_service.py:139-215` — https-only, `_DEFAULT_ALLOWED_HOSTS` {github.com,
  raw.githubusercontent.com} with `CAO_PROFILE_ALLOWED_HOSTS` override, userinfo/query/fragment
  rejection, `allow_redirects=False` + explicit `is_redirect` check, safe-path regex.
- **C6 strengthens §3.7:** `pyproject.toml` is byte-identical `fb4cc817`→`282839c1`, so the
  `uv.lock` diff must be **empty** — take `main`'s lock verbatim and verify with
  `uv lock --check`; add that check as the drift guard.

### Decisions

- **D1 (supersedes §2.5 — provenance.py): RETAIN and wire, do not remove.** The original
  "remove is smaller/safer" call was based on a grep that excluded `test/`: `owning_plugin` is
  the collision-rule oracle at 14 assertion sites (`test_projection.py`, `test_installer_property.py`)
  and the module is the documented prompt-injection mitigation (operators must be able to see
  which plugin contributed a skill whose content enters system prompts). Wire the three consumers
  the docstring names — `cao plugin list`, the `cao skills list` annotation, the `/plugins`
  payload/web panel — with ~3 tests. All three surfaces sit behind the existing default-off gate,
  so this does not widen the shipped surface. Satisfies the reviewer's "remove or wire up" on the
  "wire up" branch. CODEBASE.md gains a `provenance` row (§2.3).
- **D2 (resolves §3.2 — reserved-env branch): Option B — delete the dead branch, fix the claim.**
  Whole-document rejection is the vendored-schema contract; restoring per-entry isolation would
  change validation semantics for every whole-doc rejection and risk conformance-corpus drift —
  a spec-behavior change that doesn't belong in this PR. Keep the two-entry fixture as a
  regression test pinning whole-document rejection (`valid=False, servers=[]`), correct the
  per-entry-isolation docstring/claims, and retract the corresponding correctness property.
- **D3 (confirms §2.1 posture): default `OMIT` — no auto-grant of plugin-delivered MCP servers;
  explicit `pluginMcp` opt-in; fail-closed classification** (undeterminable provenance ⇒ treated
  as plugin-delivered). The install path persists the widened allowlist into native agent files,
  so a wrong default is durable, and restricted roles exist precisely to not gain tools
  implicitly. Surface the omission (log + plugin-list output) so operators see why a server
  wasn't granted. Reversal to grant-plus-warning stays a one-constant change. Still list the
  posture for maintainer sign-off in §4 — implemented default ≠ settled policy.
- **D4 (confirms §3.5 — credential-shaped env values): warn-only, no code change.** Refusal
  false-positives on long base64 config values; redaction breaks authentication silently. Document
  the trust model in `docs/agent-plugins.md` — cleartext write, warning as the only control,
  env-var indirection (`${VAR}` / `cao env`) as the supported path — with the decision named and
  dated.
- **D5 (confirms §3.1): add `"on"` by reusing the canonical `BOOL_TRUE_VALUES` set.**
- **D6 (resolves §3.8 — `agent-plugin/` rename): skip and record as accepted naming.** Measured
  cost (60 occurrences, 11 files, 23 moves, Makefile + CI targets) is churn mid-review for a P3
  nit; note the acceptance in the PR body.
- **D7 (records the unasked question): the delivery seam does NOT consult the ship gate, by
  design.** The gate is a management-surface release gate, not a data-path switch; gate-off ⇒ no
  install path ⇒ empty store ⇒ no delivery holds derivatively. Gating the seam would change six
  wired providers and existing tests for no security gain.

### Rebase / signature constraint (blocking, human-owned if no key)

`282839c1` carries an SSH `gpgsig`; a plain rebase onto `main` drops it. **Never push an unsigned
rewrite of the signed commit.** Preferred: if the SSH signing key is available to the executing
session, `rebase -S` (`gpg.format=ssh`) with a raw-object `grep -q '^gpgsig'` post-condition
(`%G?` is unreliable without an allowed-signers file). If the key is NOT available, do not rebase
at all: the branch is MERGEABLE against `main` (zero conflicts on the probe), so land the work as
ordered commits **on top of the existing signed head** and fix `uv.lock` to match `main` in a
normal commit (C6's `uv lock --check` still applies) — signing of the new commits then happens at
the author's push. Either way, `282839c1`'s content stays intact as commit 1 and work items land
as focused commits 2..n, preserving §0's one-commit-per-item rule and reviewers' line anchors.
