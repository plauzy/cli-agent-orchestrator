# Research: agent-plugin lifecycle (creator skill, audit skill, dogfood package, blog post)

**Researcher:** kiro-researcher (kiro_cli, terminal `963e0c90`, session `cao-apl`)
**Date:** 2026-10-29, 16:00 to 16:15 -05:00 **Rebase re-check:** 2026-10-30 ~02:00 -05:00, tree at `upstream/main` `00611d119ce6e8c8a940929f4f59c58e34a8ea2e` (#1121 merged). Line numbers below are updated to `00611d11` where they moved; facts observed only at `556726a4` say so.
**Worktree:** `/Volumes/workplace/open-source/cao-agent-plugin-lifecycle`, branch `feat/agent-plugin-lifecycle`, HEAD `556726a456f659374b86a7f9db25d6bb50bbc4ae`, equal to `upstream/main` after `git fetch upstream` (exit 0, 2026-10-29).
**Status:** spec-phase input only. Nothing in this file was implemented, committed or pushed. This is the only file written by this seat.

## Scope and method

Every claim below cites a sha, a PR number, a `file:line`, or a command with its exit status. Paths are relative to the worktree unless absolute. `$S` means the CAO state directory's skills folder, `~/.aws/cli-agent-orchestrator/skills`.

Methods used:

- Reading files by path. Under `~/.aws/cli-agent-orchestrator/` I listed files with `find … -type f` and read them one by one. I never ran `grep -r` there.
- `git log` / `git show` / `git grep` in the worktree.
- `gh api` against `awslabs/cli-agent-orchestrator`, authenticated as `plauzy` (`gh auth status`, exit 0).
- Running the gates in [Available shift-left gates](#available-shift-left-gates-exact-commands--observed-exit-status). I bounded every long command with `perl -e 'alarm N; exec @ARGV' --`.
- Read-only `sqlite3` queries against `~/.aws/cli-agent-orchestrator/db/cli-agent-orchestrator.db` for the #1121 seat evidence.

What I did not do: read `.remember/` anywhere, read anything under `/Volumes/workplace/LauerLabsLLC`, run the full test suite, or read `src/cli_agent_orchestrator/plugins/` or `test/plugins/`. For the event-plugin system I read only the `cao-plugin` skill's self-description.

## Hard distinction: Agent Plugins vs CAO event plugins

CAO has two plugin systems that share nothing but the word "plugin". The spec authors must never use an unqualified "plugin".

| | **Agent Plugins** (this work) | **CAO event plugins** (unrelated) |
|---|---|---|
| What it is | A portable directory of skills (+ optional MCP servers) conforming to the open [Agent Plugins 1.0.0](https://agent-plugins.org/specification) spec | A Python package that runs inside `cao-server` and reacts to CAO lifecycle events |
| CAO code | `src/cli_agent_orchestrator/agent_plugins/`, `scripts/build_agent_plugin.py`, `agent-plugin/`, `src/cli_agent_orchestrator/schemas/agent_plugins/1.0.0/` | `src/cli_agent_orchestrator/plugins/` (not read) |
| Docs | `docs/agent-plugins.md` | `docs/plugins.md` |
| Authoring skill | none in CAO today (see below) | `cao-plugin` |
| CLI | `cao plugin add/list/validate/remove`, gated off by default | none of its own. `docs/plugins.md` promises a future `cao plugin list / info / enable / disable` (per `docs/agent-plugins.md:85`) |

The repo states the split itself at `docs/agent-plugins.md:3-9` and in the CLI group docstring, `src/cli_agent_orchestrator/cli/commands/agent_plugin.py:146-147`.

**The collision the new skill descriptions must avoid.** The `cao-plugin` skill describes itself in two different texts:

- **Repo copy** (`skills/cao-plugin/SKILL.md:3`, 443 chars, also shipped in `agent-plugin/cao-contributor/skills/cao-plugin/`): "Create a new CAO (CLI Agent Orchestrator) plugin. Use this skill whenever the user wants to add a plugin that reacts to CAO lifecycle or messaging events, scaffold a plugin package, understand plugin requirements, or integrate an external system (Discord, Slack, dashboards, logging, metrics) with CAO. Also use when the user asks what plugin events are available, how plugin discovery works, or how to install a plugin into a CAO environment."
- **Installed copy** (`$S/cao-plugin/SKILL.md:3`, 535 chars): "Scaffold and implement a CAO plugin — a Python observer package that hooks into server-side events (message_delivered, status_changed, session_created, terminal_deleted). Use when the user says "build a Discord/Slack/Telegram notification plugin", "hook into CAO events", "add audit logging to cao-server", "export agent metrics", "what plugin events exist", or "how does plugin discovery work". … Not for provider adapters, session management, SKILL.md authoring, or MCP Apps views."

Trigger phrases in the repo copy that overlap with agent-plugin authoring and auditing: "create a new CAO … plugin", "scaffold a plugin package", "understand plugin requirements", "how to install a plugin into a CAO environment". Neither copy contains the words "agent plugin", "Agent Plugins", `plugin.json`, `mcp.json` or "manifest". `docs/issues/573-agent-plugins/design.md:144-149` (decision **M4**, still open) already records that this description "will now compete for activation against agent-plugin requests", and proposes renaming the skill to `cao-event-plugin`.

## Existing skills (creator, audit, learning) — layout and provenance

### File inventory (`find $S/<skill> -type f`, with `wc -l`)

| Skill | Files (lines) |
|---|---|
| `cao-skill-creator` | `SKILL.md` (215), `scripts/validate_skills.py` (313), `scripts/scaffold_skill.py` (164), `scripts/run_trigger_evals.py` (441), `evals/evals.json` (57), `.DS_Store` (0). No `references/`. |
| `cao-skill-audit` | `SKILL.md` (177), `scripts/validate_skills.py` (313), `evals/evals.json` (53), `.DS_Store` (0). No `references/`. |
| `cao-learning` | `SKILL.md` (113) only. |

### Frontmatter and size

I measured these with `uv run --with pyyaml python` (exit 0). "Body" means the text after the closing `---`, stripped, which is how `validate_skills.py` counts it.

| Skill | Frontmatter keys | Description chars | Body lines |
|---|---|---|---|
| `cao-skill-creator` (installed) | `name`, `description`, `compatibility` | 608 | 209 |
| `cao-skill-audit` (installed) | `name`, `description`, `compatibility` | 475 | 171 |
| `cao-learning` (installed) | `name`, `description` | 336 | 104 |
| `cao-learning` (repo `skills/`) | `name`, `description` | 336 | 110 |

Verbatim descriptions:

- **cao-skill-creator** (`$S/cao-skill-creator/SKILL.md:3`): "Scaffold a new SKILL.md skill package, write or rewrite a skill description for better trigger accuracy, fix a skill that never activates, or learn the agentskills.io spec (name format, description length, progressive disclosure, evals.json). Use when the user says "create a skill", "scaffold a skill directory", "my skill doesn't trigger", "how do I write a SKILL.md", or "bundle scripts into a skill". Produces SKILL.md files with frontmatter, body, and evals/ directory. Not for auditing multiple skills at once (cao-skill-audit handles batch compliance). Not for provider adapters, plugins, or sessions." Its `compatibility` value is "Requires the CAO source tree. Uses validate_skills.py for validation."
- **cao-skill-audit** (`$S/cao-skill-audit/SKILL.md:3`): "Run batch compliance audits on Agent Skills. Use when checking all skills against the agentskills.io spec, validating a skills directory for violations, generating audit reports, comparing quality to a baseline, or fixing non-compliant skills in bulk. Also use when reviewing skill quality before shipping or verifying spec compliance (description length, name format, body size). Not for creating new skills from scratch (use cao-skill-creator) or managing sessions/plugins." Its `compatibility` value is "Requires the CAO source tree with skills/ directory. Uses validate_skills.py script."
- **cao-learning** (`$S/cao-learning/SKILL.md:3-7`, a multi-line YAML scalar): "Report task outcomes and distill lessons so the team improves across runs — report_outcome after each unit of work, retrospector handoffs at natural boundaries, and applying injected lessons. Use in workflows that run repeatedly over similar work items. Requires memory.learning_enabled; degrade silently when the tools report disabled." The repo and installed copies differ: `cmp` exits 1, first difference at line 21.

Both the creator and the audit descriptions **exclude "plugins"** as a boundary. Evolving them into agent-plugin skills reverses that boundary, so the new descriptions need their own negative boundary against event plugins.

### What the bodies say

- **cao-skill-creator** spec table, `SKILL.md:13-20`: name lowercase-hyphen ≤64 chars and equal to the folder name; description ≤1024 chars; body ≤500 lines. Scaffold tree at `:24-35`. Description-writing rules at `:47-56`. Progressive disclosure at `:78-94`, with references kept "one level deep" at `:93-94`. Gotcha 7 (`:163-164`): "Scripts without PEP 723 deps". The evals format with 5+ positive and 5+ negative trigger queries is at `:190-215`. It links `https://agentskills.io/skill-creation/evaluating-skills` (`:214`).
- **cao-skill-audit** rules table, `SKILL.md:17-28`: rules 1-5 are FATAL, 6-8 WARNING, 9-10 ADVISORY. Rule 10 is "PEP 723 inline deps or shebang". The audit procedure is Steps 1-5, followed by a scorecard template. `:177` says a copy of the validator lives in `scripts/`.
- **Both bodies invoke `python skills/cao-skill-creator/scripts/…`** (creator `:40,128,175,183`; audit `:54,57,130,173`). That path does not exist in this repo, because there is no `skills/cao-skill-creator/` (see Provenance).
- **cao-learning** is role-split (supervisor / worker / retrospector). It covers `report_outcome` with a `friction_notes` contract (`:25-45`), `memory_store` lessons ending in `Applies when:` (`:72-85`), and `store_lesson` for the retrospector (`:95-101`). It degrades silently when the tools return `disabled: true` (`:15-17`).

### Scripts: what each does, and PEP 723 status

All three creator scripts begin with a PEP 723 `# /// script` block (line 1 of each file).

| Script | PEP 723 deps | Behaviour | Exit codes |
|---|---|---|---|
| `validate_skills.py` | `pyyaml>=6.0` | Checks: SKILL.md present; frontmatter has `name` and `description`; name matches `^[a-z0-9]+(-[a-z0-9]+)*$` (`:32`); name ≤64 (`:33`); name equals the folder; description ≤1024 (`:34`); `compatibility` ≤500 (`:35`); body ≤500 lines (`:36`). A path with `SKILL.md` is one skill; otherwise each immediate child with `SKILL.md` is a skill (one level only). Supports `--format text\|json`. | 0 pass, 1 failures, 2 usage error (docstring `:16-19`) |
| `scaffold_skill.py` | none | Validates the name, refuses an existing directory, and creates `SKILL.md`, `scripts/`, `evals/evals.json` and `references/`. The SKILL.md template's description is a `<REPLACE …>` placeholder. The evals template has 5 should-trigger, 5 should-not-trigger and 1 eval. Supports `--output-dir`. | 0 / 1 |
| `run_trigger_evals.py` | `httpx>=0.27` (`:3`), **but it imports only `json, re, sys, pathlib`** (`:29-30`), so the dependency is unused | A **keyword heuristic, not a model**. It stems tokens and combines 0.35 overlap + 0.25 Jaccard + 0.20 body overlap + 0.20 bigram overlap (`:232`). A skill "triggers" if its score > 0.192 and it ranks in the top 2 across all skills in the directory, or if its score > 0.36 (`:295-307`). It strips "Not for …" and "Distinct from …" clauses before scoring (`strip_negative_boundaries`, `:152`), so negative boundaries earn no credit in this heuristic. | 0 all pass, 1 some fail, 2 usage |

`$S/cao-skill-audit/scripts/validate_skills.py` is byte-identical to the creator's copy. `cmp` exits 0, and both have sha256 `46303ea63f457ee68ace25123348f9b6b3a28e086c17faf480f28428c4afe467`.

### evals/ format: two incompatible shapes in use

- **Object shape** (creator, audit, installed `cao-plugin`, repo `cao-mcp-apps`, repo `mcp-apps-builder`): `{"skill_name", "trigger_evals": [{"query", "should_trigger"}], "evals": [{"id", "prompt", "expected_output", "assertions": [...]}]}`. The creator and audit files each have 10 trigger evals and 3 evals.
- **List shape** (`skills/agui-author/evals/evals.json`: 8 items; `$S/agui-author/evals/evals.json`: 16 items): `[{"input", "expected"}]`.

`run_trigger_evals.py` assumes the object shape. `--all skills/` crashes on agui-author with `AttributeError: 'list' object has no attribute 'get'` at `run_trigger_evals.py:186` (exit 1). See the gates table.

The audit evals reference artifacts that do not exist. `evals.json:18` hardcodes an absolute path under a developer's home directory, ending in `…/cli-agent-orchestrator/skills/`, and `ls` on that full path exits 1. The evals also name `skills/cao-skill-audit/evals/baseline-report.json` (`:42`; `evals/` holds only `evals.json`) and `npx skills-ref validate` (`:33`).

### Provenance

- `git log --all --oneline -- '*cao-skill-audit*' '*cao-skill-creator*'` in the worktree: **no output, exit 0.** No commit on any local or remote-tracking ref has ever touched a path with either name.
- `git log --all --oneline -- 'skills/*'`: 104 commits, exit 0. `git log --all -S'cao-skill-creator' --oneline` finds `d04c51e1`: "fix(skills): remove the dangling cao-skill-creator route and guard against recurrence". Its message says: "`cao-skill-creator` does not exist in skills/ on this branch or on main, and no open PR adds it." `d04c51e1` is not an ancestor of `upstream/main` (`git merge-base --is-ancestor`, exit 1), but its guard did land: `test/test_cao_contributing_skill_accuracy.py:534-559` at `00611d11` (was `:492-517`; `TestReferencedSkillsExist`, docstring at `:537`, was `:495`: "#448 shipped a route to `cao-skill-creator`, which never existed in `skills/`").
- `git grep -n "cao-skill-creator\|cao-skill-audit" upstream/main`: the only hit is that test docstring.
- `find /Volumes/workplace/open-source -maxdepth 5 -type d \( -name cao-skill-creator -o -name cao-skill-audit \)`: no output, exit 0.
- Both `SKILL.md` files have mtime `Jul 1 06:31:39 2026`. So do `$S/cao-reinstall/SKILL.md`, `$S/workflow-author/SKILL.md` and `$S/cao-plugin/SKILL.md` (`stat -f %Sm`). That is consistent with one batch install, from a source I could not identify (see Unverified).
- **Conclusion:** `cao-skill-creator` and `cao-skill-audit` are not repo-tracked anywhere I could reach. They exist only in the installed store.

**What `skills/` in the worktree contains** (`ls skills`): 14 skill directories (`agui-author`, `cao-agent-routing`, `cao-contributing`, `cao-learning`, `cao-mcp-apps`, `cao-memory`, `cao-plugin`, `cao-provider`, `cao-session-liveness`, `cao-session-management`, `cao-supervisor-protocols`, `cao-worker-protocols`, `cao-workflow`, `mcp-apps-builder`), plus `vendor/ext-apps/` (4 vendored skills) and `plugin.json`. `skills/plugin.json` (`name: cao-skills`, no `$schema`) is the inert, non-conformant proto-manifest analysed at `docs/issues/573-agent-plugins/design.md:864-883`. All 14 directories are in `SHIPPED_SKILLS` (`scripts/sync_skills.py:44-59`), which mirrors them into `src/cli_agent_orchestrator/skills/`.

**Consequence for the spec:** a new skill added to `skills/` is not shipped in the wheel unless it is added to `SHIPPED_SKILLS`. It is not in any agent-plugin package unless it is added to a `PackageConfig.skills` allowlist in `scripts/build_agent_plugin.py`. The comment at `scripts/sync_skills.py:35-43` says a rename also needs `SKILL_RENAMES` in `cli/commands/init.py`.

## Agent Plugins v1.0.0 in CAO — package shape and existing validation

### Authority

The authority is the vendored schemas: `src/cli_agent_orchestrator/schemas/agent_plugins/1.0.0/{plugin,mcp}.schema.json`, pinned by `PIN.json`. The pin records upstream commit `b78a4f162d92c4b09ee205a11f59a6187926d947` (`PIN.json:6`) and sha256 `0a4aad95…b883` for the plugin schema and `6539175b…acb` for the mcp schema (`PIN.json:13,18`). `PIN.json:7` says §5.2 forbids fetching a schema while loading a plugin, so these bytes are the only schemas CAO validates against. A single fetch of `https://agent-plugins.org/specification` returned **HTTP 200** (`curl -sS -o /dev/null -w '%{http_code}' --max-time 20`, exit 0). The site was reachable from this seat, but I did not read the spec prose. Every rule below comes from the vendored schemas or CAO's code.

### What a package requires

| Item | Requirement | Source |
|---|---|---|
| Manifest file | `plugin.json` at the plugin root | `validation.py:74` (`_MANIFEST_FILENAME`); `docs/agent-plugins.md:38-48` |
| Required manifest keys | `$schema` and `name` only | `plugin.schema.json:63` |
| `$schema` | `const` `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json` | `plugin.schema.json:8-11` |
| `name` | 1-64 chars, pattern `^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$` (dots allowed; no `--` or `..`) | `plugin.schema.json:12-18` |
| Optional keys | `version`, `description`, `author{name,email,url}` (closed), `homepage`, `repository`, `license`, `keywords[]`, `extensions{}` | `plugin.schema.json:19-61` |
| Closed schema | `additionalProperties: false`, so an unknown key is FATAL (`manifest.unknown_field`) | `plugin.schema.json:64`; `test/agent_plugins/fixtures/corpus/manifest-unknown-field/` |
| Skills placement | Optional `skills/`, where each immediate child is one Agent Skill with a `SKILL.md`. A missing `skills/` is not an error. | `validation.py:72,580-640`; `docs/agent-plugins.md:39-47,307-309` |
| Skill validity | Uses CAO's own loader: `name` and `description` must be non-blank, and the folder name must equal the frontmatter `name`. An invalid skill is SKIPPED, not fatal. | `validation.py:685-705` → `utils/skills.py:66-69`, `models/skill.py:9-19` |
| MCP config | Optional `mcp.json`. Required keys `$schema` and `mcpServers`, closed. stdio entries need `type` + `command` (and allow `args`, `env`, `cwd`); `streamable-http`/`sse` entries need `type` + `url` (and allow `headers`). | `mcp.schema.json:19,71,90,109` |
| README / CHANGELOG / LICENSE | **Not required by either vendored schema.** CAO's builder generates `README.md` and `CHANGELOG.md` and copies `LICENSE` into its own packages. | `build_agent_plugin.py:92,689-691,707-710` (at `00611d11`) |

CAO's skill check does **not** enforce the Agent Skills name regex, the 1024-char description limit, or the 500-line body limit. `SkillMetadata` has only the two non-blank string fields (`models/skill.py:9-19`). Those limits exist only in `validate_skills.py`, and as T3 in the harness-oss validator. A plugin skill named `My_Skill` with a 2000-char description would pass `cao plugin validate` if its folder matched. I inferred this from the code and did not run that case.

### The two existing packages (not one)

`agent-plugin/` holds **two** real packages, both generated by `scripts/build_agent_plugin.py` (`:4-13` at `00611d11`, `PACKAGES = [OPERATOR, CONTRIBUTOR]` at `:188`). From `find agent-plugin -type f`:

- `agent-plugin/cao/`: `plugin.json` (name `cao`, version `2.5.3`, `repository`, `license: Apache-2.0`, 4 keywords), `mcp.json` and a byte-identical `.mcp.json` (one stdio server `cao-ops`: `uvx --from cli-agent-orchestrator==2.5.3 cao-ops-mcp-server`), `.claude-plugin/plugin.json` (name/version/description only), `README.md`, `CHANGELOG.md`, `LICENSE`, and `skills/{cao-agent-routing,cao-session-management,cao-supervisor-protocols,cao-worker-protocols}/SKILL.md`.
- `agent-plugin/cao-contributor/`: the same shape without `mcp.json`. Skills: `cao-plugin/` (with `references/hook-events.md`, `references/plugin-template.md`), `cao-provider/` (with `references/{lessons-learnt,provider-template,test-guide}.md`) and, since #1121 (`00611d11`), `cao-contributing/` (with `references/{pr-gating-workflows,test-isolation}.md`). Allowlist at `build_agent_plugin.py:162-186` (`00611d11`; was `:145-169` with two skills).
- Both packages pin `2.5.3` while `pyproject.toml` is at `2.5.4`. This lag is deliberate (`docs/agent-plugins.md:11-23`; `--check` output below).

A dogfood package for the two new skills needs one of two design choices: add the skills to the `CONTRIBUTOR` allowlist, or add a third `PackageConfig`. In both cases the skill must first exist under repo `skills/`, because `source_skill_dir` raises `BuildError` otherwise (`build_agent_plugin.py:666-674` at `00611d11`), and the drift guard requires discovered skills to equal the allowlist (`:790-794`).

**Stale-text facts the spec should know about:**

- **Resolved by #1121 (`00611d11`):** at `556726a4`, `build_agent_plugin.py:37-39,159,165` said `cao-contributing` "depends on PR #448, which is open and still a draft", although #448 merged as `5471d8f5dba94abfc267fb8037fc3e663a46e336` on 2026-09-25. At `00611d11`, `:37-39` says "#448 merged, and adding it was the one allowlist line this design promised (#1120)", and `:179` is the allowlist comment. `cao-contributing` is in `SHIPPED_SKILLS` (`scripts/sync_skills.py:58`, unchanged).
- **PR #1121 is merged** as `00611d119ce6e8c8a940929f4f59c58e34a8ea2e` (2026-10-30T06:37:43Z; head at merge `a383533b`; `gh api …/pulls/1121`, exit 0). Its `CONTRIBUTOR` edit is now on `main` (`build_agent_plugin.py:162-186`), so the earlier conflict risk is gone. `a64bbc76` was its head on 2026-10-29 and describes nothing current.

### Decisions recorded in #573 that bear on this work

- `docs/issues/573-agent-plugins/design.md:151`: "A new `cao-agent-plugin` authoring skill is **out of scope** here; the ecosystem's `migrate-agent-plugin` skill already covers authoring, and CAO dogfoods it (**D4**)." The same decision appears at `:862` and `:1172`. `migrate-agent-plugin` exists in the repo only as a test fixture (`test/agent_plugins/fixtures/canonical-example/skills/migrate-agent-plugin/SKILL.md`, upstream commit `5f3f5084…` per its `NOTICE`). Its description covers migrating client-specific plugins to v1, not creating one from scratch.
- **The M1 status disagrees between files.** `design.md:4` says "**M1 is decided — Option A, `cao plugin`**". `docs/agent-plugins.md:82-88` still says M1 "is not settled". `requirements.md:5,371-386` treats M1-M4 as open. M2-M4 are open in all three.

### Format model (`docs/issues/573-agent-plugins/`)

- `requirements.md` (454 lines): a blockquote header (Feature, Issue of record, Derived from, Open maintainer decisions) and `## Scope of this document`. Then `## Requirements` with numbered `### Requirement N: <title>`, each containing `**User Story:** As a …, I want …, so that …`, `#### Acceptance Criteria` in numbered EARS-style SHALL statements, sometimes tagged `[Increment N]`, and a `**Traceability:**` line (`:30-47`). It closes with `## Traceability Matrix`, mapping properties P1-P11 and acceptance criteria AC1-AC7 to requirements (`:421-454`).
- `design.md` (1329 lines): Overview, Goals, Non-Goals, Naming and Namespacing (M1-M4), Increment Boundary, Architecture, Components and Interfaces (10 numbered parts), Data Models, Sequence Diagrams, Failure Isolation, `## Correctness Properties` (P1-P11), Error Handling, Testing Strategy, Author Side, Buildable Units, Coverage of ACs, Security, Performance, Dependencies, Review 4 Decisions, and `## Decisions Requiring Maintainer Sign-Off` (headings from `grep -n "^## \|^### "`).
- `opencode-verification.md` (301 lines): a standalone evidence note (source read plus an empirical run with a positive control).

### The `/plugins*` gate (default off)

- The predicate is `agent_plugins_surface_enabled()`, `src/cli_agent_orchestrator/agent_plugins/gate.py:36-42`. Only `1`/`true`/`yes` in `CAO_AGENT_PLUGINS_ENABLED` (`:31,33`) opens the surface. The gate is env-only by design (`:16-20`).
- HTTP: `_require_plugins_enabled` at `src/cli_agent_orchestrator/api/main.py:3548` is applied as a route dependency on `GET /plugins` (`:3617`), the POST install route (`:3666`), `POST /plugins/validate` (`:3711`) and `DELETE /plugins/{name}` (`:3742`). The disabled surface answers 404 (`:3541-3545`).
- CLI: `@click.group("plugin", hidden=True)` at `cli/commands/agent_plugin.py:142`, which raises a `ClickException` when the gate is off (`:153-158`).
- Web: `PLUGINS_TAB_ENABLED = false` at `web/src/featureFlags.ts:28`.
- Observed: with the variable unset, `cao plugin validate ./agent-plugin/cao` printed "The agent plugin surface is not released yet (Requirement 16.5, pending maintainer decision M1). Set CAO_AGENT_PLUGINS_ENABLED=1 to enable it." and exited **1**.

### The harness-oss validator

`/Volumes/workplace/open-source/harness-oss/tools/validate-plugin.py` (380 lines; harness-oss HEAD `c42258423615569134f422a8c307caf786dd17d5`) is a dependency-free structural checker with tiers T0-T5 (docstring `:1-16`).

- **It validates only its own repository.** `ROOT = Path(__file__).resolve().parent.parent` (`:25`) and it never reads `sys.argv` (`grep -n "sys.argv\|argparse"` exits 1). Running it from the CAO worktree with `agent-plugin/cao` as an argument still reported `name 'revive-oss-pr'` and `aws-nx-scaffolding`, which is harness-oss's own package, and exited 0. You cannot point it at a CAO package without changing it.
- **Same schema bytes:** `harness-oss/tests/schema/plugin.schema.json` and `mcp.schema.json` are byte-identical to CAO's vendored copies (`cmp` exit 0 for both; sha256 `0a4aad95…` and `6539175b…`, equal to `PIN.json`). However, it does **not** run JSON Schema validation against them. It uses a hand-coded allowlist and only *compares* that allowlist with the schema's property set (`:31-35,112-120`). The name check is equivalent to the schema pattern: `NAME_RE` at `:38` plus separate `--`/`..` substring checks at `:136-138`.
- It checks skill rules that CAO's validator lacks: description ≤1024 is a FAIL (`:208`), and a body over 500 lines is a WARN (`:214`).
- Exit status: 0 when conformant, 1 on any failure (`:356-376`).

The harness-oss package `revive-oss-pr` is installed in this machine's CAO store. `$S/aws-nx-scaffolding` is a symlink into `~/.aws/cli-agent-orchestrator/agent-plugins/revive-oss-pr/skills/aws-nx-scaffolding` (`ls -la $S`). That makes it a real non-CAO agent plugin installed through CAO's own projection.

## Available shift-left gates (exact commands + observed exit status)

All commands ran in the worktree at `556726a4` on 2026-10-29 (re-run at `00611d11` on 2026-10-30: `build_agent_plugin.py --check` 0, `vendor_agent_plugins_schemas.py --check` 0, `sync_skills.py --check` 0 "14 shipped skills", `validate_skills.py skills/` 0 "14 passed"; the rest not re-run), each under `perl -e 'alarm N; exec @ARGV' --`. For the `cao plugin` runs, `CAO_HOME_DIR` pointed at a fresh `mktemp -d` directory, and I confirmed afterwards that no files had been written to it.

| Gate | Exact command | What it proves | Observed exit |
|---|---|---|---|
| Agent-plugin drift + conformance | `uv run python scripts/build_agent_plugin.py --check` (= `make check-agent-plugin`, `Makefile:46-47`; CI `ci.yml:100-101`) | Committed `agent-plugin/{cao,cao-contributor}` equal a fresh build. CAO's validator reports 0 FATAL and loadable. Discovered skills equal the allowlist. `mcp.json` rules hold (`build_agent_plugin.py:731-866` at `00611d11`). Offline. | **0**: "OK: agent plugin packages in sync and loadable at the version they were built at, 2.5.3 (cao, cao-contributor). pyproject.toml is now at 2.5.4…" |
| Schema pin | `uv run python scripts/vendor_agent_plugins_schemas.py --check` (= `make check-agent-plugins-schemas`; CI `ci.yml:94-95`) | Vendored schema bytes match `PIN.json`. | **0**: "OK (local): 2 vendored Agent Plugins 1.0.0 schemas match PIN.json" |
| Validate a package (CAO) | `CAO_AGENT_PLUGINS_ENABLED=1 uv run cao plugin validate ./agent-plugin/cao` | Loadable; skills named; `mcp.json` present. | **0**: "cao: loadable / skills: cao-agent-routing, cao-session-management, cao-supervisor-protocols, cao-worker-protocols / mcp.json: present" |
| Same, JSON | `CAO_AGENT_PLUGINS_ENABLED=1 uv run cao plugin validate ./agent-plugin/cao-contributor --json` | Machine-readable report: `loadable`, `skills[]`, `mcp_present`, `findings[]`. | **0**: `"loadable": true`, `"findings": []` |
| Validator negative control | `CAO_AGENT_PLUGINS_ENABLED=1 uv run cao plugin validate ./test/agent_plugins/fixtures/corpus/manifest-missing-name` | A FATAL finding makes the command exit non-zero. | **1**: "NOT loadable / FATAL §5.2 manifest.invalid [plugin.json]: 'name' is a required property" |
| Gate-off behaviour | `env -u CAO_AGENT_PLUGINS_ENABLED uv run cao plugin validate ./agent-plugin/cao` | The CLI refuses to run while the gate is off. | **1** (message quoted above) |
| Skill mirror drift | `uv run python scripts/sync_skills.py --check` | `skills/` and `src/cli_agent_orchestrator/skills/` agree for the 14 `SHIPPED_SKILLS`. | **0**: "OK: 14 shipped skills are in sync." |
| Skill spec limits | `uv run --script $S/cao-skill-creator/scripts/validate_skills.py skills/` | Name, length, folder, description and body limits for each child of `skills/`. | **0**: "14 passed, 0 failed" (`skills/vendor` has no top-level `SKILL.md` and is not scanned) |
| Same, packaged copies | `uv run --script $S/cao-skill-creator/scripts/validate_skills.py agent-plugin/cao/skills agent-plugin/cao-contributor/skills` | The limits also hold in the packaged copies. | **0**: "6 passed" |
| Same, on the skills being evolved | `uv run --script $S/cao-skill-creator/scripts/validate_skills.py $S/cao-skill-creator $S/cao-skill-audit $S/cao-learning` | The source skills meet their own spec. | **0**: "3 passed" |
| Trigger evals (heuristic) | `uv run --script $S/cao-skill-creator/scripts/run_trigger_evals.py -- --skill <name> <dir>` | Keyword-rank heuristic only (see caveat above). | creator in `$S`: **1** (7/10; false triggers on "create a new CAO provider…", "audit all skills…", "write a Discord plugin…"). audit in `$S`: **0** (10/10). cao-plugin in `$S`: **0** (10/10). `cao-mcp-apps` in `skills/`: **1** (9/10). `mcp-apps-builder` in `skills/`: **1** (8/10, including a false trigger on "create a CAO plugin that sends messages to Slack"). |
| Trigger evals, `--all` | `uv run --script …/run_trigger_evals.py -- --all skills/` | — | **1**: crashes on agui-author's list-shaped evals (`AttributeError`, `run_trigger_evals.py:186`) |
| Markdown links | `uv run python scripts/validate_markdown_links.py` (CI `ci.yml:88-89`) | Local Markdown links in the repo resolve. | **0** |
| Targeted tests | `uv run pytest -q -p no:cacheprovider test/agent_plugins/test_packages.py test/agent_plugins/test_schema_pin.py test/agent_plugins/test_conformance_corpus.py test/test_cao_contributing_skill_accuracy.py` | Package invariants, the pin, the conformance corpus, and the referenced-skills-exist guard (`:534-559` at `00611d11`). | **0**: "169 passed in 147.36s" |
| harness-oss validator | `python3 /Volumes/workplace/open-source/harness-oss/tools/validate-plugin.py` (from `harness-oss`) | Only harness-oss's own `revive-oss-pr` package (see above). | **0**: "13 passed, 0 warning(s), 0 failure(s)" |

Inspected but not run: the CI job `agent-plugins-dogfood`, "Agent Plugins dog-food (shift-left recording)" (`.github/workflows/ci.yml:509-559`). It records `docs/media/agent-plugins-dogfood-demo.gif` only when the asserting script exits 0 (`docs/agent-plugins.md:669-707`; example in `examples/agent-plugins/agent-plugins-dogfood/`).

Blog build constraints, inspected only: `docusaurus/docusaurus.config.ts:64-66` sets `onInlineAuthors: 'throw'`, `onInlineTags: 'throw'` and `onUntruncatedBlogPosts: 'throw'`. A post therefore needs an `authors.yml` key, a tag from `tags.yml`, and a `<!-- truncate -->` marker. `docusaurus/blog/authors.yml` has keys `cao-maintainers, haofeif, fanhongy, anilkmr-a2z, gutosantos82, sujoydc, guojing1217, googio, yinsong1986`, and **no `plauzy`** (`grep -n "^[a-z0-9-]*:$"`). The tags are `tutorial, deep-dive, orchestration-patterns, providers, mcp, case-study, community, physical-ai` (`tags.yml`). Existing posts follow `docusaurus/blog/YYYY-MM-DD-slug/index.md`; the latest is `2026-10-12-cao-aidlc-orchestration`. The `npm run build` path (`docusaurus/package.json:11-12`) was not run.

## AG-UI in CAO

- **Surface:** `GET /agui/v1/stream` (SSE) and `POST /agui/v1/emit_ui`. Both are default-off and return 404 unless `CAO_AGUI_ENABLED` (or `CAO_MCP_APPS_ENABLED`) is set (`docs/agui.md:14-26`; `services/agui_enablement.py:29-32`; `_require_agui_enabled` at `api/main.py:2132-2136`).
- **The frozen six-component allow-list** is `GENERATIVE_UI_COMPONENTS = frozenset({"approval_card", "choice_prompt", "diff_summary", "progress", "metric", "agent_card"})`, defined at `src/cli_agent_orchestrator/services/agui_stream.py:91-100`. Props are capped at 8 KiB (`_MAX_GENERATIVE_PROPS_BYTES = 8 * 1024`, `:104`). It is enforced in three places:
  1. The HTTP producer, `api/main.py:2526-2533`: an off-list component gets 400 before anything reaches the bus.
  2. The stream mapper, `services/agui_stream.py:314`: an off-list component maps to `RAW` with a rejection marker (comment at `:86-90`). Props over 8 KiB are handled at `:326`.
  3. The L2 construct base, `services/agui/base.py:339-343`: raises `ValueError`.
  The `emit_ui` MCP tool lists the same six at `mcp_server/server.py:1007`. The threat table is at `docs/agui.md:192-204`.
- **Docs and examples:** `docs/agui.md` (463 lines) covers the two-plane model (`:224-286`) and the L2 construct library (`:287-403`). `examples/ag-ui/` has 11 examples, including `cao-dojo`, `ag-ui-handoff-approval`, `ag-ui-meta-dogfood` and `run-plane-finishes` (`ls`, plus the first line of each README).
- **The `agui-author` skill:** the installed copy (`$S/agui-author/SKILL.md`, 680-char description) names the six components and says "Arbitrary HTML/markup is refused server-side" (`:2-11`). The repo copy differs (`cmp` exit 1; 400-char description, 161 body lines). The installed copy bundles `scripts/validate.sh`, `scripts/e2e-video-proof.sh` and three `references/` files.
- **Fork:** `/Volumes/workplace/open-source/ag-ui`, branch `cao-integration-458` at `0eff920842191b0797582031a111266e21c1dd79` ("chore(cli-agent-orchestrator): install CAO at the upstream #1107 merge"). Origin is `plauzy/ag-ui` and upstream is `ag-ui-protocol/ag-ui`. It is 12 commits ahead of the local `upstream/main` ref `dab9c95f8` (`git rev-list --count`; that ref was not re-fetched this session). It contains `integrations/cli-agent-orchestrator/{python,typescript,scripts,README.md,agui-approver.md}`.

## Authorship and PR history (recounted)

### Kiro trailers on `upstream/main` (`556726a4`, after `git fetch upstream`, exit 0)

I ran exactly `git log upstream/main --format='%an%x09%(trailers:key=Co-authored-by,valueonly)'` (exit 0) and counted with `grep`:

- Lines beginning `Pat Lauer<TAB>`: **18**. Of those, **15** carry `Kiro Agent <244629292+kiro-agent@users.noreply.github.com>` and 3 carry no trailer (`sort | uniq -c`).
- Lines containing "kiro" (case-insensitive) in the whole output: **15**. So all 15 Kiro co-authored commits on `upstream/main` are plauzy's.
- Identity: all 18 are `Pat Lauer <4451274+plauzy@users.noreply.github.com>`. The separate authors `Patrick` (10) and `Patrick Liao` (6) use `liao.patrick@gmail.com` and are a different person.
- Plain commit-count rank by `%an`: Stan Fan 109, Ted Swinyar 86, haofeif 73, dependabot[bot] 67, anilkmr-a2z 26, Augusto Dias 23, Harshit Wandhare 22, then RAM.R.K and Pat Lauer tied on 18 (8th/9th). Measured at `556726a4`; not for publication as a rank.
- **Updated count:** the 2026-10-27 memory said 14 of 17. At `556726a4` it is **15 of 18**. **Re-run at `9d029f9d4db16df2725bd04751756fd0b7d27440` (2026-10-29)** with `git log 9d029f9d --format='%an%x09%(trailers:key=Co-authored-by,valueonly)'` (exit 0): `Pat Lauer<TAB>` lines **18**, of which **15** carry the Kiro trailer; Kiro lines overall **15**. Unchanged, because the only commit between the two shas is `9d029f9d` (#1151), which is not plauzy's. **Re-run at `00611d119ce6e8c8a940929f4f59c58e34a8ea2e` (2026-10-30T02:01-05:00)** with `git log 00611d11 --format='%an%x09%(trailers:key=Co-authored-by,valueonly)'` (exit 0): `Pat Lauer<TAB>` lines **19**, of which **16** carry the Kiro trailer; Kiro lines overall **16**; `--format='%an <%ae>' | grep -c plauzy@` = 19. The new plauzy commit is `00611d11` (#1121), which carries the Kiro trailer; the other two new commits (`5229b712`, `2402141f`) are not plauzy's.
- The commits without a Kiro trailer are `720a3c40` (#1115), `0214f238` (#332) and `a4708eba` (#333). `5dcf3198` (#347) also carries a `haofeif` co-author trailer (`git log upstream/main --author=plauzy… --format='%h … [%(trailers…)]'`).

### Merged PRs by plauzy (`gh api search/issues`)

Query `repo:awslabs/cli-agent-orchestrator is:pr is:merged author:plauzy`, `per_page=100`. Page 1 returned `total_count` **18** with 18 items (exit 0). Page 2 returned 0 items (exit 0). The result set is complete and reconciled.

Agent Plugins and AG-UI subset, with merge shas from `gh api repos/awslabs/cli-agent-orchestrator/pulls/<n>` (exit 0):

| PR | Merged (UTC) | Merge sha | Title |
|---|---|---|---|
| #584 | 2026-09-20 | `156cf1edcdb9de1ee01a2f17c2a4026e5f305e56` | feat(agent-plugins): Agent Plugins 1.0.0 support — client pipeline, CAO-as-plugin packages, MCP delivery (#573) |
| #436 | 2026-07-17 | `a9af15953bd25980638311f44c97a5e7b43e1ed7` | feat(agui): AG-UI protocol adapter + generative UI (L1, default-off) — supersedes #387 |
| #485 | 2026-07-22 | `edf61cad65a8183d37466f2d112d19a365cfca5c` | feat(agui): AG-UI Phase 2 — L2 construct library (#458) |
| #1107 | 2026-10-28 | `9fb5e1e4a8243a032a023718e9177e425230bec6` | fix(agui): finish /agui/v1/run after resume; detect Claude Code 2.1.310 permission prompts |
| #1115 | 2026-10-28 | `720a3c40f61ee826767ff37955b5ebba8a687b61` | fix(agui): offer approve and deny only on Claude Code permission prompts |
| #1117 | 2026-10-28 | `e54e610d5e5eb5efe8bd4dd30f4e7232bb467923` | fix(agui): follow-ups to #1107; refuse resume[] without an approval bridge; valid run-plane doc bodies |
| #1111 | 2026-10-28 | `2573bd17f3dfda76e4101494b0212cc6de8b29a6` | feat(examples): CAO Dojo page with an answerable AG-UI approval card |

Related skill PR: #448 (`5471d8f5…`, merged 2026-09-25), "feat(skills): add cao-contributing skill". The other 10 merged PRs are #1119, #576, #574, #456, #452, #435, #347, #346, #333 and #332 (security, CI, test and MCP Apps work).

## PR #1121 worked example

**PR:** #1121, "docs(skills): encode the #1119 lessons in contributor skills and the cao-contributor plugin". **Merged** as `00611d11` on 2026-10-30 (`gh api …/pulls/1121`: `merged=true`, merge sha `00611d119ce6e8c8a940929f4f59c58e34a8ea2e`, head at merge `a383533b`), authored by plauzy; the merge commit carries a `Kiro Agent` co-author trailer. (Observed 2026-10-29, before the merge: head `a64bbc76`, six non-merge commits by plauzy, each with a `Kiro Agent` trailer.)

All files below are in `/Volumes/workplace/open-source/.agents/plans/pr1121/` unless the path says otherwise.

**What triggered it.** Maintainer haofeif requested changes at `4ebd1cee` (`review-5683175646.md:1`): 2 × P2 and 6 × P3. The review includes replayable experiments:

- P2-1: rule 2 would add a base dependency for an extra-only CVE fix (`:21-35`).
- P2-2: merging `main` (#1108, `921093be`) leaves the plugin copy stale and fails `make check-agent-plugin` (`:37-49`).
- P3-1: the uv lock `revision` header (`:51-57`).
- P3-2: a stale wheel in `dist/` (`:59-67`).
- P3-3: the plugin rebuild in item 7 (`:69-75`).
- P3-4: a vacuous path guard (`:77-83`).
- P3-5: a conflict with `code_supervisor` (`:85-89`).
- P3-6: a stale package description (`:91-95`).

**Who drove it.** The plan was written in a Kiro CLI session: the plan's frontmatter points at `/Volumes/workplace/open-source/.kiro/logs/2026-10-29-10-09.md`, which is headed "# Kiro Session Log". Plan decision D5 (`../2026-10-29-pr1121-haofei-review.md:72`) lists the worker and reviewer seats. CAO's database confirms the seats ran as CAO terminals in dedicated `cao-pr1121-*` sessions (`sqlite3 … "SELECT t.id,t.agent_profile,t.provider,t.tmux_session FROM terminals …"`, exit 0). Under the attribution directive (`review-1.md:32`) they are listed here by role only:

| Terminal | Role |
|---|---|
| `6097c168` | worker: tests, build script, package regeneration |
| `a37b664a` | worker: skill text |
| `640b944b` | read-only reviewer |
| `1bbc1a3c` | read-only auditor |

The `inbox` table shows the briefs went in through the outside-a-session ops server: rows 269-273 and 282-283 have `sender_id = 'cao-ops-mcp'` and receivers among those terminals, timestamps 2026-10-29 16:30-21:08 (DB clock; `status=delivered`). No inbox row has one of those seats as sender. **Results came back as files** (the `report-*.md` and `review-*.md` files ending in `DONE`), not as `send_message` callbacks.

**What happened, phase by phase.**

1. **Red first.** `phase1-red.txt:1-12` records `build_agent_plugin.py --check` failing with "CONTENT DIFFERS in agent-plugin/cao-contributor/: skills/cao-contributing/SKILL.md" (`check-agent-plugin exit=2`), plus the named failing tests.
2. **Parallel workers with disjoint file ownership.** One worker seat owned only the two `SKILL.md` files (the skill-text brief, `:11-17`). Another owned only the test and the build script (the test-and-build brief `:11-17`). That worker reproduced the P3-4 bug as a mutation that stayed green (the test-and-build worker's report `:22-32`: "`103 passed` — the bug"), then fixed it until the same mutation went red (`:104-112`).
3. **Regenerate and gate at the held pin.** The regeneration-and-gates brief `:9-27` rebuilt the packages in-process at `committed_package_version()` = 2.5.3, because the script has no keep-pin flag (plan D4, `:71`). The regeneration-and-gates report `:145-159` lists the gates: ruff exit 0; the targeted set exit 0 with "1512 passed, 11 skipped"; the P2-2 tests "5 passed". Its first gate batch was red (`sync_skills --check` exit 1, `:53`), and the report records that rather than hiding it (`:77`).
4. **Independent read-only reviewer seat with an advisor, replaying the maintainer's experiments.** The reviewer seat could not write files; the supervisor saved its reply (`review-round1.md:1`). It specified experiments E1-E5 for the test-and-build worker to run verbatim (`review-round1.md:32`). The first pass returned `VERDICT: CHANGES NEEDED` because the evidence was still pending (`:134`). `report-5-experiments.md:6` reports "E1 PASS, E2 PASS, E3 PASS, E4 PASS, E5 PASS". The final round is `VERDICT: APPROVE` (`review-round1.md:202`), pinned to the exact tree and md5s (`:145-150`). The advisor's input is tabulated at `:119-128` and `:198-200`.
5. **Second-opinion review.** The second-opinion feedback file (`:1-4`) records that its repo tools failed, so it reasoned from text. The supervisor annotated each claim as verified or contradicted. Example: its claim that `unzip` concatenates wheels was "CONTRADICTED by haofeif's experiment" (`:20-22`).
6. **Skill and Agent Plugin package audit** (the audit brief). The brief told a read-only reviewer seat to audit the changed skills and packages against `$S/cao-skill-audit/SKILL.md` rules 1-10, to use its scorecard, and to consult its advisor (`:12-14,42`). The audit report returned:
   - the scorecard (`:5-16`);
   - "Must fix in #1121: None" (`:48-50`);
   - 8 follow-ups (`:52-66`), among them R6 WARNING for the `cao-supervisor-protocols` description being declarative, which predates #1121;
   - a correction to the brief's premise. The spec URL already appears in about ten places (`:28-38`).
   - It also recorded that a second-opinion audit file did not exist at the time, instead of substituting older files (`:1`, `:75`).
7. **Status.** The plan's §7 says "READY TO PUSH (awaiting the user's OK)", with the full suite in 8 shards: "20611 passed, 129 skipped, 2 failed, both environmental and both also on main; combined branch coverage 93%" (`../2026-10-29-pr1121-haofei-review.md:278-291`). `pr-reply-draft.md` is the unposted reply, which maps each finding to a commit. *(Since then, #1121 merged as `00611d11` on 2026-10-30.)*

**What this shows for the blog.** A Kiro CLI session wrote the plan and briefs, and CAO ran the worker and read-only reviewer seats as separate terminals. The work used shift-left gates: red-first mutations, gates run at a held pin, and byte-identity md5 checks across copies. The reviewer seat's verdict was gated on replays of the maintainer's own experiments. The commits are plauzy's with Kiro co-author trailers. The PR is not merged, so the post should not describe it as shipped.

**Caveat for the spec authors.** The #1121 audit brief (`:15-16`) says the harness-oss `validate-plugin.py` was run "on `agent-plugin/cao` and `agent-plugin/cao-contributor`" and passed with 13 checks. Because the script hard-codes its own `ROOT` (`validate-plugin.py:25`) and ignores arguments, those runs validated harness-oss's own package, not CAO's. The CAO packages are independently conformant per `make check-agent-plugin` and `cao plugin validate` (both exit 0 above), so the conclusion holds, but that piece of evidence does not support it.

## Unverified / blocked

- **Where `cao-skill-creator` and `cao-skill-audit` came from.** No git history in the worktree (`git log --all …`, empty, exit 0) or on disk to depth 5 (`find`, empty, exit 0). The only clue is the shared mtime `Jul 1 06:31:39 2026` with `cao-reinstall`, `workflow-author` and `cao-plugin`. I did not search GitHub or other repos beyond `/Volumes/workplace/open-source` at depth 5.
- **Agent Plugins spec prose.** `curl` returned HTTP 200, but I did not read the specification text. Statements about README, CHANGELOG or LICENSE being required or not rest only on the vendored schemas and CAO's code. Section numbers quoted in CAO code (§4.1, §5.2, §7.2.1 and so on) are CAO's citations, not re-checked against the spec.
- **Whether `cao plugin validate` admits a skill that breaks the Agent Skills name/length limits.** Inferred from `models/skill.py:9-19`; not run.
- **The trigger-eval numbers measure a keyword heuristic, not real activation.** No provider-level activation test exists in the repo that I found.
- **The Docusaurus build** (`npm run build` in `docusaurus/`) was not run.
- **The ag-ui fork's `upstream/main`** was not re-fetched, so "12 ahead" is against a local ref.
- **Inbox timestamps** are the DB's clock. I did not confirm the timezone.

## Open questions for the user

1. **#573 decision D4** (`design.md:151`) put a CAO agent-plugin authoring skill out of scope in favour of `migrate-agent-plugin`. Does `cao-agent-plugin-creator` supersede D4, or should the spec define it as complementary (create from scratch vs migrate)?
2. **Where should the dogfood package go?** Options: add the skills to `cao-contributor`, which conflicted with #1121's edit to the same block until #1121 merged as `00611d11`, or create a third `PackageConfig`. Also: should the two new skills join `SHIPPED_SKILLS` (the wheel) or stay plugin-only?
3. **The `cao-plugin` collision and M4.** Should the new skills' negative boundaries name `cao-plugin`, or should the spec assume the M4 rename to `cao-event-plugin`, which is still open?
4. **Which validator should the audit skill wrap?** Options: `cao plugin validate --json` (gated on `CAO_AGENT_PLUGINS_ENABLED`), a schema-based script bundled in the skill (pinned to the same `PIN.json` hashes), or a generalised harness-oss `validate-plugin.py` that takes a path argument? Each has a different dependency on the CAO install.
5. **Evals format.** Object shape or list shape? And should the spec require a fix to `run_trigger_evals.py` (crash on list shape, unused `httpx` dependency) or leave it alone?
6. **Blog authorship.** `plauzy` is not in `docusaurus/blog/authors.yml`, and the config throws on inline authors. Should the post add a `plauzy` entry, or use `cao-maintainers`?
7. **M1 wording.** `design.md:4` says M1 is decided and `docs/agent-plugins.md:82-88` says it is not. Which one should the spec and the blog follow?
8. **Can the blog cite #1121 while it is still open?** *(Moot since 2026-10-30: #1121 merged as `00611d11`.)*

Two pre-existing documentation defects in `docs/agent-plugins.md`, noted for oss-docs and not acted on: the severity table is split by the inserted MCP paragraph, so the `warning` and `info` rows sit orphaned at `:304-305` after the `fatal` and `skipped` rows at `:246-247`. The second defect noted here at `556726a4`, `build_agent_plugin.py` saying #448 is still open, was fixed by #1121 (`00611d11`, `:37-39`).
