# Implementation Plan: a CAO Dojo on the docs site

**Requirements:** `./requirements.md` · **Design:** `./design.md`

Ported from `docs/issues/docsite-dojo/tasks.md` (removed; preserved at commit `b18eff6`),
whose four-PR split, sequencing rationale, riskiest-step callout, and definition of done are
preserved. Two of its tasks contradicted the design and are corrected here — see
**Corrections to the ported plan** below.

**Drop this file if the spec ships upstream, keeping a trimmed `design.md`.** Review on
https://github.com/awslabs/cli-agent-orchestrator/pull/584 asked for planning artifacts to
be removed from `docs/issues/`. This spec now lives under `.kiro/`, which CAO gitignores
wholesale (`.gitignore:56-59`) and which was force-added, so the `.kiro/` copy cannot ship
upstream as-is: an upstream pull request would place a trimmed `design.md` under
`docs/issues/<issue-number>-docsite-dojo/`, named for the tracking issue to match
`345-okf-export-import` and `568-js-yaml-omap-dos`. That numbering convention applies to
the upstream-facing copy only — this directory correctly uses the kebab-case feature name
`cao-docsite-dojo`.

## Overview

This plan delivers a CAO Dojo on the docs site: a single-file, `file://`-openable AG-UI page
that replays a recorded fleet run and, later, connects live to a local `cao-server`.

The work is split across four pull requests: **PR 1** — replay mode, the static page, and the
CI gate; **PR 2** — live mode; **PR 3** — the demo agent plugin; **PR 4** — the blog post.

**PR 1 is the immediate scope and depends on no unmerged pull request** (FR-9.3). PR 3 is
gated on https://github.com/awslabs/cli-agent-orchestrator/pull/584, and PR 4 lands last so
it links to a live page.

---

## Corrections to the ported plan

**1. "Preserving current rendering behaviour exactly" (old task 1.4) is wrong.** It would
preserve an FR-6 violation. `examples/ag-ui/ag-ui-eventsource-viewer/index.html:137` defines
a frozen `ALLOWED_COMPONENTS` map of the six allow-list names, and `addComponent()` (~line
340) gates dispatch on it — an off-list name takes `renderInertPlaceholder()` and renders a
structurally different view with **zero props fields**, failing FR-6.1 and FR-6.3. That map
is the hand-maintained client-side mirror of `GENERATIVE_UI_COMPONENTS` that FR-6 exists to
forbid. Removing it is behavioural work, not a refactor. Split into tasks **1.8** (mechanical,
reviewable as a no-op) and **1.9** (explicitly behaviour-changing). Keeping them separate
matters because the first is reviewable as a no-op and the second is not.

**2. No task existed for `applyPatch` atomicity.** `applyPatch(doc, ops)` at
`examples/ag-ui/ag-ui-eventsource-viewer/index.html:178` mutates the document in place and
returns mid-iteration, leaving it partially patched on a bad operation. CP-3 and Property 5
require atomicity. Task **1.12** adds the draft-and-commit rewrite the design specifies.

**3. The old FR-6 guard test (old task 1.9) is retired, not ported.** It grepped the built
page for literal component names — forbidding the `RENDERERS` map the design requires. FR-6.7
now prohibits lexical verification. Replaced by Properties 2-4 (tasks 1.22-1.24).

---

## Environment constraint — read before starting PR 1

Recording the fixture (tasks **1.6**, **1.7**) needs a running `cao-server` with
`CAO_AGUI_ENABLED`, Playwright's Chromium, and a gif-capable `ffmpeg`. **In a web sandbox, or
any environment without a full local CAO install, these tasks may be impossible.**

- Attempt them. If blocked, report exactly what was unavailable and continue against the
  fixture format as a defined interface — every other PR 1 task is executable without a
  recording.
- Any placeholder must be named `fleet-run.example.ndjson`, distinct from
  `fleet-run.ndjson`; carry `_meta.placeholder: true`; be marked as a placeholder inside the
  file; and **must not** satisfy FR-4 or land as the committed `Trace_Fixture` (FR-4.11,
  FR-4.12).
- **Never report the fixture work as done if it could not be recorded.**

---

## Tasks

### PR 1 — replay mode, static page, CI gate  *(depends on no unmerged pull request, FR-9.3)*

- [ ] 1.1 Add `/static/dojo/` to `docusaurus/.gitignore` in the build-output block
      alongside `/static/course/`, `/static/course-advanced/`, `/static/course-assets/` at
      lines 13-15. Without it every `npm start` dirties the working tree.
      - _Requirements: FR-1.5_

- [ ] 1.2 Add NDJSON frame capture to
      `examples/ag-ui/ag-ui-eventsource-viewer/tools/record-demo.mjs`: an `EventSource`
      listener on `/agui/v1/stream` writing one JSON object per line in arrival order, beside
      the existing GIF output. Capture failure must be **non-fatal** — report it, still
      produce the GIF unchanged in name and location, and exit with the status the recorder
      would return with capture absent. The GIF job is green and gates today.
      - _Requirements: FR-4.1, FR-4.2, FR-4.3_

- [ ] 1.3 RED-first: write `test/examples/test_dojo_fixture_is_metadata_only.py` with
      `hypothesis` (already a dev dep at `pyproject.toml:369`) — recursive traversal through
      objects and arrays to arbitrary depth asserting no `delta`, `content`, `message_body`, or
      `stdout` key occurs, reporting frame index and JSON path on detection, and generating
      poisoned fixtures with body fields injected at random paths and depths. **Confirm it
      fails against a deliberately poisoned copy before it passes against the real fixture** —
      a test that has never failed proves nothing. `@settings(max_examples=100)`, tagged
      `Feature: cao-docsite-dojo, Property 9: ...`.
      **Authored against the fixture format as documented in `design.md`** — NDJSON, one JSON
      object per line, line-1 `_meta` header — so no real recording is needed to write it. It is
      proven RED against synthetic and poisoned inputs here; the real fixture recorded in 1.7
      must then pass it.
      - **Property 9: Metadata-only invariance**
      - _Requirements: FR-7.1, FR-7.2, FR-7.3, CP-5_

- [ ] 1.4 Write `test/examples/test_dojo_fixture_prefix_validity.py` — for every
      line-boundary truncation point, including `_meta`-only and zero lines, the prefix is
      itself a valid `Trace_Fixture`. Single property test, ≥100 examples, tagged
      `Feature: cao-docsite-dojo, Property 8: ...`. Authored against the `design.md` fixture
      format and exercised over synthetic fixtures, then proven RED against inputs whose
      truncation points are deliberately invalid, before any real recording exists.
      - **Property 8: Fixture prefix validity**
      - _Requirements: NFR-2.1, CP-4_

- [ ] 1.5 Write `test/examples/test_dojo_fixture_provenance.py` — the validator accepts
      exactly the `_meta` headers satisfying FR-4 and rejects every other, naming the
      offending field: missing or non-`_meta` first record, unparseable or future
      `captured_at`, absent or unparseable `cao_version`, empty `run_ids`, a run id in a frame
      absent from `run_ids`, a `run_ids` value in no frame, and a `placeholder` that is absent,
      `true`, or non-boolean. A `cao_version` differing from the repository version is
      **accepted**, not rejected. Applied to both the committed fixture and the copy extracted
      from the built page. Tagged `Feature: cao-docsite-dojo, Property 7: ...`.
      Authored against the `_meta` contract documented in `design.md` and proven RED against
      synthetic headers with each field deliberately poisoned in turn, before any real fixture
      is recorded; the fixture recorded in 1.7 must then pass it.
      - **Property 7: Provenance validation completeness**
      - _Requirements: FR-4.5, FR-4.6, FR-4.7, FR-4.8, FR-4.9, FR-4.12_

- [ ] 1.6 Commit the synthetic demo scenario the recorder drives, executed solely for
      recording — never a maintainer or reader work session — and reference it from
      `record-demo.mjs`.
      - _Requirements: FR-4.10_

- [ ] 1.7 Record `docusaurus/dojo-src/fixtures/fleet-run.ndjson` from that scenario, with
      the line-1 `_meta` header carrying `captured_at`, `cao_version`, `run_ids`, `truncated`,
      and `placeholder: false`. Truncate at a run boundary if the run exceeds the reviewable
      size bound, setting `_meta.truncated: true`. The recording must pass the guard tests
      **1.3**, **1.4**, and **1.5** — already RED-proven — before it is committed. **Subject to
      the environment constraint above** — if recording is impossible, produce
      `fixtures/fleet-run.example.ndjson` with `_meta.placeholder: true` and leave this task
      open.
      - _Requirements: FR-4.5, FR-4.10, FR-4.11, NFR-2.1, NFR-2.2_

- [ ] 1.8 **Mechanical refactor, reviewable as a no-op.** Split
      `examples/ag-ui/ag-ui-eventsource-viewer/index.html` into `docusaurus/dojo-src/` parts:
      `_base.html`, `modules/10-transport.html`, `modules/20-state.html`,
      `modules/30-render.html`, `modules/40-controls.html`, `modules/90-seam.html`,
      `_footer.html`. Modules are **`.html`** fragments each carrying its own `<script>` block,
      because `course-src/build.sh` globs `"$SRC/$name"/modules/*.html`. Behaviour is preserved
      exactly in this task — including the `ALLOWED_COMPONENTS` gate, which task 1.9 removes.
      Move code, change none.
      - _Requirements: FR-1.2_

- [ ] 1.9 **Behaviour-changing.** Delete `ALLOWED_COMPONENTS` from
      `modules/30-render.html` and replace the gated branch with the design's unconditional
      path: `GENERIC_RENDERER(name, props)` always runs and produces the view; `RENDERERS` is
      consulted for an optional appearance-only refinement that decorates a view already
      created, never consulted as a condition. Zero props keys yields the named view with zero
      fields, not no view. Remove `renderInertPlaceholder`. No branch may produce zero views —
      that rules out a name list, a known-prefix test, a props-shape precondition, a `switch`
      without a `default`, and a `try`/`catch` that drops on error.
      **The PR description must justify this**: removing `ALLOWED_COMPONENTS` reads as
      weakening a security control, and it is not one — the gate never prevented injection,
      `textContent`-only insertion does, and Property 4 asserts it over hostile generated
      strings.
      - _Requirements: FR-6.1, FR-6.2, FR-6.3, FR-6.4, CP-2_

- [ ] 1.10 Add `normaliseForDisplay` to `modules/30-render.html`, affecting the label only
      and never reaching dispatch: empty or whitespace-only name → the fixed placeholder
      `(unnamed component)`; name longer than 512 characters → first 512 chars plus an
      ellipsis; non-string → `String(value)`. Props render unchanged in every case.
      - _Requirements: FR-6.5_

- [ ] 1.11 Audit and enforce text-never-markup across the refactored modules: every
      component name, props key, and scalar value enters the DOM through
      `document.createTextNode` or `node.textContent` only. Assert by inspection that the
      source contains no `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`,
      `eval`, or `new Function`, and no attribute whose value derives from frame content — no
      `href`, `src`, `style`, or `on*` sink. The existing `el()` helper already holds this
      line; the refactor must not relax it.
      - _Requirements: FR-6.6_

- [ ] 1.12 Rewrite state-delta application in `modules/20-state.html` as
      draft-and-commit: `applyDelta(state, ops)` clones via `structuredClone` with a JSON
      round-trip fallback, applies `add`/`remove`/`replace`/`move`/`copy`/`test` sequentially
      to the draft, and returns `{ok: false, state}` with the **prior state unchanged** on the
      first non-applicable operation — invalid path, missing `op`, type-mismatched value,
      failing `test` — otherwise `{ok: true, state: draft}`. Render a rejected-patch notice in
      the event log. No partially-mutated view is ever rendered. This replaces the in-place,
      mid-iteration-return `applyPatch` at `index.html:178`.
      - _Requirements: CP-3, Property 5_

- [ ] 1.13 Implement `openReplay(records, onFrame, opts)` in `modules/10-transport.html`
      taking an **already-parsed record array** — not a `fixtureUrl`, since browsers block
      `fetch` and XHR on `file://` origins. Returns `{stop()}`, delivers records in committed
      order, and paces them at the single `REPLAY_INTERVAL_MS` definition site (400 ms). Skip
      an unparseable line, log it with its index, and still deliver the remaining records.
      Replay is the default mode when the URL carries no recognised live-mode selector.
      - _Requirements: FR-3.1, FR-3.4, FR-3.9_

- [ ] 1.14 Implement the scrubber in `modules/40-controls.html`, positioning playback at
      any index in `[0, recordCount - 1]` by resetting to the empty projection and re-folding
      records `0..i` — a fold from the start, not a reverse patch, because RFC-6902 operations
      are not generally invertible.
      - _Requirements: FR-3.10_

- [ ] 1.15 Render the mode-dependent chrome in the **page shell** (`_base.html` +
      `modules/40-controls.html`), not in the Renderer: the "recorded run" label carrying
      `_meta.captured_at` and `_meta.cao_version`, the truncation notice when
      `_meta.truncated` is true, and the "no recorded events are available" message with the
      Transport selector left operable when the fixture has `_meta` but zero event records.
      **This is load-bearing for CP-1: if the Renderer can branch on mode, CP-1 fails by
      construction and replay stops being evidence about live mode.** The Renderer receives
      frames and nothing else — no mode argument, no `isReplay`, no transport handle.
      - _Requirements: FR-3.7, FR-3.8, NFR-2.2, CP-1_

- [ ] 1.16 Add the `window.__dojo` test seam in `modules/90-seam.html`, exposing one
      namespaced object holding references to existing internals only: `openReplay`,
      `openLive` (PR 2), `dispatch`, `applyDelta`, `reset`, and `REPLAY_INTERVAL_MS`. No
      query-flag gating — a flag the test must set is a mode the page can observe, which is
      the shape CP-1 forbids.
      - _Requirements: CP-1, CP-2, CP-3, FR-5.3_

- [ ] 1.17 Write `docusaurus/dojo-src/build.sh` mirroring `course-src/build.sh`:
      `set -euo pipefail`, `cat` of `_base.html` + `modules/*.html` in filename order +
      `_footer.html` into `static/dojo/index.html`. Add a `build-dojo` script to
      `docusaurus/package.json` and invoke it from the existing `prestart` and `prebuild`
      hooks that currently run `build-courses` (`bash course-src/build.sh`). **All CSS and JS
      inlined into the single output file** — no `dojo-assets/` directory, no relative asset
      paths, no webfonts, system font stacks only — because the course pages reference Google
      Fonts and `../course-assets/*` externally and are not `file://`-openable. `bash` and
      coreutils only; no compiler, bundler, or package install.
      - _Requirements: FR-1.1, FR-1.2, FR-1.3, FR-1.4, NFR-1.2, NFR-3.1_

- [ ] 1.18 Add fixture embedding and byte verification to `dojo-src/build.sh`. `_base.html`
      carries exactly one slot,
      `<script id="dojo-fixture" type="application/x-ndjson">@@DOJO_FIXTURE@@</script>` — an
      unrecognised script type is never executed. `sed` rewrites each occurrence of `</script`
      → `<\/script`, `<script` → `\u003cscript`, `<!--` → `\u003c!--`, `-->` → `--\u003e`,
      U+2028 → `\u2028`, U+2029 → `\u2029`; every substitution is legal inside a JSON string
      literal, so recovered field values are byte-identical after `JSON.parse`. After writing
      the output, extract the block back with `sed -n`, reverse the escaping, and `cmp -s`
      against `fixtures/fleet-run.ndjson`. On mismatch, on zero slots, or on more than one
      slot: exit non-zero with a named error and **publish nothing** — remove the output.
      - _Requirements: FR-3.2, FR-3.3, FR-3.5, FR-3.6, NFR-3.1_

- [ ] 1.19 **RISKIEST — do this in isolation, as an independently revertible commit.**
      Regenerate `examples/ag-ui/ag-ui-eventsource-viewer/index.html` from the same `dojo-src/`
      parts so exactly one Renderer exists in the tree. Then confirm the recorder still works
      end to end. The DOM ids and classes `record-demo.mjs` relies on are a **contract**:
      `#components`, `.gcard`, `.gtype`, `#components iframe`, and the "connected" status text
      (`record-demo.mjs:219,257,267,271`). See **Riskiest step** below.
      - _Requirements: FR-1.2_

- [ ] 1.20 Create `examples/ag-ui/ag-ui-eventsource-viewer/tools/dojo.spec.mjs` and a
      `test` script in that package's `package.json`, using the existing `@playwright/test`
      1.56.1 — no new devDependency, no test runner added to `docusaurus/`. Navigate to the
      **built** `static/dojo/index.html` over a `file://` URL, per FR-5.3 asserting build
      output rather than `dojo-src/`. Add the seeded generator inside the spec — `mulberry32`
      plus shape builders for the three frame shapes, the six RFC-6902 ops, and the degenerate
      names — with **the seed printed on failure**. Every property below is a single
      property-based test running ≥100 iterations, tagged
      `Feature: cao-docsite-dojo, Property {n}: {property text}`.
      - _Requirements: FR-5.1, FR-5.3, NFR-1.1_

- [ ] 1.21 Property 1, **structural half only**. Assert the Renderer receives no transport
      identity and that `openReplay` delivers the generated sequence in order for
      arbitrary-length sequences including the empty sequence, single-frame sequences, and
      sequences with repeated frames. The full two-transport equivalence lands in PR 2 with
      `openLive` — see **Notes**.
      - **Property 1: Transport-seam indistinguishability**
      - _Requirements: FR-3.4, CP-1_

- [ ] 1.22 Property 2 in `dojo.spec.mjs`. Generator domain: every member of
      `GENERATIVE_UI_COMPONENTS`; names absent from it; `""`; whitespace-only; 511-, 512- and
      513-character names; names with punctuation, non-ASCII, and HTML metacharacters;
      non-string values. Props: `{}`, flat scalar maps, arrays, objects nested to arbitrary
      depth. Assert exactly one visible view per frame, never a throw, never a drop, the name
      as text plus one labelled field per top-level props key, and structural identity between
      an off-list name and an on-list name with the same props and no refinement.
      - **Property 2: Dispatch totality and view fidelity**
      - _Requirements: FR-6.1, FR-6.2, FR-6.3, FR-6.5, FR-6.7, CP-2_

- [ ] 1.23 Property 3 in `dojo.spec.mjs` — the set of props values rendered is the same
      whether a refinement is registered or `RENDERERS` is empty.
      - **Property 3: Refinement invariance**
      - _Requirements: FR-6.4_

- [ ] 1.24 Property 4 in `dojo.spec.mjs` over hostile strings — nested tags, unterminated
      tags, attribute-escape attempts, `javascript:` values, entity- and percent-encoded
      variants, and the six sequences FR-3.2 escapes — used as component name, props key, and
      scalar value. Assert the string appears verbatim, element count is unchanged against a
      benign control of the same shape, no attribute originates from the string, and no script
      executes. This is the assertion that justifies removing `ALLOWED_COMPONENTS` in 1.9.
      - **Property 4: Frame content is text, never markup**
      - _Requirements: FR-6.6, FR-6.7_

- [ ] 1.25 Property 5 in `dojo.spec.mjs` — determinism across evaluations;
      order-dependence, so reordering non-commuting operations changes the result; atomicity,
      so a malformed or non-applicable patch leaves prior state exactly intact and renders no
      partially-mutated view; and scrubber fold equality, so seeking to index `i` equals a
      fresh fold over records `0..i`.
      - **Property 5: State application soundness**
      - _Requirements: FR-3.10, CP-3_

- [ ] 1.26 Property 6 in `dojo.spec.mjs` — for generated fixtures whose string values
      contain arbitrary interleavings of `</script`, `<script`, `<!--`, `-->`, U+2028 and
      U+2029, run `build.sh`, extract the single embedded block from the built page, reverse
      the escaping, and assert byte-for-byte equality with the committed fixture and
      byte-identical field values on every record delivered to the Renderer.
      - **Property 6: Fixture embedding round trip**
      - _Requirements: FR-3.2, FR-3.3, FR-3.5_

- [ ] 1.27 Add the FR-5 render gate and the recorder DOM contract to `dojo.spec.mjs`:
      one view per `GENERATIVE_UI` record in the embedded fixture, failing if any stops
      rendering; zero network requests after document load over `file://`; the default mode is
      replay; the recorded-run label, truncation notice, and `_meta`-only empty state render;
      `window.__dojo.REPLAY_INTERVAL_MS` matches the value documented in
      `docs/features/dojo.md`; and the `#components` / `.gcard` / `.gtype` selectors
      `record-demo.mjs` depends on are present.
      - _Requirements: FR-3.1, FR-3.7, FR-3.8, FR-3.9, FR-5.1, FR-5.2, NFR-1.1, NFR-2.2_

- [ ] 1.28 Wire the gates into `.github/workflows/ci.yml`. Add the `test/examples/`
      pytest selection and the Playwright spec run against the built page. Add build
      assertions: artifact present and non-empty with part markers in order;
      `git status --porcelain docusaurus/` empty after build (FR-1.5); no `src`/`href` pointing
      outside the built file, no `@import`, no webfont, the only `http` occurrence being the
      default endpoint *value* (NFR-1.2). Add a shell test that corrupts the embedded block and
      asserts `build.sh` exits non-zero and publishes nothing (FR-3.6); an FR-4.3 case where an
      unwritable capture path still produces the GIF with an unchanged exit status; the FR-4.13
      staleness warning for event types and component names observed in a recorder run but
      absent from the fixture; and an FR-9.1 diff check that PR 1 introduces no `openLive` and
      no `EventSource` under `dojo-src/`. **Introduce no lexical search of the built page for
      component names** — the retired grep must not reappear (FR-6.7).
      - _Requirements: FR-1.1, FR-1.5, FR-3.6, FR-4.3, FR-4.4, FR-4.13, FR-5.1, FR-6.7, FR-9.1, NFR-1.2_

- [ ] 1.29 Write `docusaurus/docs/features/dojo.md` and register it in
      `docusaurus/sidebars.ts` alongside `features/web-ui`. Document the `REPLAY_INTERVAL_MS`
      value (400 ms) and its single definition site, mark `window.__dojo` as **test-only and
      unstable**, state that `_meta.cao_version` drift is displayed rather than gated, and
      record that `ALLOWED_COMPONENTS` was removed because `textContent`-only insertion — not
      a name list — is what prevents injection.
      - _Requirements: FR-3.9, FR-8.1, FR-8.4_

- [ ] 1.30 Add the navbar entry for `pathname:///dojo/index.html` in
      `docusaurus/docusaurus.config.ts`, mirroring how `pathname:///course/index.html` is
      registered at lines 103 and 131.
      - _Requirements: FR-8.3_

- [ ] 1.31 Verify PR 1: `cd docusaurus && npm ci && npm run build`;
      `static/dojo/index.html` present and non-empty; the page opens and renders from a
      `file://` URL with no server and no network; `uv run python
      scripts/validate_markdown_links.py` passes (this gate broke
      https://github.com/awslabs/cli-agent-orchestrator/pull/448 — every new `.md` is in
      scope); `uv run black --check` and `uv run isort --check-only` pass on the new Python;
      the `test/examples/` pytest selection passes; the Playwright spec passes; and
      `git status --porcelain docusaurus/` is empty, proving the build output is ignored.
      - _Requirements: FR-1.1, FR-1.5, FR-8.4, NFR-1.1_

- [ ] 1.32 Checkpoint — ensure all tests pass, ask the user if questions arise.

### PR 2 — live mode  *(no hard dependency, but better after PR 1 merges)*

- [ ] 2.1 Implement `openLive(endpoint, onFrame, onError)` in `modules/10-transport.html`
      against `http://localhost:9889/agui/v1/stream`, with an editable endpoint field used for
      subsequent connections. Browser-side `EventSource` only; no server-side fetch.
      - _Requirements: FR-2.1, FR-2.2, FR-2.5_

- [ ] 2.2 Implement the two distinct failure states in the page shell — `never-connected`
      (zero frames: "no CAO server was reachable at `<endpoint>`" plus start instructions) and
      `disconnected` (after N frames: "disconnected after N frames" plus a retry control). An
      empty view resembling a working fleet with no activity is prohibited.
      - _Requirements: FR-2.3, FR-2.4_

- [ ] 2.3 Document the `CAO_AGUI_ENABLED` and scope-auth prerequisites and the CORS origin
      the reader may need, in `docusaurus/docs/features/dojo.md`.
      - _Requirements: FR-2.1, FR-8.1_

- [ ] 2.4 Complete Property 1 in `dojo.spec.mjs`: drive the same generated sequence through
      `openReplay` and `openLive` inside one page and assert identical final rendered state and
      identical delivery order. This closes the PR 1 limitation named in **Notes**.
      - **Property 1: Transport-seam indistinguishability**
      - _Requirements: CP-1_

- [ ] 2.5 Extend CI: boot a real server, switch to live mode, assert frames arrive, and
      intercept requests to confirm only the `EventSource` connection is made. Reuses the
      pattern the existing recorder job already proves.
      - _Requirements: FR-2.5, FR-9.2_

### PR 3 — demo agent plugin  *(gated on https://github.com/awslabs/cli-agent-orchestrator/pull/584 merging)*

- [ ] 3.1 Package the demo fleet — profiles, skills, MCP wiring — as an Agent Plugin.
      - _Requirements: FR-4.10_

- [ ] 3.2 Implement the one-command path: install plugin → run → open the Dojo in live
      mode.
      - _Requirements: FR-2.1_

- [ ] 3.3 Document it as the plugin system's first real consumer, which is a stronger
      argument for Agent Plugins than describing the feature.
      - _Requirements: FR-8.1_

### PR 4 — blog post  *(after PR 1 merges, so it links to something live)*

- [ ] 4.1 Register `plauzy` in `docusaurus/blog/authors.yml` — **the docs build fails
      without this** (`onInlineAuthors: 'throw'`; registered today: `cao-maintainers`,
      `haofeif`, `fanhongy`, `anilkmr-a2z`, `gutosantos82`, `sujoydc`, `guojing1217`).
      - _Requirements: FR-10.1, FR-10.4_

- [ ] 4.2 Use only tags defined in `docusaurus/blog/tags.yml` — `tutorial`, `deep-dive`,
      `orchestration-patterns`, `providers`, `mcp`, `case-study`, `community` — or add `ag-ui`
      in the same PR with a justification in the PR description.
      - _Requirements: FR-10.2, FR-10.3_

- [ ] 4.3 Write the post: what the AG-UI surface is, the projection principle, the static
      and fork-gated deploy constraint and why live-against-your-own-fleet beats a hosted
      demo, and what the recorder proves. Link to `docs/features/dojo.md` rather than
      restating it.
      - _Requirements: FR-8.2_

- [ ] 4.4 Include the honest limitation in the post: `run_plane_stream` calls
      `snapshot_fn` once per run, so the fixture advances one step per turn. Say so rather
      than editing the fixture to hide it.
      - _Requirements: FR-8.2_

- [ ] 4.5 Final checkpoint — ensure all tests pass, ask the user if questions arise.

---

## Sequencing and rationale

PR 1 is self-contained and carries the whole demonstrable value. PR 2 adds the
differentiator. PR 3 needs https://github.com/awslabs/cli-agent-orchestrator/pull/584. PR 4
lands last so it links to a live page instead of promising one.

Within PR 1: `.gitignore` first so nothing dirties the tree; recorder capture (1.2) next, so
the fixture format the tests target is implemented; then the RED-first file properties
(**1.3-1.5**) **before** the synthetic scenario (1.6) and the recording (1.7), because they
gate what a recording is allowed to contain — a guard written after the artifact it guards
cannot prevent the mistake it exists to prevent (FR-7). The tests are authored against the
format documented in `design.md`, so they need no real recording; they are proven RED against
synthetic and poisoned inputs, and the recorded fixture must then pass them before it is
committed. Then the mechanical refactor (1.8) strictly before the
behavioural change (1.9); `build.sh` concatenation (1.17) before embedding (1.18), because
embedding verification needs an output to verify; the risky regeneration (1.19) alone; then
the browser properties against the built artifact; then CI, docs, and verification.

**The split is normative (FR-9), not stylistic.**
https://github.com/awslabs/cli-agent-orchestrator/pull/387 bundled a full stack into one
review and closed unmerged at +16,288 lines. PR 1 must depend on no unmerged pull request
(FR-9.3).

## Riskiest step

**1.19.** Regenerating `examples/ag-ui/ag-ui-eventsource-viewer/index.html` from shared parts
modifies a file the currently-green `AG-UI demo (shift-left recording)` CI job depends on
(`.github/workflows/ci.yml:259`) — `record-demo.mjs` navigates to that page, waits for the
"connected" text, locates `#components .gcard .gtype`, counts `#components .gcard` and
`#components iframe`, and screenshots the result. **If it breaks, the failure will look
unrelated to a docs PR.**

Do 1.19 in isolation. Confirm the recorder still works before continuing. Treat the DOM ids
and classes above as a contract, asserted by the same spec that carries the FR-5 gate (1.27).
Land it as an **independently revertible commit** so a red recorder job can be backed out
without unwinding the rest of PR 1.

## Notes

- **CP-1 is only half-assertable in PR 1.** Until `openLive` exists in PR 2, task 1.21
  asserts the structural half — the Renderer receives no transport identity and `openReplay`
  delivers in order. This is a **named limitation, not a silent gap**, and it is the price of
  FR-9; the seam is transport-agnostic by construction from PR 1 rather than retrofitted.
- **CI's `-m "not e2e"` overrides local pytest `addopts`**
  (`-m 'not e2e and not integration'`, `pyproject.toml:404`), so integration tests run in CI
  but may be deselected locally. A green local run can hide a red CI — **compare deselected
  counts, not just pass counts.**
- If `git commit` fails with a husky or `core.hooksPath` error, run the quality gates manually
  (`black`, `isort`, the pytest selection) then `git commit --no-verify`, **and say so** in
  the commit or PR description.
- Conventional Commits for subject lines.
- Tasks marked with `*` would be optional; none are — every task here implements a
  requirement or a stated correctness property.

## Definition of done for PR 1

Release-gate criteria 1, 3, 4, 5, 6, 7, and 8 from `requirements.md` — every criterion that
does not mention live mode — plus: CI green; `validate_markdown_links.py` clean; no committed
build output (`git status --porcelain docusaurus/` empty after a build); exactly one copy of
the Renderer in the tree; Properties 2-9 passing and Property 1 passing in its structural
half; the guard tests **1.3-1.5** written and proven RED before the recording task **1.7** ran;
and the fixture either recorded from a committed synthetic run with
`_meta.placeholder: false`, or **explicitly reported as not done** with the unavailable
prerequisites named.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.8"] },
    { "id": 1, "tasks": ["1.3", "1.9", "1.12", "1.13", "1.16"] },
    { "id": 2, "tasks": ["1.4", "1.10", "1.14", "1.17"] },
    { "id": 3, "tasks": ["1.5", "1.11", "1.15"] },
    { "id": 4, "tasks": ["1.6", "1.18"] },
    { "id": 5, "tasks": ["1.7"] },
    { "id": 6, "tasks": ["1.19"] },
    { "id": 7, "tasks": ["1.20"] },
    { "id": 8, "tasks": ["1.21"] },
    { "id": 9, "tasks": ["1.22"] },
    { "id": 10, "tasks": ["1.23", "1.29"] },
    { "id": 11, "tasks": ["1.24", "1.30"] },
    { "id": 12, "tasks": ["1.25"] },
    { "id": 13, "tasks": ["1.26"] },
    { "id": 14, "tasks": ["1.27"] },
    { "id": 15, "tasks": ["1.28"] },
    { "id": 16, "tasks": ["1.31"] },
    { "id": 17, "tasks": ["2.1", "2.2", "2.3"] },
    { "id": 18, "tasks": ["2.4", "2.5"] },
    { "id": 19, "tasks": ["3.1"] },
    { "id": 20, "tasks": ["3.2", "3.3"] },
    { "id": 21, "tasks": ["4.1", "4.2"] },
    { "id": 22, "tasks": ["4.3"] },
    { "id": 23, "tasks": ["4.4"] }
  ]
}
```
