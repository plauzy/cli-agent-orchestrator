# Requirements: a CAO Dojo on the docs site — runnable proof of the AG-UI surface

**Related:** [#519](https://github.com/awslabs/cli-agent-orchestrator/issues/519) ·
[#436](https://github.com/awslabs/cli-agent-orchestrator/pull/436) (merged) ·
[#485](https://github.com/awslabs/cli-agent-orchestrator/pull/485) (merged) ·
[ag-ui#2216](https://github.com/ag-ui-protocol/ag-ui/pull/2216)
**Scope:** `docs` + `examples` — a static interactive page, a trace fixture, and a CI
assertion. No change to the AG-UI service, the stream contract, or the allow-list.
**Status:** Specified, not implemented.

---

## Context

CAO's AG-UI surface shipped in [#436](https://github.com/awslabs/cli-agent-orchestrator/pull/436)
(L1) and [#485](https://github.com/awslabs/cli-agent-orchestrator/pull/485) (L2). The
claim it makes is that *a stock AG-UI client renders a live multi-agent CAO run with
zero CAO-specific client code.* Today that claim is demonstrated by a CI job that
produces a GIF, and by a zero-dependency viewer a reader must find in
`examples/`, read, and run themselves.

The [AG-UI Dojo](https://dojo.ag-ui.com/) solves the equivalent problem for every
other framework by hosting live example servers a reader can click. CAO has no such
surface, and [ag-ui#2216](https://github.com/ag-ui-protocol/ag-ui/pull/2216) — which
would put CAO *in* the Dojo — is open pending maintainer review that we do not
control.

This spec covers a Dojo-equivalent **on CAO's own docs site**, which we do control.

## Provenance

Every mechanism below already exists in the repository. This is assembly, not
invention, and the requirements are written to keep it that way:

| Existing thing | Location | Why it matters here |
|---|---|---|
| Interactive standalone HTML build pipeline | `docusaurus/course-src/build.sh`, wired via `prebuild`/`prestart` in `docusaurus/package.json` | The pattern to follow. Concatenates `_base.html` + modules + `_footer.html` into `static/`, linked as `pathname:///course/index.html` |
| Zero-dependency AG-UI viewer | `examples/ag-ui/ag-ui-eventsource-viewer/index.html`, 499 lines, no build step | The renderer. Already consumes `/agui/v1/stream` via `EventSource` |
| Shift-left recorder | `examples/ag-ui/ag-ui-eventsource-viewer/tools/record-demo.mjs` (Playwright + ffmpeg), CI job `AG-UI demo (shift-left recording)` | Already boots a live server and drives the viewer on every commit |
| Governed blog | `docusaurus/blog/` with `authors.yml` / `tags.yml` | Where the narrative ships |
| Allow-list source of truth | `GENERATIVE_UI_COMPONENTS`, enforced at `services/agui/base.py:339` | What the Dojo must not be able to widen |

## The hard constraint someone must internalise

**GitHub Pages is static, and the docs deploy is fork-gated.** The AG-UI Dojo hosts
live agent backends; `.github/workflows/gh-pages.yml` publishes a static Docusaurus
build, only from `awslabs/cli-agent-orchestrator` (or a fork that sets
`DEPLOY_DOCS_PAGES=true`), and only on `main`.

There is therefore **no server** to stream from on the published site. Any design that
assumes a hosted CAO instance is wrong. The two viable sources are the reader's own
`localhost:9889`, and a fixture committed to the repository — which is why FR-2 and
FR-3 exist as separate requirements rather than one.

A second, quieter constraint: the recorder captures **pixels**, not frames.
`record-demo.mjs` drives Playwright and pipes screenshots to ffmpeg; it never
persists the SSE payloads. Replay mode cannot reuse its output and needs frame
capture added (FR-4).

## Functional requirements

### FR-1 — Build as a static artifact using the established pattern

The Dojo must be assembled by a `docusaurus/dojo-src/build.sh` that mirrors
`course-src/build.sh`: source parts concatenated into `docusaurus/static/dojo/`,
invoked from the same `prebuild` hook, reachable at `pathname:///dojo/index.html`.

It must not introduce a bundler, a framework dependency, or a second build system.
If the courses build with `bash` and `cp`, so does this.

### FR-2 — Live mode against the reader's own fleet

The page must be able to stream from `http://localhost:9889/agui/v1/stream` and render
the reader's **own** running agents. The endpoint must be editable in the UI, because
a reader may run `cao-server` on another host or port.

Live mode must degrade honestly: when nothing is listening, the page states that no
CAO server was reachable and how to start one. It must not present an empty view that
looks like a working fleet with no activity.

### FR-3 — Replay mode with zero setup

The page must render a committed event-trace fixture with no CAO installation, no
server, and no network access beyond loading the page. Replay is the default mode,
because most readers arrive without CAO running.

Replay must be visibly labelled as recorded. A reader must never mistake a fixture for
their own fleet.

### FR-4 — Capture the fixture from a real run, never hand-write it

The trace fixture must be produced by recording an actual CAO run through the real
`/agui/v1/stream`, by extending the existing recorder to persist SSE frames alongside
the GIF it already produces.

A hand-authored fixture is prohibited. The entire value of this page is that it shows
what CAO actually emits; a fabricated trace would make it a mock-up that asserts its
own correctness — the same failure the AG-UI projection principles reject.

### FR-5 — CI must fail when the Dojo stops rendering

A CI assertion must drive the built page in replay mode and verify that the expected
components render. This page is a claim about the product; an unverified claim on a
docs site is worse than no claim, because it is quoted.

The assertion must run on the **built** artifact from `static/dojo/`, not on the source
parts, so a build-script regression is caught too.

### FR-6 — The allow-list must remain the only source of truth

The Dojo must render components by reading what the stream sends. It must not carry its
own list of component names that could drift from `GENERATIVE_UI_COMPONENTS`, and it
must not be able to render a component the server would refuse.

If a future component is added server-side, the Dojo should render it without a code
change; if one is removed, the Dojo must not keep rendering it.

### FR-7 — Metadata-only, verifiably

No message body may appear in the fixture. `_BODY_FIELDS`
(`services/agui/base.py:28`) names the fields the surface strips; the fixture must be
asserted free of them, so a recording mistake cannot publish agent output into a
public repository.

### FR-8 — Reference docs, separate from the narrative

The Dojo must be documented in `docusaurus/docs/` as maintained reference material,
distinct from the blog post that announces it.

A blog post is dated and narrative; docs are current and maintained. Conflating them is
how [#448](https://github.com/awslabs/cli-agent-orchestrator/pull/448) drifted into
three factually wrong claims and blocked itself for 46 days. The post links to the
docs; it does not replace them.

### FR-9 — Ship in reviewable increments

Live mode and the demo agent plugin depend on
[#584](https://github.com/awslabs/cli-agent-orchestrator/pull/584); replay mode and the
static page depend on nothing. They must be separate pull requests.

[#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387) bundled a full stack
into one review and was closed unmerged at +16,288 lines. That outcome is the reason
this requirement is normative rather than advisory.

### FR-10 — Blog governance is a build gate, not a formality

`docusaurus.config.ts` sets `onInlineAuthors: 'throw'` and `onInlineTags: 'throw'`.
`plauzy` is **not** in `blog/authors.yml` (registered: `cao-maintainers`, `haofeif`,
`fanhongy`, `sujoydc`), and no `ag-ui` tag exists (available: `tutorial`, `deep-dive`,
`orchestration-patterns`, `providers`, `mcp`, `case-study`, `community`).

The docs build **fails** until the author is registered and every tag resolves. Either
reuse existing tags or add one in the same PR with a justification, which `tags.yml`
explicitly permits.

## Non-functional requirements

### NFR-1 — No new runtime dependency for the page

The published page must remain openable from `file://` with no server and no package
install, matching the viewer's existing zero-dependency property.

### NFR-2 — Fixture size bounded

The committed trace must stay small enough to review in a diff. If a representative run
does not fit, it must be truncated at a run boundary rather than mid-stream, and the
truncation must be visible in the page.

### NFR-3 — Does not slow the docs build materially

`build.sh` runs on every `npm start` and `npm run build`. The Dojo assembly must stay a
file-concatenation step.

## Out of scope

- **Expanding `GENERATIVE_UI_COMPONENTS`.** Owned by
  [#582](https://github.com/awslabs/cli-agent-orchestrator/issues/582), whose non-goal
  — *expanding the allow-list before compatibility is established* — is adopted here.
- **Hosting a live CAO instance** for the public site. Ruled out by the static
  constraint above, not deferred.
- **The `UiIntentProjection` seam** and external UI specs (A2UI, MCP Apps) — later
  milestones of the AG-UI roadmap track.
- **Replacing [ag-ui#2216](https://github.com/ag-ui-protocol/ag-ui/pull/2216).** This
  complements the upstream Dojo contribution; it does not substitute for it.
- **Within-run progression.** `run_plane_stream` calls `snapshot_fn` once per run, so
  the fixture shows one step per turn. Fixing that is a separate roadmap milestone; this
  spec must not work around it by fabricating intermediate frames.

## Acceptance criteria

1. `cd docusaurus && npm run build` produces `static/dojo/index.html`, and the page
   opens from `file://` and renders the fixture with no server running.
2. With `cao-server` running and `CAO_AGUI_ENABLED` set, switching to live mode renders
   the reader's own fleet; with nothing listening, the page says so explicitly.
3. The fixture is byte-traceable to a recorded run, and CI regenerates or verifies it.
4. A CI job drives the built page and fails if an expected component stops rendering.
5. No `_BODY_FIELDS` key appears anywhere in the fixture, asserted by test.
6. The docs page exists in `docusaurus/docs/` and the blog post links to it.
7. `npm run build` succeeds, proving author and tag registration are complete.
8. Replay mode and live mode ship as separate pull requests.
