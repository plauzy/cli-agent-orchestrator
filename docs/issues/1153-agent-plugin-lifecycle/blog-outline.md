# Blog outline: the Agent Plugin lifecycle in CAO, gated by exit status

**Revision 3** (2026-10-29 ~17:45 -05:00) applies the binding attribution directive (`review-1.md:32`, "Attribution directive").
- The post names kiro-cli only in two measured forms: the Kiro co-author trailer figure, and the session in which the #1121 plan was written. It attributes no seat's work to any agent, kiro-cli included (B-4, round 9).
- Seats are named by role, never by provider.
- Authorship rests on the Kiro co-author trailers, recounted at `9d029f9d`, and is not widened to an "exclusively" claim.
- The rows, figures, appendix entries and §8 items that described other agents' work are withdrawn. Withdrawn rows keep their numbers so earlier cross-references don't silently shift.

**Naming rule:** every "plugin" is qualified as *Agent Plugin* or *CAO event plugin*. The lines that match `plugin` without matching `(Agent|agent|event)[ -]plugin|plugin\.json|\.claude-plugin` are all deliberate exceptions, listed in the NAMING-EXCEPTIONS line at the end of this file. **Attribution principle (ratified by `9feec10a`):** verbatim third-party artifacts are reproduced exactly, because altering them to satisfy a naming rule falsifies evidence. That covers PR titles, upstream descriptions and spec-mandated paths such as `.claude-plugin/`. Our own new prose names no foreign agent.

**Owner:** kiro-researcher (terminal `963e0c90`, session `cao-apl`)
**Date:** 2026-10-29 -05:00
**Status:** spec-phase outline. No post file exists yet, and none was written. Issue #1153 is blocked on D4.
**Source of facts:** [`research.md`](research.md), plus the re-checks listed in the Evidence appendix.
**Plans-folder citations:** files under `/Volumes/workplace/open-source/.agents/plans/pr1121/` are outside the repo. Where a file's *name* would attribute work to another agent, this outline cites it by role, for example "the #1121 audit report". The supervisor holds the exact filenames.

## Title options

1. **"Shift-left an Agent Plugin: every gate is a command with an exit status"** *(recommended)*. Promises a lifecycle a reader can rerun, gate by gate. For CAO users who ship skills or Agent Plugin packages.
2. **"From skill to Agent Plugin package: create, gate, audit, fix, learn, release"**. Promises a step-by-step lifecycle, closer to a tutorial. For contributors packaging skills for any Agent-Plugins client.
3. **"Replaying a maintainer's review through CAO: an Agent Plugin case study"**. Promises the #1121 review cycle told by role. For people evaluating multi-agent orchestration. It underplays the lifecycle.
4. **"Every claim has an exit status: shift-left testing for Agent Plugins in CAO"**. Promises the evidence discipline. For reviewers and maintainers. It reads abstract without the case study.

Revision 2's recommended title and option 3 are withdrawn under the attribution directive.

## Thesis

An Agent Plugin package can move through create, shift-left test, audit, fix, learn and release with a gate at every step, and every gate is a command a reader can run and check by exit status. In CAO, the Kiro co-author trailer is on 15 of plauzy's 18 commits on `main` at `9d029f9d` (2026-10-29), including the Agent Plugins support merged in #584. PR #1121's review cycle ran in CAO as separate worker and read-only reviewer seats, which this post describes by role only, and the PR is still open.

## Audience and prerequisites

- **Audience:** CAO users who author skills or Agent Plugin packages; contributors to `awslabs/cli-agent-orchestrator`; people evaluating multi-agent supervision in CAO.
- **Prerequisites the post must state:**
  - A CAO checkout and `uv`.
  - `cao-server` on `127.0.0.1:9889` for the ops-MCP parts.
  - **`CAO_AGENT_PLUGINS_ENABLED=1` exported before any `cao plugin` command.** The surface is default-off, and without the variable `cao plugin validate` exits 1 (research.md, gates table).
  - `CAO_AGUI_ENABLED=true` for the AG-UI section.
  - At least one CAO-supported provider CLI, installed and authenticated, for readers who want to reproduce the orchestration section.
- **Not assumed:** familiarity with the Agent Plugins spec. The post links it once and treats CAO's vendored schemas as the authority.

## Proposed front matter

```yaml
---
title: "Shift-left an Agent Plugin: every gate is a command with an exit status"
authors: [plauzy]
tags: [deep-dive, case-study]
description: "How an Agent Plugin package moves through create, shift-left test, audit, fix, learn and release in CAO, with the Kiro co-author trailer on 15 of the author's 18 commits on main at 9d029f9d, and an exit status behind every step."
---
```

- **Path:** `docusaurus/blog/<YYYY-MM-DD>-shift-left-agent-plugin/index.md`. The date is the publish date, which is not decided.
- **Truncation marker:** put the MDX form `{/* truncate */}` after the hook (row 0), before the first `##`. Existing posts use that form, for example `2026-10-12-cao-aidlc-orchestration/index.md:21`.
- **Build blocker:** `authors.yml` must gain a `plauzy` entry, appended after the `yinsong1986` entry (which starts at `authors.yml:99`), with `title` left blank per `authors.yml:36-41`. Otherwise `onInlineAuthors: 'throw'` (`docusaurus.config.ts:64`) fails the build. That entry is a separate one-file change.
- **Tag alternatives, recorded only:** `tutorial` (existing), or a new `agent-plugins` tag, which would need a `tags.yml` entry and is not proposed.

## Section plan

The "Figure" column refers to F1-F6 in the next section. Seats are described by role.

| # | Section | Claim it makes | Exact evidence it cites | Figure |
|---|---|---|---|---|
| 0 | Hook (2–4 paragraphs, before `{/* truncate */}`) | An Agent Plugin package change passed a maintainer's review only after the maintainer's own experiments were replayed by CAO worker seats, each step gated by an exit status. The hook names no agent for any seat and puts no kiro-cli mention next to the seats. | #1121 review `pr1121/review-5683175646.md:1` (2 × P2, 6 × P3); `pr1121/report-5-experiments.md:6` "E1 PASS … E5 PASS"; `pr1121/review-round1.md:202` `VERDICT: APPROVE`. #1121 is **open, not merged** (`gh api …/pulls/1121`, `state: open`, head `a64bbc76`) | none |
| 1 | Two things called "plugin" | Agent Plugins (an open spec of portable skill and MCP packages) and CAO event plugins (Python hooks in `cao-server`) are unrelated. The post is about the first. | `docs/agent-plugins.md:3-9`; `cli/commands/agent_plugin.py:146-147` | none |
| 2 | What an Agent Plugin package is | Only `plugin.json` with `$schema` and `name` is required. `skills/` and `mcp.json` are optional. Both schemas are closed. CAO validates against vendored bytes and never fetches a schema. | `plugin.schema.json:63,64`; `mcp.schema.json:19`; `PIN.json:6,7,13,18` (upstream commit `b78a4f16…`, sha256 `0a4aad95…` and `6539175b…`); `validation.py:74` | F1 |
| 3 | CAO ships itself as two Agent Plugin packages | `agent-plugin/cao` (operator: 4 skills plus the `cao-ops` MCP server pinned to `cli-agent-orchestrator==2.5.3`) and `agent-plugin/cao-contributor` (authoring skills, no MCP). Both are generated from `skills/` and committed. Merged in #584. | #584 merge `156cf1edcdb9de1ee01a2f17c2a4026e5f305e56`; `build_agent_plugin.py:4-12,107,145,170`; `agent-plugin/cao/mcp.json:4-12` | F1 |
| 4 | **Create** | A package skill is a copy of a canonical `skills/<name>/` directory, never a symlink. The build refuses an allowlisted skill that has no source. | `build_agent_plugin.py:641-649` (`BuildError`) and `:652-693` (copy, §4.1 rationale); `scripts/sync_skills.py:44-59` (`SHIPPED_SKILLS`) | none |
| 5 | **Shift-left test**: the gates | Each gate is one command with a known exit status, runnable offline | From research.md's gates table: `build_agent_plugin.py --check` → 0; `vendor_agent_plugins_schemas.py --check` → 0; `CAO_AGENT_PLUGINS_ENABLED=1 cao plugin validate ./agent-plugin/cao` → 0; the same command on `corpus/manifest-missing-name` → 1 (FATAL §5.2); the same command with the gate unset → 1; `sync_skills.py --check` → 0; `validate_skills.py skills/` → 0 (14/14); targeted pytest → 0 (169 passed). CI wiring: `ci.yml:88-89,94-95,100-101` | F2 (terminal capture) |
| 5a | A negative control is part of the gate | A gate that goes red on a known-bad input is what makes its green meaningful | `cao plugin validate …/manifest-missing-name` → exit 1, "FATAL §5.2 manifest.invalid". #1121 red-first P3-4: the mutation stayed green with `103 passed` before the fix (the test-and-build worker's report `:22-32`) and failed after it (`:104-112`) | F2 |
| 6 | **Audit** | Two layers: CAO's validator checks spec conformance, and the skill audit checks limits CAO's skill check does not enforce (name regex, 1024-char description, 500-line body) | `validation.py:685-705` → `utils/skills.py:66-69`, `models/skill.py:9-19` (non-blank fields, folder equals name); `$S/cao-skill-audit/SKILL.md:17-28` (rules 1-10); the #1121 audit report (read-only reviewer seat): scorecard `:5-16`, "Must fix in #1121: None" `:48-50`, 8 follow-ups `:52-66` | none |
| 6a | What the audit caught about its own brief | The audit corrected its brief's premise (the spec URL already appears in about ten places) and declined to substitute a missing input | the #1121 audit report `:28-38`, `:1`, `:75` | none |
| 7 | **Fix**: a maintainer review replayed | haofeif's findings were reproduced before they were fixed, then re-run as experiments E1-E5. A drift guard fired on a stale package copy. | P2-2 red: `pr1121/phase1-red.txt:1-12` ("CONTENT DIFFERS … cao-contributing/SKILL.md", `check-agent-plugin exit=2`). Gates: the regeneration-and-gates report `:145-159` (targeted set "1512 passed, 11 skipped"; P2-2 tests "5 passed"). `report-5-experiments.md:6`. Reviewer seat's first pass `CHANGES NEEDED` at `review-round1.md:134`, final `APPROVE` at `:202` | F3 |
| 7a | The pin is held on purpose | The packages pin 2.5.3 while `pyproject.toml` is at 2.5.4. The release job repins after publishing, and a contributor PR must not move the pin. | `docs/agent-plugins.md:11-23`; `--check` output "built at, 2.5.3 … pyproject.toml is now at 2.5.4" (exit 0); plan decision D4 at `../2026-10-29-pr1121-haofei-review.md:71`; `publish-to-pypi.yml:503,572` | none |
| 8 | *(withdrawn in revision 3 under the attribution directive)* | — | — | — |
| 8a | Second opinions are weighed, not obeyed | Each claim in a second-opinion review was marked verified or contradicted before use. One was contradicted by the maintainer's own experiment. | the #1121 second-opinion feedback file `:1-4,20-22` | none |
| 8b | Orchestration, by role | The plan and briefs split the work with disjoint file ownership. CAO delivered each brief to a worker or a read-only reviewer seat through the ops MCP server, and each seat returned its result as a report file ending in `DONE`. **No sentence in this section names, or lets a reader infer, which agent filled a seat.** The kiro-cli planning session is mentioned only in row 12's trailer context, if at all. | disjoint ownership in each brief's "You own ONLY" section (e.g. the test-and-build brief `:11-17`); inbox rows 269-273 and 282-283 with `sender_id='cao-ops-mcp'`; report files ending `DONE` (e.g. `report-5-experiments.md`, last line); plan provenance: `.kiro/logs/2026-10-29-10-09.md` (header "# Kiro Session Log"), for row 12 only | none |
| 9 | **Learn** | A durable lesson is re-checked before it is reused. The stored "14 of 17" trailer count was recounted, and the post uses the recount. The post must **not** claim `report_outcome` or a retrospector ran on #1121. Optional, labelled as a *different* run: this spec fleet recorded two outcomes on 2026-10-29. | Memory key `plauzy-kiro-coauthor-evidence` (2026-10-27: 14 of 17) vs the recount at `9d029f9d` (15 of 18; appendix). `cao-learning` contract: `$S/cao-learning/SKILL.md:15-17,25-45,72-85`. This fleet's rows: `SELECT substr(id,1,8), workflow_name, session_name, success, created_at FROM workflow_outcomes` (exit 0) → `9124f65c`, `821e3521`, workflow `agent-plugin-lifecycle-spec`, session `cao-apl`, `success=1` | none |
| 10 | **Release** | The release job regenerates the packages after the PyPI publish, refuses a pin whose ops server doesn't bound its HTTP requests, then checks strict equality | `publish-to-pypi.yml:503` (job), `:532` (`--require-bounded-client`), `:572` (`--check --require-current-pin`); `docs/agent-plugins.md:11-23,523-541` | none |
| 11 | AG-UI: what the operator sees | Agents can only emit six named components with JSON props, enforced server-side in three places | `services/agui_stream.py:91-100` (`GENERATIVE_UI_COMPONENTS`), `:104` (8 KiB cap), `:314` (RAW fallback); `api/main.py:2526-2533` (400); `services/agui/base.py:339-343` (`ValueError`); default-off gate `api/main.py:2132-2136`. PRs: #436 `a9af1595`, #485 `edf61cad`, #1107 `9fb5e1e4`, #1115 `720a3c40`, #1117 `e54e610d`, #1111 `2573bd17` | F5 |
| 12 | Authorship, measured | The Kiro co-author trailer is on 15 of plauzy's 18 commits on `main` at `9d029f9d` (2026-10-29). The post states what the figure assumes: it measures authorship only if a trailer appears where a Kiro session actually co-authored the commit. A trailer does not say which seat or agent produced each change in that commit. The post gives the recount command inline, re-runs it at the sha it publishes against (never inheriting 15-of-18 from this outline or the spec), and makes no "exclusively" claim and no rank claim. | Recount command, numbers, assumption and re-run rule in the appendix. 18 merged PRs, reconciled (`total_count` 18, page 2 empty). | F6 (optional) |
| 13 | What's next | The lifecycle skills (`cao-agent-plugin-creator`, `cao-agent-plugin-audit`) and a dogfood package are being specified, not built | Issue #1153 (sub-issue of #1154) and `docs/issues/1153-agent-plugin-lifecycle/`. Blocked on D4 (§8). | none |

**Totals:** 14 top-level rows (0-13; row 8 is withdrawn) plus sub-rows 5a, 6a, 7a, 8a and 8b. That is 18 live rows. **Rows with a figure requirement: 6** (rows 2, 3, 5, 5a, 7, 11). Row 12's F6 is optional and not counted.

## Figures and recordings needed

| ID | Format | What it must show | Supports |
|---|---|---|---|
| F1 | SVG | The package tree: `plugin.json` (required `$schema`, `name`), optional `skills/<name>/SKILL.md`, optional `mcp.json`. Also CAO's client-compatibility overlay (`.claude-plugin/plugin.json`, `.mcp.json`), labelled "CAO-generated, not required by the spec". Show `cao` and `cao-contributor` side by side. | rows 2, 3 |
| F2 | asciinema or terminal capture (text, not an image of text) | In order, with `echo $?` after each: `make check-agent-plugin` → 0; `export CAO_AGENT_PLUGINS_ENABLED=1`; `cao plugin validate ./agent-plugin/cao` → 0; `cao plugin validate ./test/agent_plugins/fixtures/corpus/manifest-missing-name` → 1, showing the FATAL line. The env var must be visible on screen. | rows 5, 5a |
| F3 | SVG | The lifecycle loop create → gate → audit → fix → learn → release. Label each arrow with the command whose exit status gates it (from row 5's list). Mark the reviewer seat's `CHANGES NEEDED` → `APPROVE` transition. | rows 4-10, mainly 7 |
| F4 | *(withdrawn in revision 3 under the attribution directive)* | — | — |
| F5 | SVG, or a screenshot of `examples/ag-ui/cao-dojo` | The six components, and where an off-list name is refused (400 at the producer, RAW in the stream). A screenshot needs a reproducible capture command and must sit next to the post. | row 11 |
| F6 (optional) | Code block, not a graphic | The recount command and its counted output at `9d029f9d` | row 12 |

Optional reuse: `docs/media/agent-plugins-dogfood-demo.gif` exists. It is produced only when the asserting script exits 0 (`docs/agent-plugins.md:669-707`; CI `ci.yml:509-559`). To use it, copy it next to the post rather than linking into `docs/`, because `onBrokenLinks: 'throw'` applies.

## Evidence appendix

Copied from `research.md` unless marked otherwise.

**Authorship: recounted 2026-10-29 at `upstream/main` = `9d029f9d4db16df2725bd04751756fd0b7d27440`.** This recount is new for revision 3. `git fetch upstream` exited 0, and `upstream/main` resolves to `9d029f9d` (`git rev-parse`).
- Command: `git log 9d029f9d --format='%an%x09%(trailers:key=Co-authored-by,valueonly)'`, exit 0. **What the figure establishes:** it counts trailers. It is evidence about authorship only under the assumption that a trailer appears where a Kiro session actually co-authored the commit. It does not identify which seat or agent produced any change within a trailered commit. **Re-run rule:** whoever writes the post re-runs this command at the sha they publish against, and must not inherit 15-of-18 from this document or the spec.
- Denominator: lines beginning `Pat Lauer<TAB>` = **18**. All 18 are `Pat Lauer <4451274+plauzy@users.noreply.github.com>`, which `git log 9d029f9d --format='%an <%ae>' | grep -c plauzy@` also counts as 18.
- Numerator: lines `Pat Lauer<TAB>Kiro Agent <244629292+kiro-agent@users.noreply.github.com>` = **15**. The other 3 lines carry no trailer.
- Lines mentioning Kiro anywhere in the output (case-insensitive) = **15**, so every Kiro-trailer commit on `main` is plauzy's.
- No Kiro trailer: `720a3c40` (#1115), `0214f238` (#332), `a4708eba` (#333).
- `Patrick` and `Patrick Liao` (`liao.patrick@gmail.com`) are a different person and are not counted.
- The numbers are unchanged from the count at `556726a4`, because the only commit between the two shas is `9d029f9d` (#1151), which is not plauzy's.
- **The post must carry the date and sha.** The count changes as `main` moves. No rank claim, no "exclusively".

**Merged PRs:** search `repo:awslabs/cli-agent-orchestrator is:pr is:merged author:plauzy`, `per_page=100`. Page 1 returned `total_count` 18 with 18 items, and page 2 returned 0 items. Both exit 0.

| PR | Merge sha | Area |
|---|---|---|
| #584 | `156cf1edcdb9de1ee01a2f17c2a4026e5f305e56` | Agent Plugins 1.0.0 |
| #436 | `a9af15953bd25980638311f44c97a5e7b43e1ed7` | AG-UI L1 |
| #485 | `edf61cad65a8183d37466f2d112d19a365cfca5c` | AG-UI L2 constructs |
| #1107 | `9fb5e1e4a8243a032a023718e9177e425230bec6` | AG-UI run plane |
| #1115 | `720a3c40f61ee826767ff37955b5ebba8a687b61` | AG-UI approvals |
| #1117 | `e54e610d5e5eb5efe8bd4dd30f4e7232bb467923` | AG-UI follow-ups |
| #1111 | `2573bd17f3dfda76e4101494b0212cc6de8b29a6` | CAO Dojo example |
| #448 | `5471d8f5dba94abfc267fb8037fc3e663a46e336` | cao-contributing skill |

**#1121 (open):** head `a64bbc7639c7c71b00c35c3093d3b81e8b2500e9`. Its six non-merge commits are by plauzy, and each carries a `Kiro Agent` trailer (`git log upstream/main..a64bbc76 --no-merges`). Read this, and `research.md:252` and `:281`, with the row 12 qualification: a trailer on a #1121 commit does not say which seat wrote which change, so these lines must not be combined into a claim about who wrote the skill text (B-4).

**Gates** (exit status observed 2026-10-29 at `556726a4`; not re-run at `9d029f9d`):
- `build_agent_plugin.py --check`: 0
- `vendor_agent_plugins_schemas.py --check`: 0
- `cao plugin validate ./agent-plugin/cao` with the env var: 0
- the same with `--json` on `cao-contributor`: 0
- the FATAL fixture: 1
- gate off: 1
- `sync_skills.py --check`: 0
- `validate_skills.py skills/`: 0 (14 passed)
- the packaged copies: 0 (6 passed)
- `validate_markdown_links.py`: 0
- targeted pytest: 0 (169 passed)

**Schemas:** `PIN.json:6` records upstream commit `b78a4f162d92c4b09ee205a11f59a6187926d947`. The sha256 values are `0a4aad95ce337878ad38802ebf0daa3fde76abe3f65400c86bcbb1ec0b3ab883` (`plugin.schema.json`) and `6539175bfcdf43085855183e86da40ea94b166547a72b47ae9a0a390516d3acb` (`mcp.schema.json`).

**harness-oss validator.** These are the only claims the post may make about it:
- Its vendored schemas are byte-identical to CAO's (`cmp` exit 0 for both).
- It validates the harness-oss package `revive-oss-pr` (exit 0, "13 passed").
- It hard-codes `ROOT` (`validate-plugin.py:25`) and reads no argv.

**AG-UI:** the allow-list is at `services/agui_stream.py:91-100`. It is enforced at `api/main.py:2526-2533`, `services/agui_stream.py:314` and `services/agui/base.py:339-343`, and listed in `mcp_server/server.py:1007`. The 8 KiB cap is at `agui_stream.py:104`.

**Gate surface:** `gate.py:31,36-42`; `api/main.py:3548,3617,3666,3711,3742`; `cli/commands/agent_plugin.py:142,153-158`; `web/src/featureFlags.ts:28`.

**Orchestration, role-only:**
- Inbox rows 269-273 and 282-283 have `sender_id='cao-ops-mcp'` (2026-10-29, DB clock).
- No supervisor terminal is recorded in the #1121 sessions (routed by `9feec10a`), so the post must not say a supervisor terminal dispatched the work.
- *Withdrawn in revision 3:* the `terminals` query and its four seat rows.

**Outcomes** (routed by `9feec10a`):
- Before this fleet's rounds, `SELECT COUNT(*) FROM workflow_outcomes;` returned **0** across every session, with `memory.learning_enabled: true`.
- It now returns **2** (`9124f65c`, `821e3521`; workflow `agent-plugin-lifecycle-spec`). I re-ran it and got exit 0. Those rows describe the spec fleet, not #1121.

**Checked for this outline** (re-checks, all exit 0):
- `publish-to-pypi.yml:503` is the `regenerate-agent-plugin:` job, `:532` passes `--require-bounded-client`, and `:572` runs `--check --require-current-pin`.
- `authors.yml:36-41` is the note on leaving `title` blank and not naming an employer. The `yinsong1986` entry starts at `:99`.
- All six existing posts use `{/* truncate */}`.

## Claims I could not evidence

1. **The skills this post's lifecycle is named for do not exist.** `cao-agent-plugin-creator`, `cao-agent-plugin-audit` and the dogfood package are spec-only, and #1153 is blocked on D4. The post can't show them being created, gated or released. Every lifecycle row is evidenced by the existing packages (#584) and #1121.
2. **D4 conflict.** `docs/issues/573-agent-plugins/design.md:151` puts a CAO agent-plugin authoring skill out of scope in favour of `migrate-agent-plugin`. Unless the maintainer revisits D4, row 13 describes something that was decided against. Flagged, not argued; oss-docs owns this.
3. *(Withdrawn in revision 3 under the attribution directive.)*
4. *(Withdrawn in revision 3 under the attribution directive.)* One part survives as a rule: no supervisor terminal is recorded in the #1121 sessions. The post may say "planned in a kiro-cli session" only in the authorship context of row 12, never next to a description of the seats, because that adjacency lets a reader infer who filled them (B-4). It may not say a supervisor terminal dispatched the work.
5. **The harness-oss validator never validated `agent-plugin/cao`.** The #1121 audit brief (`:15-16`) claims it did, and a later worker brief asks for the same run again. The post must not repeat either claim (`validate-plugin.py:25`, argv ignored).
6. **Skill activation.** `run_trigger_evals.py` is a keyword heuristic (`:232,295-307`), and it crashes on list-shaped evals (`:186`). The post can't claim that any skill "activates" or "triggers".
7. **Agent Plugins spec text.** I didn't read the spec prose; I only confirmed the site returns HTTP 200. Section numbers like §4.1 and §5.2 are CAO's own citations, so the post should attribute them ("CAO cites §5.2").
8. **Cross-client reach.** CAO documents the clients it exercises end to end (`docs/agent-plugins.md:50-54`). The post makes no "works in any client" claim, and it quotes that line verbatim if it uses it at all.
9. **#1121 outcome.** The PR is open, and the plan says "READY TO PUSH (awaiting the user's OK)" (`…review.md:278`). The post makes no "merged" or "shipped" claim. The full-suite figure (`:278-291`) is the plan's summary of shard logs I didn't read.
10. **The learn step did not run through `report_outcome` or a retrospector on #1121.** This is settled: the answer is no. Row 9 rests only on the memory note and the recount. The spec fleet's two outcome rows may illustrate a live learn step only if labelled as such.
11. **The reviewer seat's advisor.** The only record of what the advisor said is the reviewer seat's own account (`review-round1.md:119-128,198-200`).
12. **AG-UI screenshot (F5).** I didn't run `examples/ag-ui/cao-dojo`, so the screenshot has to be captured fresh.
13. **Docs-site build.** I didn't run `npm run build` in `docusaurus/`. The build will fail until `plauzy` is added to `authors.yml`.
14. **Orchestration rests on role-level evidence only.** With row 8 withdrawn, the post can describe briefs, disjoint file ownership, ops-MCP delivery and file-based results. It can't describe which agents filled the seats, and it must not imply they were all kiro-cli.

**Open question for the user:** does the maintainer revisit D4 before the post publishes? If not, rows 0 and 13 and the title must frame the new skills as a proposal.

NAMING-EXCEPTIONS (line numbers in this file):
- :36, :69: the CLI verb `cao plugin` and the env var `CAO_AGENT_PLUGINS_ENABLED`
- :67, :128, :129, :145, :149: file and script names (`build_agent_plugin.py`, `vendor_agent_plugins_schemas.py`, `validate-plugin.py`, `cli/commands/agent_plugin.py`)
- :140: the filename `plugin.schema.json`
- :9 and this list: the rule's own text
- :64: row 1's quoted bare word, which the line regex passes; it is deliberate because the section is about the word itself
