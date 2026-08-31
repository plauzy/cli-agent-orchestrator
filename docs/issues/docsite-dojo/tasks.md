# Tasks: a CAO Dojo on the docs site

**Requirements:** `./requirements.md` · **Design:** `./design.md`
**Not for upstream as-is.** Review on
[#584](https://github.com/awslabs/cli-agent-orchestrator/pull/584) asked for planning
artifacts to be dropped from `docs/issues/`, and a 374-line task plan was removed as a
result. This file lives here so it can be pushed and iterated on a fork branch —
CAO ignores `.kiro/`, `.claude/`, `.codex/` and `.agents/` wholesale (`.gitignore:56-59`,
zero tracked files), so an agent-tooling directory was not an option. **If this ships
upstream, drop this file and keep a trimmed `design.md`.**

Directory is slug-only because no tracking issue exists yet; rename to
`<issue-number>-docsite-dojo` to match `345-okf-export-import` and
`568-js-yaml-omap-dos` once one is filed.

---

## PR 1 — replay mode, static page, CI gate  *(no dependency on #584)*

- [ ] **1.1** Add frame capture to `examples/ag-ui/ag-ui-eventsource-viewer/tools/record-demo.mjs`
      — an `EventSource` listener writing NDJSON beside the existing GIF. Do not change
      the GIF behaviour; the job that produces it is green and gates today.
- [ ] **1.2** Record a synthetic demo run and capture `dojo-src/fixtures/fleet-run.ndjson`
      with a `_meta` header (`captured_at`, `cao_version`, `run_ids`, `truncated`).
      **Synthetic run only** — never a real work session (FR-7).
- [ ] **1.3** RED-first: write `test_dojo_fixture_is_metadata_only.py` asserting no
      `_BODY_FIELDS` key (`delta`, `content`, `message_body`, `stdout`) appears in the
      fixture, and that `_meta.captured_at` is present. Confirm it fails against a
      deliberately poisoned copy before it passes against the real one.
- [ ] **1.4** Split the viewer into `docusaurus/dojo-src/` parts (`_base.html`,
      `modules/10-transport.html` … `40-controls.html`, `_footer.html` — modules are
      **.html** fragments, matching how `course-src/build.sh` globs `modules/*.html`), preserving current
      rendering behaviour exactly.
- [ ] **1.5** Write `dojo-src/build.sh` mirroring `course-src/build.sh`; wire it into the
      existing `build-courses` prebuild chain in `docusaurus/package.json` (or a sibling
      `build-dojo` script invoked from the same hook).
- [ ] **1.6** Regenerate `examples/ag-ui/ag-ui-eventsource-viewer/index.html` from the
      same parts so there is exactly one renderer. Verify the recorder job still passes
      against the regenerated file — this is the step most likely to break CI.
- [ ] **1.7** Implement replay transport + scrubber; make replay the default mode with a
      visible "recorded" label (FR-3).
- [ ] **1.8** Implement the generic component dispatch (`RENDERERS` + `GENERIC_RENDERER`)
      and remove any hardcoded component-name list.
- [ ] **1.9** Add the FR-6 guard test: grep the **built** `static/dojo/index.html` for
      literal component names and fail if present.
- [ ] **1.10** Add the CI assertion that drives the built page over `file://` in replay
      mode and asserts each component in the fixture renders.
- [ ] **1.11** Write `docusaurus/docs/features/dojo.md` (FR-8) and add it to
      `sidebars.ts`.
- [ ] **1.12** Add the navbar entry, mirroring how `pathname:///course/index.html` is
      registered in `docusaurus.config.ts`.
- [ ] **1.13** Verify: `cd docusaurus && npm ci && npm run build` clean; page opens from
      `file://` with no server; `uv run python scripts/validate_markdown_links.py`
      passes (this bit #448 — every new `.md` is in scope).
- [ ] **1.14** Add `/static/dojo/` to `docusaurus/.gitignore` alongside the existing
      `/static/course/`, `/static/course-advanced/`, `/static/course-assets/` entries
      (lines 13-15). Without it every `npm start` dirties the working tree.

## PR 2 — live mode  *(no hard dependency, but better after PR 1 is merged)*

- [ ] **2.1** Implement `openLive()` against `http://localhost:9889/agui/v1/stream` with
      an editable endpoint field.
- [ ] **2.2** Implement the two distinct failure states — never-connected (with start
      instructions) vs disconnected-after-N-frames (FR-2).
- [ ] **2.3** Document the `CAO_AGUI_ENABLED` + scope-auth prerequisites on the docs
      page, and the CORS origin the reader may need.
- [ ] **2.4** Extend the CI assertion: boot a real server, switch to live mode, assert
      frames arrive. Reuses the pattern the existing recorder job already proves.

## PR 3 — demo agent plugin  *(gated on #584 merging)*

- [ ] **3.1** Package the demo fleet (profiles, skills, MCP wiring) as an Agent Plugin.
- [ ] **3.2** One-command path: install plugin → run → open the Dojo in live mode.
- [ ] **3.3** Document it as the plugin's first real consumer, which is a stronger
      argument for Agent Plugins than describing the feature.

## PR 4 — blog post  *(after PR 1 merges, so it links to something live)*

- [ ] **4.1** Register `plauzy` in `docusaurus/blog/authors.yml` — **the docs build
      fails without this** (`onInlineAuthors: 'throw'`).
- [ ] **4.2** Choose tags from `tutorial` / `deep-dive` / `orchestration-patterns` /
      `providers` / `mcp` / `case-study` / `community`, or add `ag-ui` with a
      justification in the PR description.
- [ ] **4.3** Write the post: what the surface is, the projection principle, the static
      constraint and why live-against-your-own-fleet beats a hosted demo, and what the
      recorder proves. Link to `docs/features/dojo.md` rather than restating it.
- [ ] **4.4** Include the honest limitation: `snapshot_fn` is called once per run, so the
      fixture advances one step per turn. Say so rather than editing the fixture to hide
      it.

## Sequencing and rationale

PR 1 is self-contained and carries the whole demonstrable value. PR 2 adds the
differentiator. PR 3 needs #584. PR 4 should land last so it links to a live page
instead of promising one.

The split is normative (FR-9), not stylistic:
[#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387) bundled a full stack
into one review and closed unmerged at +16,288 lines.

## Riskiest step

**1.6.** Regenerating the standalone example from the shared parts touches a file that
an existing green CI job depends on. If it breaks, the `AG-UI demo (shift-left
recording)` job goes red and the failure will look unrelated to a Dojo PR. Do 1.6 in
isolation, confirm the recorder job passes, and only then continue.

## Definition of done for PR 1

All eight acceptance criteria in `requirements.md` that do not mention live mode, plus:
CI green, `validate_markdown_links` clean, no committed build output, and exactly one
copy of the renderer in the tree.
