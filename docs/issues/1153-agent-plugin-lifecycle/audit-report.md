# T6 audit report: `agent-plugin/cao-agent-plugin-lifecycle`, audited by a skill it carries

**Task:** `tasks.md` T6, wave 3. **Seat:** `oss-docs` (terminal `d35cdf54`). **Date:** 2026-11-01.
**Tree:** `HEAD` `fa2240ef1e1d11a4e1fda3c6c477bdb00a2fe5c8` (T5), on base `27311798`. This report and
`audit-raw.txt` are untracked, and T6 makes no commit.

**The claim this report supports, in its exact shape:** the `Dogfood_Package` is **audited by** a skill it
carries, `cao-agent-plugin-audit`. It is not produced by that skill. It is produced by
`scripts/build_agent_plugin.py` (Requirements 8.1, 8.10).

## Verdict

**Clean: 0 fatal, 0 skipped, 0 limit, 0 warning, 1 advisory. audit exit=0.** The one advisory is the
description/skills listing that Requirement 2.12 requires the audit to **emit**. It is not a defect,
and it makes no judgement about meaning. CAO's own manifest verdict agrees: `"loadable": true`,
`"findings": []`, validate exit=0. **No finding needs a T5 follow-up.**

## The command, verbatim

T6's published "Command that must pass" block was copied byte-for-byte from `tasks.md` and run with
`zsh`, after T6's start block printed `stamp taken: /tmp/cao-apl-t6.stamp` (exit 0). Its audit step is
this line:

```text
uv run --quiet --script skills/cao-agent-plugin-audit/scripts/validate_agent_plugin.py ./agent-plugin/cao-agent-plugin-lifecycle 2>&1 | tee docs/issues/1153-agent-plugin-lifecycle/audit-raw.txt
```

It gave **audit exit=0**. The block then ran
`CAO_AGENT_PLUGINS_ENABLED=1 uv run cao plugin validate ./agent-plugin/cao-agent-plugin-lifecycle --json`,
which gave **validate exit=0**. **The first run of the block exited 1**, at step 3, with
`missing from report: cao-agent-plugin-audit: package agent-plugin/cao-agent-plugin-lifecycle`. That
was intended. The report did not exist yet, because it is written only after the audit has run
(T6 defect 1). The block's final run is recorded in the callback.

## Captured output, quoted verbatim from `audit-raw.txt`

**Read this before the raw lines.** The line `cao plugin validate: not run` does **not** mean a check
was skipped. The block's audit step deliberately runs with `CAO_AGENT_PLUGINS_ENABLED` unset, so the
audit skill's own optional wrapper around `cao plugin validate` does not run. **CAO's verdict comes from
the block's step 2**, which sets the gate: `"loadable": true`, `"findings": []`, validate exit=0 (see
"Manifest verdict" below). The two checks are reported separately by design (OQ-4, option C).

```text
cao-agent-plugin-audit: package agent-plugin/cao-agent-plugin-lifecycle
schemas: bundled plugin.schema.json and mcp.schema.json hash to the pinned sha256
schemas: pin agrees with CAO's PIN.json at /Volumes/workplace/open-source/cao-agent-plugin-lifecycle/src/cli_agent_orchestrator/schemas/agent_plugins/1.0.0/PIN.json
mcp.json: absent (optional)
skill cao-agent-plugin-audit: name 22 chars, description 966 chars, body 232 lines
skill cao-agent-plugin-creator: name 24 chars, description 864 chars, body 325 lines
ADVISORY manifest.description_listing [plugin.json]: declared description: "Skills for the Agent Plugins 1.0.0 package lifecycle: author a new package from an empty directory (the plugin.json manifest, skills/ and an optional mcp.json), and audit an existing one against the vendored schemas and the Agent Skills limits that CAO's own validator does not check. The audit skill bundles a validator that needs no CAO install and no network."; discovered skills: cao-agent-plugin-audit, cao-agent-plugin-creator. Read them side by side; this audit makes no judgement about whether they correspond.
cao plugin validate: not run (CAO_AGENT_PLUGINS_ENABLED is not set to 1, true or yes)
summary: 0 fatal, 0 skipped, 0 limit, 0 warning, 1 advisory; exit 0
```

audit exit=0

The line `cao plugin validate: not run` is the audit skill reporting, correctly, that its optional CAO
wrapper did not run, because the gate is unset in the block's audit step. The CAO verdict is taken
separately in the block's step 2, below. The two checks are reported separately on purpose (OQ-4,
option C).

## The five mechanical checks

The validator reports the measured values. It raises a `LIMIT` finding for any breach, and this run
raised none. The table restates its numbers, and the pass/fail column was re-measured directly
against the package's two `SKILL.md` files, so it does not rest on the validator alone:

| Check | `cao-agent-plugin-audit` | `cao-agent-plugin-creator` |
|---|---|---|
| Name matches `[a-z0-9]+(-[a-z0-9]+)*` | pass | pass |
| Name ≤ 64 characters | pass (22) | pass (24) |
| Folder equals `name` | pass | pass |
| Description ≤ 1024 characters | pass (966) | pass (864) |
| Body ≤ 500 lines | pass (232) | pass (325) |

## Every finding, with its severity

| Severity | Code | Where | Meaning |
|---|---|---|---|
| advisory | `manifest.description_listing` | `plugin.json` | Lists the declared `description` beside the discovered skills (`cao-agent-plugin-audit`, `cao-agent-plugin-creator`) for a reader to compare. Required by Requirement 2.12. It is **advisory by design** and does not change the exit status, and the audit **claims no verdict** on whether the two correspond |

No fatal, skipped, limit or warning finding was raised. `mcp.json` is absent, which the schema allows;
this package ships skills only.

## Manifest verdict from `cao plugin validate --json`

**validate exit=0.** Key fields from `/tmp/manifest-verdict.json`: `"loadable": true`,
`"blocked_by_cao": false`, `"name": "cao-agent-plugin-lifecycle"`, `"version": "2.5.3"`, `"schema_id":
"https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"`, two skills (`cao-agent-plugin-audit`,
`cao-agent-plugin-creator`), `"mcp_present": false`, `"findings": []`. The version is the held pin,
2.5.3, as Requirement 8.13 requires.

## Evidence that the skill can fail

A clean audit of a package built from the skill's own sources shows little on its own (T6 defect 6),
so two runs are cited where the audit **does** fail:

- **T3** (`t3-overlimit-experiment.md`, `P-6`). `cao plugin validate` admits a skill with a
  2000-character description and a skill with a 600-line body: `"loadable": true`, `"findings": []`,
  exit 0. That is the gap the audit skill exists to close.
- **The audit skill on the same kind of fixture, run during this task** in a `mktemp -d` package that
  was deleted afterwards. It held one skill with a 2000-character description and one with a 600-line
  body. The validator printed `LIMIT    skill.description_length [zz-longdesc]: description is 2000
  characters; the limit is 1024` and `LIMIT    skill.body_length [zz-longbody]: body is 600 lines after
  the frontmatter; the limit is 500`, then `summary: 0 fatal, 0 skipped, 2 limit, 0 warning, 1 advisory;
  exit 1`, **exit 1**. `cao plugin validate` on that same fixture gave `loadable True findings []`,
  **exit 0**.

So the audit is a strict superset on these limits (property P2): it flags what CAO reports clean.

## Install smoke test

The real-pipeline install smoke test is `TestPackagesInstallThroughTheRealPipeline`, cited by the spec as
`test/agent_plugins/test_packages.py:309`. **At `fa2240ef` the class is at
`test/agent_plugins/test_packages.py:345`,** because T5 extended that file. This report introduces no
second smoke test.

## Fleet story

The account of how the fleet built this is `blog-outline.md`'s, and it is deferred with the post. This
report does not restate it.

## Outcome and lesson (`cao-learning`)

Recorded through CAO's own tools, not substitutes:

- **Outcome:** `report_outcome`. The row is identified by the id the tool returned. See the
  `outcome-id` line below.
- **Lesson:** `memory_store`, with `scope="agent"`, `memory_type="feedback"`, and text ending in
  `Applies when: …`. Conclusions only.

outcome-id: `d808da17-8833-4e4e-93a7-73dd2617b44b`. `report_outcome` returned this id with
`launch_linked: true`. `SELECT id, task_label, agent_profile, success, workflow_name FROM workflow_outcomes WHERE id = 'd808da17-8833-4e4e-93a7-73dd2617b44b'`
returned exactly one row: `d808da17-8833-4e4e-93a7-73dd2617b44b|T6 audit agent-plugin/cao-agent-plugin-lifecycle with its own cao-agent-plugin-audit skill|oss-docs|1|agent-plugin-lifecycle-spec`.
The row was found by its id, not by a count.

lesson-key: `pair-self-audit-with-failing-fixture`. It was created in agent scope for `oss-docs`, and
its text ends with "Applies when: dogfooding an audit or validator skill against the package that
ships it."

## Findings reported back, not fixed

None blocks T7, and none needs a change to a tracked file. Two are spec-side notes for the supervisor:

1. T6 cited the install smoke test at `test_packages.py:309`. It is at `:345` since T5. **Resolved in the
   spec between waves 4 and 5** (`P-77`): `tasks.md`, `design.md` and `P-63` now name both positions.
2. In the block's audit step, the gate is unset, so the skill's own `cao plugin validate` wrapper reports
   `not run`. The CAO verdict comes from step 2. **Now stated plainly** in T6's description ("How to read
   `audit-raw.txt`") and at the top of the captured-output section above.

## Gaps

This report does not cover a run with `CAO_AGENT_PLUGINS_ENABLED` set inside the audit step itself. It
also does not cover other installers or the network, and `PIN.json`-disagreement refusals were not
exercised here; `P-74` records them from reading the code.
