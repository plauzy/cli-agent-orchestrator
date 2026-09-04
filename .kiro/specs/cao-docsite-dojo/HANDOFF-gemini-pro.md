# Handoff — spec hardening pass, Gemini Pro

**How to use:** clone `https://github.com/plauzy/cli-agent-orchestrator`, check out
`spec/docsite-dojo-gemini-pro-review` — your own review branch — then paste everything
below the `---` into Gemini Pro. Commit your findings and edits to that branch. The
shared baseline both reviews are cut from is `spec/docsite-dojo`; diff against it to see exactly
what you changed. If your session cannot read the repo directly, attach the three files from
`.kiro/specs/cao-docsite-dojo/` (`requirements.md`, `design.md`, `tasks.md`) plus
`examples/ag-ui/ag-ui-eventsource-viewer/index.html` and
`docusaurus/course-src/build.sh` — those two source files are what the spec's factual
claims rest on.

**Why a second provider:** this is the B side of an A/B. The body below is deliberately
near-identical to `HANDOFF-claude-fable.md` so the two outputs can be diffed and the
difference attributed to the model rather than to the prompt. **Do not edit one without
the other** — divergent prompts would make the comparison measure prompt authorship
instead of model judgment.

**Reading the results:** agreement between the two runs on a defect raises confidence;
disagreement is the interesting signal and should be adjudicated on the argument, not by
majority. A defect found by only one run is not thereby weaker.

**Where this run has an edge:** Gemini Pro arrives with no history of authoring these
documents and no exposure to the reasoning that produced them. Several of the decisions
below were argued at length in a prior session; an independent reader is better placed to
notice where that argument was self-serving.

---

You are doing a **spec hardening pass**. Do not implement the feature. Do not write
production code. The deliverable is a written critique plus, optionally, surgical spec
edits.

## Where the spec is

`.kiro/specs/cao-docsite-dojo/` on the review branch named in the preamble:

- `requirements.md` — FR-1..FR-10, NFR-1..NFR-3, CP-1..CP-5, EARS acceptance criteria
- `design.md` — architecture, transport seam, Properties 1-9, alternatives, risks
- `tasks.md` — 4 PRs, 45 tasks, 32 in PR 1

Read all three before writing anything. They are mutually dependent; a change to one
usually implies a change to another.

**`.kiro/` is gitignored in this repo** (`.gitignore:56-59`, no other tracked files under
it). These files are tracked only because they were force-added. Any edit needs
`git add -f` or it will silently fail to stage. This will bite you.

## What the feature is

A static, zero-dependency interactive "Dojo" page on CAO's Docusaurus docs site rendering
the AG-UI event stream in **replay** mode (default, from a trace fixture embedded at build
time) and **live** mode (from the reader's own `cao-server` at
`localhost:9889/agui/v1/stream`).

It exists to make an existing claim runnable: that a stock AG-UI client renders a live
multi-agent CAO run with zero CAO-specific client code. Today that claim is demonstrated
only by a CI job that exports a GIF.

The Dojo is a pure **consumer** of the stream contract. It adds no route, imports no CAO
Python, and cannot change what the surface emits. The only new Python is test code.

## Facts already verified against this tree — do not re-derive

| Fact | Evidence |
|---|---|
| Build pattern to mirror | `docusaurus/course-src/build.sh` concatenates `_base.html` + `modules/*.html` (globbed, line 24) + `_footer.html` into `static/` |
| Modules are `.html`, not `.js` | that glob; each fragment carries its own `<script>` block |
| Build output gitignored, pattern established | `docusaurus/.gitignore:13-15` lists the three course outputs; `/static/dojo/` must join it |
| The renderer to reuse | `examples/ag-ui/ag-ui-eventsource-viewer/index.html`, 499 lines, zero deps |
| The recorder does **not** persist SSE frames | `tools/record-demo.mjs` pipes Playwright screenshots to ffmpeg; frame capture is new work |
| Allow-list source of truth | `GENERATIVE_UI_COMPONENTS`, enforced at `services/agui/base.py:339` |
| Body fields the surface strips | `_BODY_FIELDS = frozenset({"delta","content","message_body","stdout"})`, `base.py:28` |
| PBT deps already present | `hypothesis>=6.0` at `pyproject.toml:369`; `@playwright/test` 1.56.1 in the viewer's `tools/` |
| `docusaurus/` has **no** test runner | devDeps are five Docusaurus/TS packages only |
| Course pages are **not** `file://`-openable | they reference Google Fonts and `../course-assets/*` externally |
| Blog author gate is real | `onInlineAuthors: 'throw'`; `plauzy` is not in `blog/authors.yml` |

## Four defects already found — do not re-report, do not regress

1. **FR-6's original verification was a grep** for hardcoded component names, which
   contradicted the design's own `RENDERERS` map (whose keys *are* component names).
   Restated behaviourally: no name list may *gate* rendering; refinements keyed by name
   affect appearance only. The grep is retired.
2. **Replay originally `fetch()`ed the fixture**, which cannot work — browsers block
   `fetch`/XHR on `file://` origins. The fixture is now embedded at build time.
3. **The existing viewer already violates FR-6.** `ALLOWED_COMPONENTS`
   (`index.html:137`) gates dispatch at ~line 340 and renders off-list names with zero
   props fields. Removing it is behavioural work, split across tasks 1.8 and 1.9.
4. **Guard tests were ordered after the fixture they guard.** Now 1.3-1.5 precede 1.6-1.7.

## Attack these five decisions specifically

These are load-bearing, they were authored rather than derived, and they are the most
likely to be wrong. For each: defend it with an argument the spec does not already make,
or propose a concrete replacement.

1. **`window.__dojo`** (`design.md`, the test seam). The page exposes a namespaced global
   so Playwright can drive the transport, dispatch, and state applier on the *built*
   artifact. It is an ambient API on a public docs page. It is also the only thing that
   makes CP-1 checkable. If you would remove it, say what replaces CP-1's verification —
   "test through the DOM" was considered and rejected because CP-1 needs both transports
   driven over one generated sequence inside one page.

2. **`REPLAY_INTERVAL_MS = 400`** (task 1.13). Invented, not derived. Is a fixed interval
   even right, or should the fixture carry relative timings? Constraint: frames have no
   wall-clock deltas, and fabricating them would be a performance claim the recording
   cannot support.

3. **Replay as the default mode** (FR-3). Justified because most readers arrive without
   CAO running and a page that opens broken teaches nothing. The counter-argument is that
   it makes the *weaker* demonstration the front door.

4. **The NFR-3 adjudication** (`design.md`). `build.sh` gains `sed` and `cmp`, and this was
   ruled inside "concatenation and copying only". Is byte-verification really a
   build-script concern, or does it belong in CI where the other fixture validations live?

5. **CP-1 is only half-assertable in PR 1.** Transport-seam indistinguishability needs
   `openLive`, which is PR 2 — so PR 1 ships the property that justifies the whole
   approach in partial form. Acceptable, or does it argue for merging PR 1 and PR 2
   despite FR-9?

## Also look for, without being limited to

- Acceptance criteria that are not falsifiable, or that no named test reaches.
- Requirements that contradict each other, or that the design silently violates.
- Correctness properties whose generator domain does not cover the criterion they claim to
  validate. Nine properties claim to cover 13 requirements — check the mapping table in
  `design.md` rather than trusting it.
- Tasks whose dependency-graph wave ordering contradicts their stated prerequisites.
- Anywhere the spec asserts a codebase fact. Verify it. Several were wrong before.

## Constraints on your proposals

- **Do not expand `GENERATIVE_UI_COMPONENTS`.** Owned by
  https://github.com/awslabs/cli-agent-orchestrator/issues/582.
- **Do not propose hosting a live CAO instance.** `cao-server` is an unauthenticated
  command-execution surface; ruled out, not deferred.
- **Do not propose changes under `src/cli_agent_orchestrator/services/agui/`.** The Dojo
  consumes that contract. New test files are the only exception.
- **Do not collapse the PR split** without arguing against FR-9 explicitly.
  https://github.com/awslabs/cli-agent-orchestrator/pull/387 bundled a full stack and
  closed unmerged at +16,288 lines.
- **Do not push, open a PR, or comment on GitHub.** Commit locally if you edit, and report.

## Output contract — follow exactly, so the run is comparable

1. **Verdict table.** One row per FR/NFR/CP: `sound` / `weak` / `broken`, one-line reason.
   18 rows.
2. **Defects**, ordered by severity. For each: document and line, why it is wrong, the
   concrete fix. Distinguish *contradiction* (two statements cannot both hold) from *gap*
   (unspecified) from *unfalsifiable* (stated but not checkable).
3. **The five decisions**, one paragraph each: defend or replace.
4. **What you would cut.** The spec is 1,930 lines for a static page. Name what earns its
   length and what does not.
5. **Confidence**, and what you could not verify and why.

If you edit the spec documents, keep edits minimal and surgical, preserve FR/NFR/CP
numbering, and list every file and line touched. Remember `git add -f`.

## Environment notes

Recording the trace fixture (tasks 1.6-1.7) needs a running `cao-server` with
`CAO_AGUI_ENABLED`, Playwright's Chromium, and `ffmpeg`. If you lack those, say so plainly
and treat the fixture format as a defined interface. **Never report fixture work as done
if it was not recorded.** A placeholder must be named `fleet-run.example.ndjson`, carry
`_meta.placeholder: true`, and must not satisfy FR-4.

CI's `-m "not e2e"` overrides local pytest `addopts`, so integration tests run in CI but
may be deselected locally. Compare deselected counts, not just pass counts.

If `git commit` fails with a husky or `core.hooksPath` error, run the gates manually, then
`git commit --no-verify`, and say that you did.
