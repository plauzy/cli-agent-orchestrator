# Agent Plugins 1.0.0 adoption — implementation audit

**Date:** 2026-08-09
**Auditor:** Claude Code (autonomous session), commissioned by @plauzy
**Subject:** the two competing implementations of the `cao-agent-plugins` Kiro spec, both targeting
[awslabs/cli-agent-orchestrator#573](https://github.com/awslabs/cli-agent-orchestrator/issues/573)
("Agent Plugins 1.0 support — package the CAO ecosystem as portable plugins + a plugin install/marketplace surface"):

| | [PR #36](https://github.com/plauzy/cli-agent-orchestrator/pull/36) | [`impl/cao-agent-plugins`](https://github.com/plauzy/cli-agent-orchestrator/tree/impl/cao-agent-plugins) |
|---|---|---|
| Head | `2d69333` (1 squashed commit) | `38897f5` (10 commits, one per W-unit) |
| Base | `spec/cao-agent-plugins` @ `9241c61`, targets `main` | same spec base, **no PR opened** |
| Size vs spec base | 136 files, +15,099 / −65 | 74 files, +16,203 / −24 |
| Scope | W1–W11 (Increments 1 **and** 2) | W1–W10 (Increment 1 only, mechanically fenced) |
| CI | 17 green, 1 pre-existing failure (verified pre-existing) | **never run before this audit** |

Both branches were produced by agent sessions (author identity `Kiro Agent`, co-authored `plauzy`) from the same spec documents:
`.kiro/specs/cao-agent-plugins/{requirements,design,tasks}.md` on the
[`spec/cao-agent-plugins`](https://github.com/plauzy/cli-agent-orchestrator/tree/spec/cao-agent-plugins) branch
(23 requirements, maintainer decisions M1–M4, correctness properties P1–P11, buildable units W1–W11).

---

## 1. Verdict

**Land PR #36 as the vehicle. Do not open a PR for `impl/cao-agent-plugins`.** PR #36 is the more complete, more conformance-honest artifact, and it is the only one that has ever passed CI. But it is **not merge-ready as it stands**: two findings below (R1, R2) should block, and a handful of small test/comment defects should ride along in the same fix pass. After landing, port the `impl` branch's genuinely superior assets (its property-test tier, docs-guard suite, and resolver/store hardening deltas) as follow-up work — then retire the branch.

The one-line version of each branch:

- **PR #36** shipped both increments with a conformance corpus and a green pipeline, but its Increment-2 consumer half is unreachable code and its docs say otherwise.
- **`impl`** is a disciplined, gate-respecting Increment-1 delivery with the deepest test tier — whose two highest-value conformance suites silently skip everywhere but the author's sandbox, and whose web surface **does not parse**.

The second point deserves emphasis because it is the audit's cleanest lesson: `impl`'s `web/src/api.ts` has contained a syntax error (`},,`) since its W8 commit, breaking every web test and any web build — and nobody knew, because a branch with no PR gets no CI in this repo (`ci.yml` fires only on `base: main`). The first time anyone executed `impl`'s web suite was this audit.

---

## 2. Method

Static review of both full trees (branch-qualified `git show`/`git grep`/`git diff`, no checkout of either implementation into the working tree), grounded against three sources:

1. **The Agent Plugins 1.0.0 spec itself** — `agentplugins/agent-plugins-spec` @ `bd38355` (640-line `spec/1.0.0.md`, status *Published*) and the schemas served by agent-plugins.org.
2. **The Kiro spec** on `spec/cao-agent-plugins` (the requirements both branches claim to implement).
3. **The upstream canonical example** (`agent-plugins-example`).

Plus **dynamic verification** in isolated worktrees — notably the first-ever execution of the `impl` branch's test suites. Full log in [§9](#9-dynamic-verification-log).

Line references use the notation `branch @ path:line`. `PR36` = `claude/cao-agent-plugins-impl-1id3pg` @ `2d69333`; `impl` = `impl/cao-agent-plugins` @ `38897f5`.

---

## 3. Provenance and timeline

| When (UTC) | Event |
|---|---|
| Aug 7 | #573 filed upstream. Spec branch built: requirements → design → tasks (`9241c61`) |
| Aug 8, 20:35 → Aug 9, 01:16 | `impl` branch: 10 commits, W1→W10, stopping on the Increment-1 boundary |
| Aug 8, 22:35 | PR #36 opened (then 16 commits; that history preserved at `backup/pr36-original-history` @ `9cf1f90`) |
| Aug 8–9 | PR #36 CI iteration: corpus fixture not git-representable (fixed), `tomllib` on 3.10 (fixed) |
| Aug 9, 08:04 | PR #36 force-pushed as a single squashed commit `2d69333` with five changes, including the M1 gates (previously **not** enforced) and the two-glob Kiro fix |

**The two implementations are independent code.** Every core module differs in blob SHA *and* internal API (e.g. `impl` has a separate `schema_registry.py` and a persisted projection ledger; PR36 folds schema access into `validation.py` and derives prior projection state from install records). The only identical blobs are ones any correct generator must produce: the vendored schemas and the byte-copied packaged `SKILL.md` files. `git merge-base` of the two heads is the spec base — neither descends from the other.

**But PR #36's final form was written with `impl`'s results in hand.** The spec-amendment prose (Requirement 13, see [§5.4](#54-the-requirement-13-amendment)) appears in PR36's tree in near-verbatim form — 3 changed lines out of a multi-paragraph amendment — despite being absent from the shared ancestor, and PR36's commit message re-narrates `impl`'s W6 findings and design arguments point for point. `impl` finished 01:16; the squash is 08:04. This is worth stating plainly in any upstream conversation: the two branches are not a blind A/B experiment; PR #36 is best understood as **the second pass**, incorporating the first pass's spec findings while re-implementing the code.

---

## 4. Conformance against Agent Plugins 1.0.0

### 4.1 Schema pinning — verified byte-identical, three ways

Both branches vendor the two canonical schemas with identical bytes, verified by sha256 across **four** locations:

| Source | `plugin.schema.json` | `mcp.schema.json` |
|---|---|---|
| Spec repo @ `bd38355` (`schemas/1.0.0/`) | `0a4aad95ce33…3ab883` | `6539175bfcdf…16acb` |
| agent-plugins.org (`public/schemas/1.0.0/`, site repo) | identical | identical |
| PR36 vendored (`src/cli_agent_orchestrator/schemas/agent_plugins/1.0.0/`) | identical | identical |
| impl vendored (same path) | identical | identical |

Both `PIN.json` hash sets are internally consistent and both `make check-agent-plugins-schemas` gates pass ([§9](#9-dynamic-verification-log)). One nuance: **the two branches pin different provenance for the same bytes.** `impl` records the spec repo's HEAD (`bd38355…`, status *Published*); PR36 records the commit agent-plugins.org itself pins (`b78a4f16…`, one commit earlier, status *Working Draft*). The only difference between those commits in `spec/1.0.0.md` is the status line; `schemas/` is unchanged. PR36's choice matches what the `$schema` URL actually serves today; `impl`'s matches the source of truth. Either is defensible — the eventual merged `PIN.json` should say *which* policy it follows so the next refresh doesn't flip-flop.

### 4.2 Clause-by-clause

| Spec clause | PR36 | impl |
|---|---|---|
| §4.1 realpath containment + narrowest-failure-boundary ladder | ✅ `containment.py::resolve_within_root` (realpath-then-guard, `+ os.sep` prefix fix); ladder rungs verified at each call site | ✅ same doctrine, different API (`realpath`/`is_within`/`resolve_within_root`/`resolve_relative_within_root`); ladder documented as a table |
| §5.2 closed manifest, exactly two non-fatal tolerances | ✅ unknown top-level field → WARNING; non-object `extensions` → WARNING; all else FATAL | ✅ equivalent |
| §5.2 "MUST NOT retrieve a schema while loading" | ✅ `referencing` registry refuses all retrieval; proven under process-wide socket blocking | ✅ same technique (`schema_registry.py`), same socket-blocked proof |
| §7.1 immediate-children-only skill discovery, sibling isolation | ✅ | ✅ |
| §8.1 unimplemented-namespace `extensions` ignored **without validating contents** | ✅ member is popped *before* the schema sees it — the subtle reading, done right | ✅ equivalent (`_take_extensions`) |
| §7.2.1 mcp.json contract (single-token command, transports, header rules) | ✅ full mapping layer (`mcp_mapping.py`, 604 lines, 45 tests) | ➖ out of scope by design (Increment 1); `mcp.json` presence detected and reported unsupported |
| §9.2 single-pass, non-recursive `${PLUGIN_ROOT}`/`${PLUGIN_DATA}` expansion in `args`/`env` values/`cwd` only | ✅ implemented + property-tested (incl. the seeded-literal single-pass proof) — **but see R1: the output is never consumed** | ➖ out of scope; mechanically fenced (AST test asserts `mcp_mapping.py` does not exist) |
| §9.1 PLUGIN_DATA managed dir (create-before-launch, survive updates) | ✅ store creates `agent-plugin-data/<name>` as a **sibling** of the plugins dir so update-by-rename can't destroy it; retained on remove unless `--purge-data` | ✅ identical layout decision |
| §11.2 skills-only client conformance | n/a (full client) | ✅ this is precisely the boundary `impl` ships |

**A point the spec is silent on:** skill-name collisions. The spec delegates skill semantics to agentskills.io and defines no cross-plugin precedence. Both branches implement the same CAO-policy rule — pre-existing skills always win; among plugins, the **lexicographically smallest manifest `name`** wins; `installed_at` is explicitly rejected (order-independence); a rebuild that changes winners emits `projection.winner_changed`. Both correctly document this as CAO policy rather than spec conformance. This is exactly the kind of client-policy write-up worth contributing back to the spec's FUTURE_CONSIDERATIONS.

### 4.3 The delivery seam (the hard problem both had to solve)

Both branches independently chose **projection**: plugin skills are materialized into `SKILLS_DIR` as managed symlinks (copy fallback per Requirement 13.4), rather than registering plugin roots as extra search directories. The reasoning is the same on both sides and it is correct: Kiro CLI receives a literal `skill://{SKILLS_DIR}/…` glob and OpenCode reads through a single symlink to `SKILLS_DIR`, so anything stored elsewhere is invisible to exactly those two providers — including CAO's own default provider. Convergent choice by independent implementations is decent evidence the design doc's argument holds.

Where they diverge is what they did about the **glob-semantics hazard** their own testing surfaced — see PR36's fix vs `impl`'s open risk in [§6](#6-findings--pr-36)/[§7](#7-findings--implcao-agent-plugins).

---

## 5. Conformance against the Kiro spec

### 5.1 Unit coverage

| Unit | PR36 | impl |
|---|---|---|
| W1 store primitives · W2 pinned schemas · W3 validator+containment · W4 resolver · W5 installer/projection/provenance | ✅ | ✅ |
| W6 cross-provider delivery verification | ✅ + vendored canonical example | ⚠️ suites exist but the canonical-example halves skip (see [§7](#7-findings--implcao-agent-plugins) F1) |
| W7 CLI · W8 API/web · (M1-gated) | ✅ gated | ✅ gated (web **broken**, F0) |
| W9 CAO-as-plugin packages | ✅ (+README/CHANGELOG per package) | ✅ (LICENSE only) |
| W10 docs + naming migration | ✅ | ✅ |
| W11 MCP mapping (Increment 2) | ⚠️ built, tested, **not wired** (R1) | ➖ deliberately absent, AST-fenced |

### 5.2 The M1 ship-gate (Requirement 16.5) — closed on both, with tests

| Surface | PR36 | impl |
|---|---|---|
| CLI | `@click.group("plugin", hidden=True)`; test asserts absence from `cao --help` | same (`agent_plugin.py:69`), test equivalent |
| TUI | 4 × `Policy::Hidden`; distribution guard updated to 24/18/31 = 73 | same (`catalog.rs:869/889/903/921`) |
| Web | `PLUGINS_TAB_ENABLED = false` in `featureFlags.ts`; tab filtered **and** render gated | same (`featureFlags.ts:24`) |

History note: PR #36's gates were added **in the Aug-9 squash** — its own comment records that the pre-squash head advertised the CLI group, used `Policy::Handoff` (which *is* offered in navigation), and had no web flag. `impl` had all three gates from its W7/W8 commits. Both now share one soft leak: `README.md` publicly links the agent-plugins doc for a surface that is deliberately hidden (R5/F5).

### 5.3 The increment boundary

`tasks.md` is explicit: *"W11 must not begin before W5 is **merged**, or the Increment boundary erodes… not merely queued."* `impl` honors this to the letter — including an `test_increment_boundary.py` that AST-walks the package and fails if any live string references the Increment-2 placeholders, and a packaging script that hard-errors on an `mcp.json`. PR #36 ships both increments in one PR, in open contradiction of that sequencing note (its description says "both increments" without acknowledging the rule). Two honest readings: (a) a process deviation that should be called out to maintainers rather than discovered by them; (b) evidence the rule itself was overweighted once a single session could build both increments coherently. Either way — **the PR description should name the deviation**, as it carefully does for its other deviations. Note the internal tension in the spec itself: tasks.md's own dependency-graph JSON schedules W11's first sub-tasks alongside W7/W8, contradicting its prose. The spec docs should reconcile that on the next amendment.

### 5.4 The Requirement-13 amendment

`impl` discovered during W6 that criterion 13.2 was never satisfiable: `skills.extra_dirs` entries live outside `SKILLS_DIR`, so Kiro and OpenCode can't see them **with zero plugins installed** — a pre-existing gap, not a regression. `impl` amended the spec (commit `5efa70c`): 13.2 narrowed, new provider-dependent criteria 13.6/13.7, criteria 3–5 keep their numbers so existing cross-references stay valid, and a three-paragraph amendment note records the evidence. PR #36 carries the amendment **near-verbatim** (3 changed lines: the two-glob rewording, one added rationale clause, the regression-guard pointer retargeted to its own test). Credit where due: the amendment is `impl`'s work product; PR #36 refined it. Both document the limitation in `docs/skills.md`.

### 5.5 Properties P1–P11

Both branches cover P1–P8, P10, P11; P9 (expansion soundness) exists only on PR36 (Increment 2). Structural difference: `impl` isolates 45 Hypothesis `@given` properties into four dedicated `*_property.py` modules (validation 19, installer 20, delivery 6) — the cleanest property-tier in the repo; PR36 mixes Hypothesis into its example-based modules. PR36 adds something `impl` lacks entirely: the **conformance corpus** (16 cases in `fixtures/corpus/cases.json`, each pinning `loadable`, exact finding codes, and the spec clause each cites — exact-set matched by default). For a conformance feature, expectations-as-reviewable-data is the artifact maintainers will actually want to diff; it is PR36's single strongest asset.

---

## 6. Findings — PR #36

Ranked. R1/R2 should block merge; the rest ride along.

### R1 (blocking) — Plugin MCP servers are mapped and then discarded; the docs say otherwise

`mcp_mapping.load_and_map` has exactly one caller: `validation._map_mcp` (`PR36 @ src/cli_agent_orchestrator/agent_plugins/validation.py:673-677`). The result lands in `PluginValidationReport.mcp_servers`, which is read nowhere outside `to_dict()` (`models.py:213`). `PluginRecord` has no MCP field. Nothing inserts a mapped entry into any agent profile's `mcpServers` — which makes the receiving seam in `install_service.py` (the `is_plugin_mcp_entry`/`strip_plugin_mcp_marker` branch, guarded by `PRE_EXPANDED_KEY = "x-cao-pre-expanded"`, `mcp_mapping.py:62`) **unreachable in production**, and the test that covers it (`test_mcp_mapping.py::test_install_service_skips_a_marked_entry`) a test of a hypothetical: it hand-builds a marked entry and re-implements the comprehension rather than driving `install_agent`.

Install a third-party plugin with an `mcp.json` today: its servers are validated, expanded, containment-checked, credential-scanned, reported — and never launched. Meanwhile `docs/agent-plugins.md:172-175` tells operators CAO "maps each server into its internal MCP configuration, **from which every provider's native form is already derived**." A reader concludes plugin MCP servers run. They do not.

The design doc's own architecture (mapping targets "the agent-profile `mcpServers` dict") and the very existence of the pre-expanded marker (whose only purpose is to survive CAO's profile interpolation pass) both presuppose profile injection. **Fix either direction before merge:** wire `report.mcp_servers` into installed-plugin state and the profile-build path (and make the marker test drive the real seam), or strip the claim from the docs and mark the mapping layer as validation/reporting-only pending a follow-up. The former is the spec's intent; the latter is honest scoping. Shipping the current combination — dead seam plus overclaiming doc — is the one indefensible option.

### R2 (blocking) — `GET /plugins` has no scope gate and is quadratic on live state

`PR36 @ src/cli_agent_orchestrator/api/main.py:2040` — no `require_any_scope` dependency, while `POST /plugins`, `POST /plugins/validate`, and `DELETE /plugins/{name}` all carry WRITE|ADMIN. The response discloses, per plugin, the original source path/URL and `affected_sessions`: live terminal IDs, session names, profile names, skill names. The repo's own precedent gates comparable reads (`GET /settings/agent-dirs` is read-scope gated *because* it discloses local paths). The existing `test_scope_coverage` guard only enumerates mutating methods, so nothing catches this. Additionally `affected_sessions` is recomputed **per record** — `list_sessions()` × `list_terminals_by_session()` × `load_agent_profile()` per plugin — a quadratic walk on an unauthenticated endpoint the panel would poll. Add the read floor (`SCOPE_READ|WRITE|ADMIN`) and hoist the session enumeration out of the loop. (`impl` shares the missing gate, F3 — landing the fix on PR36 resolves it for the merged tree.)

### R3 — One test is a source-grep of the module it should exercise

`test_delivery_providers.py::test_the_installed_kiro_profile_carries_both_globs` reads `install_service.py`'s **source text** and asserts two f-string literals appear in it, ignoring the `skills_root` fixture it sets up. The behaviour *is* genuinely covered — by pre-existing `test/services/test_install_service.py:698-711`, which asserts the emitted Kiro `resources` array — so this is a mislabeled tautology rather than a coverage hole. Rename it or make it assert the produced agent JSON.

### R4 — The vocabulary guard short-circuits half its own parametrization

`test_naming_migration.py::test_bare_plugin_is_qualified_outside_a_scoped_title` parametrizes over 4 docs but early-returns for any title containing "Plugin" — which exempts `agent-plugins.md` and `plugins.md`, the two documents most likely to slip. Only `skills.md` and `control-planes.md` are actually checked. The commit message sells this guard as enforcement; make the exemption explicit (separate the scoped-title fixture set) or check qualified usage inside scoped docs too.

### R5 — Stale comments that contradict adjacent code, in a PR whose comments are the review trail

- `validation.py:16-23` module docstring still declares the Increment-1 boundary ("does not read the file, validate it against mcp.schema.json, expand any placeholder") while `_map_mcp` in the same file does all three.
- `tui/src/server.rs:565-570` block header says the plugin group is HANDOFF; `catalog.rs` says `Hidden` ×4 (and its comment correctly frames HANDOFF as the *post-M1* state).
- `catalog.rs` retains "= 61" and two "69" numerals from earlier distribution counts next to the now-73 constant.
- `README.md` publicly links `docs/agent-plugins.md`, and that doc's "Plugins tab" sentence (`:95`) is unqualified while the tab ships flag-off — both in tension with 16.5's "shall not ship this surface"; the doc's CLI section handles the same tension correctly with a provisional-verb note. Qualify the tab sentence; consider whether the README bullet should land at all before M1.

### Verified sound (a non-exhaustive list of things checked and found right)

Atomic stage-then-rename publish with rollback; independent dirname guard at the store boundary; total validator (`try/except Exception` → FATAL `internal.error`); `loadable` as a frozen-dataclass `@property` (cannot disagree with findings, P1 by construction); resolver `copytree(symlinks=True)` with the correct smuggling rationale; git invocation hardening (list argv, `--`, `--depth 1`, `--no-recurse-submodules`, prompts disabled, 300 s timeout); `--subdir` containment; collision rule exactly as specified with order-permutation tests; `winner_changed` transitions snapshotted before mutation on both install and uninstall paths; removal warns-never-refuses with the panel as a second independent enforcement point; `ops_mcp_server` timeout `(5, 300)` preserving the documented error contract; corpus guarded by `test_every_corpus_directory_is_tracked_by_git` (the fix for its own first CI failure, reproduced before fixed); `SKILL_RENAMES == {}` with the M4 retirement machinery tested through a synthetic rename; Trivy failure verified pre-existing (`docusaurus/package-lock.json` byte-identical to `main`); squash fidelity verified (21 files, +348/−99 vs `backup/pr36-original-history`, exactly as described).

---

## 7. Findings — `impl/cao-agent-plugins`

### F0 (fatal for the branch as it stands) — the web surface does not parse

`impl @ web/src/api.ts:371` contains `},,` — a doubled comma inside an object literal, a syntax error introduced by its own W8 commit (`3f638c7`; the branch diff shows `-  },` / `+  },,`). Every one of the 7 web test files fails at transform (`vite:oxc: PARSE_ERROR`), zero tests execute, and any `tsc`/`vite build` fails the same way. First detected by this audit — the branch never ran CI because it has no PR and `ci.yml` triggers only on `base: main`. One character to fix; a complete answer to "why does this repo insist on CI on every PR."

### F1 (blocking if the branch were to land) — the two highest-value conformance suites silently skip everywhere

`test_validation.py:27` and `test_delivery_providers.py:674` hardcode `CANONICAL_EXAMPLE = Path("/projects/sandbox/agent-plugins-example")` — the authoring agent's sandbox path — with `skipif` guards. Result: the 8 tests that implement Requirement 23.4/23.5 (upstream canonical example is a known-good fixture; installing it delivers its skill to a provider) **skip on every machine but the author's**, including CI. Dynamically confirmed: they are exactly the 8 skips in the branch's first suite run; with the fixture symlinked into place, **all 8 pass** — the conformance logic is right, the fixture plumbing is wrong. PR36's approach (vendor the example into `test/agent_plugins/fixtures/canonical-example/`, exercised unconditionally by 6 modules) is the correct fix and is already written.

### F2 (blocking if landed) — the Kiro glob hazard: diagnosed, proven, documented… and not fixed

`impl`'s `TestKiroGlobSymlinkSemantics` states it plainly ("a real, recorded risk, not a curiosity"), proves that `pathlib.Path.glob("**/SKILL.md")` does **not** traverse a symlinked skill directory while `glob.glob(recursive=True)` does, proves the `*/SKILL.md` mitigation finds it under both — and then leaves `install_service.py` untouched, still emitting only the `**` glob. If Kiro's internal expansion has pathlib semantics, **every plugin skill is invisible to Kiro alone** — a direct Requirement-13.2 violation the branch's own equivalence suite cannot catch, because `test_delivery_property.py:131` expands the glob with the *favorable* (`glob.glob`) semantics. PR #36 ships the fix (a second `skill://{SKILLS_DIR}/*/SKILL.md` resource, recorded as a design deviation, with a pathlib tripwire test).

### F3 — `GET /plugins` ungated (shared with PR36; see R2)

`impl @ api/main.py:2058`. Same gap, same fix. `impl`'s API does have two postures PR36 should copy in spirit: its `validate` (CLI and API both) takes a **local path only** — no source resolution, no clone — which avoids the network-and-disk-on-validate problem PR36 instead had to solve by scope-gating; and every install/validate response embeds the untrusted-content warning so a client cannot render an install affordance without having been handed it.

### F4 — READ-floor `POST /plugins/validate` permits filesystem probing

A `cao:read` caller can point `body.path` at arbitrary locations and infer existence/shape from findings. Total/read-only so no write risk, and localhost-only by default — but worth a containment check or a WRITE floor if the endpoint survives reconciliation.

### F5 — README soft leak (identical to PR36's R5 item; a wash)

### Where `impl` is genuinely stronger

1. **Test depth in Increment-1 scope:** 653 collected tests pass across its suites vs PR36's 434 (which include 73 Increment-2 tests). 45 Hypothesis properties in dedicated modules.
2. **The docs-guard suite** (`test_agent_plugins_docs.py`, 22 tests): asserts the untrusted-content warning appears within the first screenful, "no signing/no provenance" is stated, the documented `127.0.0.1:9889` matches `constants.SERVER_HOST/PORT`, packaged skill lists match build config. PR36 dropped this tier entirely; it should come back in the port.
3. **Resolver hardening deltas:** `-c credential.helper=` + empty `GIT_ASKPASS`/`SSH_ASKPASS`/`GCM_INTERACTIVE=never`, `--no-tags`, `-c submodule.recurse=false`, `.git` stripped post-clone, and a full-40-hex-only commit-pin fallback (`init` + `fetch --depth 1` + `checkout FETCH_HEAD`) that PR36's `--branch`-only resolver cannot express.
4. **Store `_replace()` restores the old tree if the second rename fails** — PR36 rolls back the aside-move but `impl`'s double-rename recovery is the more complete failure story.
5. **The increment fence** (`test_increment_boundary.py`) — moot once W11 lands, but the technique (AST-walk for forbidden literals) is worth keeping in the toolbox.
6. **`SchemaUnavailableError`** distinguishing "CAO's packaging is broken" from "the plugin is invalid" — a diagnostic distinction PR36's folded design loses.

---

## 8. Head-to-head

| Dimension | PR #36 | impl | Edge |
|---|---|---|---|
| Scope vs #573 | both increments; author+client halves | Increment 1 | PR36 |
| Spec-process discipline | ships Inc 2 against tasks.md sequencing | boundary honored and fenced | impl |
| Agent Plugins 1.0.0 conformance | full clause coverage; §8.1 subtlety right; R1 undermines §7.2/§9 *in practice* | clean within its declared §11.2 boundary | tie, different shapes |
| M1–M4 gates | closed + tested (since squash) | closed + tested (from the start) | tie (impl by history) |
| Conformance-as-data | 16-case corpus, exact codes + clauses | none | PR36, decisively |
| Canonical example | vendored, always runs | hardcoded path, always skips | PR36, decisively |
| Kiro symlink-glob hazard | fixed + tripwired | proven, unfixed | PR36 |
| Increment-1 test depth | ~282 fns (Python, Inc-1 scope) | 527 fns, 45 properties, 22 doc guards | impl |
| Web | 106 tests, CI-green | **does not parse** | PR36 |
| Rust TUI | 143 green (CI + local) | 143 green (this audit) | tie |
| CI status | 17 green / 1 verified-pre-existing | never ran until now | PR36 |
| Reviewability | 1 squashed commit + narrative + preserved history branch | 10 clean W-unit commits | impl (with PR36's backup mitigating) |
| API safety posture | cloning validate, scope-gated | local-only validate, warning-in-every-response | impl (posture), PR36 (enforcement) |

---

## 9. Dynamic verification log

All runs performed 2026-08-09 in isolated git worktrees, Python 3.11.15, `uv sync --all-extras --dev`, this container (root; no `cao-server` running).

| Run | Result |
|---|---|
| **impl** `pytest test/agent_plugins/ test/api/test_plugins_endpoints.py test/cli/commands/test_agent_plugin.py test/cli/commands/test_skill_retirement.py test/test_agent_plugins_docs.py -rs` | **653 passed, 8 skipped, 51 s** — first execution ever; all 8 skips are the F1 canonical-example tests ("canonical agent-plugins-example checkout not present") |
| **impl** same 8 tests with the canonical example symlinked to the hardcoded path | **8 passed** — logic correct, plumbing wrong |
| **impl** `make check-agent-plugins-schemas` / `make check-agent-plugin` | both OK (pin `bd38355…`; 2 packages in sync @ 2.4.1) |
| **impl** `npm ci && npm test` (web) | **7/7 test files fail — `PARSE_ERROR` at `src/api.ts:371` (`},,`)**; zero tests execute (F0) |
| **impl** `cargo test --bins` (TUI in-crate) | **143 passed, 0 failed** |
| both branches `tui/tests/endpoint_contract.rs` (3 failures here) | classified **environmental**: it is a deliberate live-server contract test that fails-not-skips without a running `cao-server`; the file is untouched by both branches; PR36's CI (server available) runs it green |
| **PR36** `pytest test/agent_plugins/` | **434 passed** — the PR body's claim verified exactly; 2 skips are root-privilege artifacts (chmod fixtures no-op as root) that run in CI |
| **PR36** `make check-agent-plugins-schemas` / `make check-agent-plugin` | both OK |
| **PR36** full-suite / web / Rust | not re-run locally — CI on `2d69333` verified directly via the checks API: 17 success, 1 skipped (Dependency Review), 1 failure (Security Scan, verified pre-existing: `docusaurus/package-lock.json` byte-identical to `main`). The fix has since landed on `main` as #576 (`5464a2e`, nanoid ≥3.3.17 via npm overrides) — syncing PR #36 with `main` clears its one red check |

## 10. PR #36 description — claims audit

| Claim | Verdict |
|---|---|
| "All eleven buildable units, both increments" | ⚠️ **Overstated for W11**: mapping built and tested, consumer seam dead (R1) |
| "Schemas vendored byte-identical + PIN + offline drift guard" | ✅ verified by hash against spec repo *and* live site |
| "M1 gate enforced on all three surfaces," each with a closed-state test | ✅ verified at file:line, tests present |
| "`loadable` is derived, not a field" | ✅ frozen-dataclass property |
| "Extensions dropped without being validated (§8.1)" | ✅ popped before schema validation |
| "Validation offline by construction," socket-blocked test | ✅ |
| "Removal warns, never refuses"; panel independently enforces | ✅ |
| Kiro two-glob rationale + tripwire | ✅ code, tests, docs all consistent (one mislabeled test, R3) |
| "Requirement 13 amended (maintainer-approved)" | ⚠️ amendment present and sound; provenance is `impl`'s commit `5efa70c`, adopted near-verbatim — "maintainer-approved" presumably refers to the repo owner co-driving both sessions, but upstream maintainers have approved nothing yet |
| "`ops_mcp_server` one-line change" | ✅ functionally one line (`_HTTP_TIMEOUT = (5, 300)` + use), +19/−1 with comment/tests |
| "`POST /plugins/validate` scope-gated" (unlike sibling validators) | ✅ and well-argued — but see R2 for the GET route |
| "SKILL_RENAMES empty; retirement step tested synthetically" | ✅ |
| "6725 passed / 434 / 106 / 143" | ✅ 434 reproduced exactly; 143 reproduced on both branches; 6725 and 106 accepted via green CI, not re-run |
| "62 remaining failures pre-existing, identical sets vs base" | ➖ not re-verified (author-environment claim); green CI makes it moot for merge purposes |
| "Squashed tree byte-identical to sum of parts + listed changes" | ✅ 21 files, +348/−99, exactly |
| Trivy failure pre-existing, wants its own PR | ✅ verified byte-identical lockfile; that PR happened — #576 landed on `main` after this audit's static pass |

## 11. Recommendation

**Sequence:**

1. **Fix-forward on PR #36 (blocking):** R1 (wire `report.mcp_servers` → install record → profile `mcpServers`, making the pre-expanded seam live and driving `test_install_service_skips_a_marked_entry` through the real path — or, if maintainers prefer the smaller diff, demote the docs claim and label mapping validation-only) and R2 (read-scope on `GET /plugins` + hoist the session walk). Ride-alongs: R3, R4, R5 comment/docs fixes. Add a sentence to the PR description naming the Increment-boundary deviation. Sync the branch with `main` while at it — the nanoid fix (#576) landed there, so the sync turns Security Scan green and makes the pipeline fully clean for the merge decision.
2. **Port from `impl` after merge (fast follows, in value order):** the docs-guard suite; the resolver hardening deltas (credential-helper neutralization, `--no-tags`, commit-pin fetch); the four dedicated property modules (adapted to PR36's module API); store `_replace()` restore-on-failure; `SchemaUnavailableError`. Consider `impl`'s local-only `validate` posture for the CLI/API as the default, keeping resolution behind the WRITE-gated install path.
3. **Retire `impl/cao-agent-plugins`** (after the port): fix or don't fix `},,` — but do not leave a branch alive whose web surface can't build; it will be mistaken for a viable alternative.
4. **Upstream (#573):** what CAO can now demonstrate is substantial — both sides of the contract, pinned schemas gated in CI, a conformance corpus keyed to spec clauses, the canonical example as an executable fixture, and a §11.2-clean increment story. What it cannot yet claim: AC2's end-to-end half (install `agent-plugin/cao` into ≥2 foreign clients and call the tools — needs R1 on the client side and a real foreign-client run on the author side), and every naming decision M1–M4, which are maintainers' to make and are correctly left open behind enforced gates. Lead with the corpus and the two-glob finding; the latter is exactly the class of cross-client subtlety the spec's conformance section exists to surface, and is worth filing upstream against the spec repo as an implementer's note.

**Process lesson worth keeping:** the highest-severity defect in each branch (R1's dead seam; F0's parse error + F1's skipping suites) is precisely the kind that static self-review keeps missing and execution finds instantly. The repo's rule that conformance gates run in CI on every PR is vindicated; the corollary — *a branch without a PR is a branch without verification* — is now demonstrated twice in one feature.

---

## 12. Addendum (2026-08-10): reconciliation outcome and client verification

Everything §11 recommended has since been executed, and the landing vehicle changed shape:

1. **PR #36 absorbed the full reconciliation** as reviewable commits — R1 (`4f2d523`, new `agent_plugins/mcp_delivery.py` wiring plugin MCP servers into profiles by **re-mapping from the installed root**, the stale-record-proof option), R2 (`05b74e2`, read floor + hoisted walk + today's ungated GETs pinned as data), ride-alongs (`a099309`), and all six `impl` ports (WP4.1–4.6). Two ports found real defects on arrival: the docs-guard cross-check exposed an undocumented package skill list, and the store-recovery "cosmetic" difference was a genuine data-loss path (backup swept by a `finally` clause), reproduced before fixing.
2. **[PR #38](https://github.com/plauzy/cli-agent-orchestrator/pull/38)** collapsed the reviewed work into a single **signed** commit on current `main` and added net-new work this audit verified separately: an OpenCode shared-config defect pair (uninstall left a removed plugin's server `enabled: true` pointing at a deleted `PLUGIN_ROOT`; install could silently overwrite a user's hand-written entry — now disable-in-place and refuse-and-report, with the disable semantics verified against the shipped OpenCode 1.18.15 bundle), a CI-gated dog-food recording (CAO installs its own package through its own pipeline; the GIF cannot be produced by a failing run), and the spec docs relocated to `docs/issues/573-agent-plugins/`. Suite re-run here: 597 passed + 3 root-only skips (the claimed 600 under non-root CI), drift guards green, 20 CI checks green.
3. **Claude Code verified as a working client** (2.1.226, live install in this audit's environment): skills discovered from the untouched Agent Plugins 1.0.0 package; identity and MCP required Claude Code's own files; the measured gap closed by a generated, drift-guarded **compatibility overlay** (`.claude-plugin/plugin.json` + byte-identical `.mcp.json`) pushed to PR #38 (`a5c10ec`) — after which strict `claude plugin validate` passes and the `cao-ops` server's 11 tools were exercised over MCP stdio against the published `cli-agent-orchestrator==2.4.1` pin: structured error naming operation + cause without `cao-server` (Requirement 20), `{"success":true,"sessions":[]}` with one running. AC2-grade tools-callable evidence, from a client outside the spec's listed set.
4. **The vocabulary backlog is cleared** (`71c9de2`): five docs qualified and promoted into the enforced guard; `cursor-cli.md` and `opencode-cli.md` remain as permanent justified exemptions (third-party plugin concepts).

Still open after all of this: maintainer decisions M1–M4 (gates remain closed and tested), and AC2's letter — the spec's *listed* clients. Next validation target: **Antigravity CLI**, using the same matrix (pure-package install → discovery → bridge deltas → `cao-ops` handshake) so evidence stays comparable across clients.

---

## Appendix — suggested review comment for PR #36

> Audited against the Agent Plugins 1.0.0 spec, the `.kiro` spec, and the sibling `impl/cao-agent-plugins` branch (full report: `docs/audits/agent-plugins-adoption-audit.md`). Core pipeline verified sound: containment, atomicity, collision determinism, offline validation, all three M1 gates + tests, schema bytes identical to upstream. Two blockers before this merges:
> 1. **Plugin `mcp.json` servers are mapped and then discarded** — `load_and_map`'s output is only ever serialized into the report; nothing writes it into install records or profile `mcpServers`, so the `x-cao-pre-expanded` branch in `install_service.py` is unreachable and `docs/agent-plugins.md:172-175` overclaims. Wire it or re-scope the doc.
> 2. **`GET /plugins` needs the read-scope floor** (it discloses live session/terminal/profile names and source paths) and should hoist the per-plugin `affected_sessions` session walk.
>
> Ride-alongs: `test_the_installed_kiro_profile_carries_both_globs` greps source instead of asserting the emitted profile; the vocabulary guard early-returns for scoped titles so `agent-plugins.md`/`plugins.md` are unchecked; stale comments (`validation.py:16-23` Inc-1 docstring, `server.rs` HANDOFF block, `catalog.rs` 61/69 numerals); the unqualified "Plugins tab" doc sentence. Also please name the Increment-boundary deviation (tasks.md says W11 waits for W5 to *merge*) in the description — the PR names its other deviations; this one it should too.
