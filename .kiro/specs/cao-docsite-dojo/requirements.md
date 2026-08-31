# Requirements Document

## Introduction

A CAO Dojo on the docs site — a static, zero-dependency interactive page that renders
the AG-UI event stream in two modes: **replay** from a committed trace fixture (the
default, requiring no setup) and **live** from the reader's own `cao-server`. The page
is a runnable proof of the claim CAO's AG-UI surface already makes: *a stock AG-UI
client renders a live multi-agent CAO run with zero CAO-specific client code.*

**Related:** [#519](https://github.com/awslabs/cli-agent-orchestrator/issues/519) ·
[#436](https://github.com/awslabs/cli-agent-orchestrator/pull/436) (merged) ·
[#485](https://github.com/awslabs/cli-agent-orchestrator/pull/485) (merged) ·
[ag-ui#2216](https://github.com/ag-ui-protocol/ag-ui/pull/2216)

**Scope:** `docs` + `examples` — a static interactive page, a trace fixture, and a CI
assertion. No change to the AG-UI service, the stream contract, or the allow-list. PR 1,
the immediate scope, is replay mode plus the static page plus the CI gate.

**Provenance of this document:** ported and refined from
`docs/issues/docsite-dojo/requirements.md`, whose FR/NFR numbering, evidence citations,
and rationale are preserved. Two defects found in that version are corrected here — see
FR-6 and FR-3 — and a Correctness properties section is added.

---

## Glossary

- **Dojo_Page**: the built static artifact at `docusaurus/static/dojo/index.html`,
  reachable on the docs site as `pathname:///dojo/index.html`.
- **Dojo_Build**: `docusaurus/dojo-src/build.sh`, the file-concatenation script that
  assembles Dojo_Page from source parts.
- **Renderer**: the component-dispatch and state-application logic inside Dojo_Page,
  sourced from `examples/ag-ui/ag-ui-eventsource-viewer/index.html`.
- **Transport**: the seam supplying AG-UI frames to Renderer. Two implementations exist:
  Live_Transport and Replay_Transport.
- **Live_Transport**: an `EventSource` connection to a reader-supplied AG-UI endpoint,
  default `http://localhost:9889/agui/v1/stream`.
- **Replay_Transport**: a paced player over Trace_Fixture, requiring no network.
- **Trace_Fixture**: the NDJSON event trace committed under `docusaurus/dojo-src/fixtures/`,
  captured from a real recorded CAO run.
- **Placeholder_Trace**: a hand-authored NDJSON trace kept only as a local development
  convenience, stored under a filename distinct from Trace_Fixture and carrying
  `_meta.placeholder` set to `true`. A Placeholder_Trace never satisfies FR-4 and never
  reaches Dojo_Page.
- **Recorder**: `examples/ag-ui/ag-ui-eventsource-viewer/tools/record-demo.mjs`, driven by
  the existing `AG-UI demo (shift-left recording)` CI job.
- **Allow_List**: `GENERATIVE_UI_COMPONENTS`, enforced server-side at
  `src/cli_agent_orchestrator/services/agui/base.py:339`.
- **Body_Fields**: `_BODY_FIELDS = frozenset({"delta", "content", "message_body", "stdout"})`
  at `src/cli_agent_orchestrator/services/agui/base.py:28` — the fields the AG-UI surface
  strips before emission.
- **Generic_Renderer**: the fallback presentation path that renders any props object as
  labelled fields, used for any component name lacking a specific refinement.

---

## Context

CAO's AG-UI surface shipped in
[#436](https://github.com/awslabs/cli-agent-orchestrator/pull/436) (L1) and
[#485](https://github.com/awslabs/cli-agent-orchestrator/pull/485) (L2). Today that
claim is demonstrated by a CI job that produces a GIF, and by a zero-dependency viewer a
reader must find in `examples/`, read, and run themselves.

The [AG-UI Dojo](https://dojo.ag-ui.com/) solves the equivalent problem for every other
framework by hosting live example servers a reader can click. CAO has no such surface,
and [ag-ui#2216](https://github.com/ag-ui-protocol/ag-ui/pull/2216) — which would put
CAO *in* the Dojo — is open pending maintainer review that we do not control.

This spec covers a Dojo-equivalent **on CAO's own docs site**, which we do control.

## Provenance

Every mechanism below already exists in the repository. This is assembly, not invention,
and the requirements are written to keep it that way:

| Existing thing | Location | Why it matters here |
|---|---|---|
| Interactive standalone HTML build pipeline | `docusaurus/course-src/build.sh`, wired via `prebuild`/`prestart` in `docusaurus/package.json:7-10` | The pattern to follow. Concatenates `_base.html` + `modules/*.html` (globbed in filename order) + `_footer.html` into `static/`, linked as `pathname:///course/index.html` |
| Zero-dependency AG-UI viewer | `examples/ag-ui/ag-ui-eventsource-viewer/index.html`, 499 lines, no build step | The Renderer. Already consumes `/agui/v1/stream` via `EventSource` |
| Shift-left recorder | `examples/ag-ui/ag-ui-eventsource-viewer/tools/record-demo.mjs` (Playwright + ffmpeg), CI job `AG-UI demo (shift-left recording)` | Already boots a live server and drives the viewer on every commit |
| Build-output ignore block | `docusaurus/.gitignore:13-15` (`/static/course/`, `/static/course-advanced/`, `/static/course-assets/`) | Establishes that assembled artifacts are gitignored, not committed |
| Governed blog | `docusaurus/blog/` with `authors.yml` / `tags.yml` | Where the narrative ships |
| Allow-list source of truth | `GENERATIVE_UI_COMPONENTS`, enforced at `services/agui/base.py:339` | What the Dojo must not be able to widen |

## The hard constraint someone must internalise

**GitHub Pages is static, and the docs deploy is fork-gated.** The AG-UI Dojo hosts live
agent backends; `.github/workflows/gh-pages.yml` publishes a static Docusaurus build,
only from `awslabs/cli-agent-orchestrator` (or a fork that sets
`DEPLOY_DOCS_PAGES=true`), and only on `main`.

There is therefore **no server** to stream from on the published site. Any design that
assumes a hosted CAO instance is wrong. The two viable sources are the reader's own
`localhost:9889`, and a fixture committed to the repository — which is why FR-2 and FR-3
exist as separate requirements rather than one.

A second, quieter constraint: the Recorder captures **pixels**, not frames.
`record-demo.mjs` drives Playwright and pipes screenshots to ffmpeg; it never persists
the SSE payloads. Replay mode cannot reuse its output and needs frame capture added
(FR-4).

A third, discovered while refining this document: browsers block `fetch`/XHR against
`file://` origins. A design in which Replay_Transport fetches Trace_Fixture at runtime
cannot satisfy the `file://` requirement at all. This is corrected in FR-3.

---

## Requirements

### Functional requirements

#### FR-1 — Build as a static artifact using the established pattern

Dojo_Page must be assembled by Dojo_Build mirroring `course-src/build.sh`: source parts
concatenated into `docusaurus/static/dojo/`, invoked from the same `prebuild` hook,
reachable at `pathname:///dojo/index.html`.

It must not introduce a bundler, a framework dependency, or a second build system. If the
courses build with `bash` and `cat`, so does this. Module fragments are `.html` files
each carrying its own `<script>` block, because `course-src/build.sh` globs
`"$SRC/$name"/modules/*.html` — introducing a `.js` variant would make Dojo_Build and its
sibling diverge for no gain.

##### Acceptance Criteria

1. WHEN `npm run build` is executed in `docusaurus/`, THE Dojo_Build SHALL write a
   non-empty `static/dojo/index.html`.
2. THE Dojo_Build SHALL assemble Dojo_Page by concatenating `_base.html`, then
   `modules/*.html` in filename order, then `_footer.html`.
3. THE Dojo_Build SHALL be invoked from the same `prebuild` and `prestart` npm hooks that
   invoke `course-src/build.sh`.
4. THE Dojo_Build SHALL complete using only `bash` builtins and coreutils already
   required by `course-src/build.sh`.
5. THE `docusaurus/.gitignore` file SHALL list `/static/dojo/` alongside the existing
   `/static/course/`, `/static/course-advanced/`, and `/static/course-assets/` entries at
   lines 13-15.

#### FR-2 — Live mode against the reader's own fleet

Dojo_Page must be able to stream from `http://localhost:9889/agui/v1/stream` and render
the reader's **own** running agents. The endpoint must be editable in the UI, because a
reader may run `cao-server` on another host or port.

Live mode must degrade honestly. Distinguishing "never connected" from "connection
dropped" matters: the first is a setup problem with a documented fix, the second is not.
An empty view that looks like a working fleet with no activity is prohibited.

##### Acceptance Criteria

1. WHERE live mode is selected, THE Live_Transport SHALL open an `EventSource` connection
   to the endpoint shown in the endpoint field, defaulting to
   `http://localhost:9889/agui/v1/stream`.
2. THE Dojo_Page SHALL accept a reader-edited endpoint value and use that value for
   subsequent Live_Transport connections.
3. IF Live_Transport reports an error before any frame has arrived, THEN THE Dojo_Page
   SHALL display that no CAO server was reachable at the configured endpoint, together
   with instructions for starting one.
4. IF Live_Transport reports an error after at least one frame has arrived, THEN THE
   Dojo_Page SHALL display a disconnection notice stating the number of frames received
   and offer a retry control.
5. THE Dojo_Page SHALL perform every live-mode network request from the browser via
   `EventSource`, introducing no server-side fetch.

#### FR-3 — Replay mode with zero setup, from a build-time embedded fixture

Dojo_Page must render Trace_Fixture with no CAO installation, no server, and no network
access beyond loading the page. Replay is the default mode, because most readers arrive
without CAO running.

**This corrects a defect in the ported version.** The earlier design had
`openReplay(fixtureUrl, …)` fetch Trace_Fixture at runtime. Browsers block `fetch` and
XHR against `file://` origins, so acceptance criterion 1 — *the page opens from `file://`
and renders the fixture with no server running* — was unachievable as designed. The
fixture delivery mechanism is therefore itself a requirement: Dojo_Build embeds the
fixture into Dojo_Page, which is what concatenation naturally does. The page performs no
runtime fetch in replay mode and genuinely satisfies `file://`.

The committed NDJSON fixture remains the source artifact under `dojo-src/fixtures/`, so
FR-4 is untouched. The build is the **only** path from the source fixture to the inlined
copy; no second, hand-maintained inlined copy may exist, because two copies would drift
exactly as two copies of the Renderer would.

This tightens rather than loosens NFR-2: inlining means fixture bytes land directly in
the shipped page, so the size bound now governs page weight as well as diff
reviewability.

##### Acceptance Criteria

1. WHEN Dojo_Page loads from a URL carrying no recognised live-mode selector, THE
   Dojo_Page SHALL activate Replay_Transport as the active Transport.
2. THE Dojo_Build SHALL embed the committed Trace_Fixture into Dojo_Page as exactly one
   inline, non-executing data block, escaping every occurrence of `</script`, `<script`,
   `<!--`, `-->`, U+2028, and U+2029 so that no byte sequence present in Trace_Fixture
   can terminate or alter the enclosing element.
3. WHEN a Trace_Fixture whose event records contain the sequences `</script`, `<script`,
   `<!--`, `-->`, U+2028, or U+2029 inside string values is embedded by Dojo_Build, THE
   Replay_Transport SHALL deliver each such record to Renderer with field values
   byte-identical to the committed record.
4. WHEN Dojo_Page is opened from a `file://` URL with no server running and no network
   available, THE Replay_Transport SHALL deliver every event record of the embedded
   Trace_Fixture to Renderer in committed order, without issuing any network request
   after document load.
5. THE Dojo_Page SHALL contain exactly one embedded copy of Trace_Fixture, such that
   extracting and unescaping that copy yields the committed Trace_Fixture byte for byte.
6. IF the copy extracted from a built Dojo_Page does not match the committed
   Trace_Fixture byte for byte, THEN THE Dojo_Build SHALL exit with a non-zero status and
   an error indicating the mismatch, and SHALL NOT publish Dojo_Page.
7. WHILE Replay_Transport is active, THE Dojo_Page SHALL display a label identifying the
   displayed run as recorded, carrying the embedded `_meta.captured_at` value and, where
   `_meta.truncated` is true, an indication that the recording is incomplete.
8. IF the embedded Trace_Fixture contains zero event records after the `_meta` header,
   THEN THE Dojo_Page SHALL display a message indicating that no recorded events are
   available and SHALL leave the Transport selector operable.
9. WHILE Replay_Transport is active, THE Replay_Transport SHALL pace records at a fixed
   inter-record interval, defined at a single location in the Dojo_Page source and
   documented in the reference page, rather than synthesising wall-clock timings the
   recording does not contain.
10. WHILE Replay_Transport is active, THE Dojo_Page SHALL expose a scrubber that
    positions playback at any record index from 0 to one less than the embedded record
    count.

#### FR-4 — Capture the fixture from a real run, never hand-write it

Trace_Fixture must be produced by recording an actual CAO run through the real
`/agui/v1/stream`, by extending the Recorder to persist SSE frames alongside the GIF it
already produces.

A hand-authored fixture is prohibited. The entire value of this page is that it shows
what CAO actually emits; a fabricated trace would make it a mock-up that asserts its own
correctness — the same failure the AG-UI projection principles reject.

Recording needs a running `cao-server` with `CAO_AGUI_ENABLED`, Playwright's Chromium,
and `ffmpeg`, none of which exist in a constrained environment. A clearly-marked
placeholder is therefore permitted as a local development convenience and nothing more:
a placeholder never satisfies this requirement, never reaches Dojo_Page, and carries a
machine-detectable marker so the build can refuse one that does.

Provenance must be **checkable**, not merely asserted — a `_meta` block a hand-writer can
type is worth nothing unless the values are validated against the frames and against the
repository. And a fixture is a dated snapshot: when the stream contract changes, the
fixture is regenerated, or the page starts describing a CAO that no longer exists.

##### Acceptance Criteria

1. WHEN the Recorder executes a demonstration run, THE Recorder SHALL persist every AG-UI
   frame received from `/agui/v1/stream` as NDJSON, one JSON object per line, in arrival
   order.
2. WHEN the Recorder completes a demonstration run, THE Recorder SHALL produce the
   existing GIF output unchanged in name and location, so the currently green `AG-UI demo
   (shift-left recording)` job keeps gating.
3. IF frame capture fails during a Recorder run, THEN THE Recorder SHALL report the
   capture failure, complete GIF production, and exit with the status the Recorder would
   return with frame capture absent.
4. THE CI pipeline SHALL assert that the `AG-UI demo (shift-left recording)` job produces
   the GIF artifact, independently of whether frame capture succeeded.
5. THE Trace_Fixture SHALL carry, on the first line, a `_meta` header record with the
   fields `captured_at`, `cao_version`, `run_ids`, `truncated`, and `placeholder`.
6. IF the first record of a candidate Trace_Fixture is missing, is not a `_meta` record,
   or carries a `captured_at` value that is not a parseable UTC timestamp at or before the
   time of validation, THEN THE CI pipeline SHALL fail the build and name the offending
   field.
7. THE `_meta.cao_version` value SHALL be a parseable version string, and THE Dojo_Page
   SHALL display that value alongside the recorded-run label, so that a reader can judge
   how old the recording is; version drift between the recording and the repository is
   surfaced to the reader rather than failing the build, because gating on a match would
   red the docs build on every minor release until someone re-records.
8. IF `_meta.cao_version` is absent or is not a parseable version string, THEN THE CI
   pipeline SHALL fail the build and name the offending field.
9. IF `_meta.run_ids` is empty, IF a run identifier carried by any Trace_Fixture frame is
   absent from `_meta.run_ids`, or IF a value in `_meta.run_ids` appears in no frame, THEN
   THE CI pipeline SHALL fail the build and name the mismatching identifier.
10. THE Recorder SHALL capture Trace_Fixture from a demonstration scenario committed in
    the repository and executed solely for recording, rather than from a maintainer or
    reader work session.
11. WHERE a hand-authored trace is used for local development, THE trace SHALL be stored
    under a filename distinct from Trace_Fixture and SHALL carry `_meta.placeholder` set
    to `true`.
12. IF a trace that does not carry `_meta.placeholder` set to `false` is committed as
    Trace_Fixture or embedded into Dojo_Page by Dojo_Build, THEN THE CI pipeline SHALL
    fail the build.
13. WHERE the CI pipeline performs a Recorder run, THE CI pipeline SHALL report every
    event type and component name observed in that run but absent from Trace_Fixture as a
    staleness warning, and THE Trace_Fixture SHALL be regenerated before the next release
    rather than immediately, because gating the docs build on a live recorded run would
    couple it to server behaviour this specification does not own.

#### FR-5 — CI must fail when the Dojo stops rendering

A CI assertion must drive Dojo_Page in replay mode and verify that the expected
components render. This page is a claim about the product; an unverified claim on a docs
site is worse than no claim, because it is quoted.

The assertion must run on the **built** artifact from `static/dojo/`, not on the source
parts, so a build-script regression is caught too.

##### Acceptance Criteria

1. THE CI pipeline SHALL drive the built `static/dojo/index.html` over a `file://` URL in
   replay mode.
2. IF any component present in the embedded fixture fails to render, THEN THE CI pipeline
   SHALL fail.
3. THE CI pipeline SHALL execute the render assertion against the build output rather than
   against files in `dojo-src/`.

#### FR-6 — The allow-list must remain the only source of truth

Dojo_Page must render components by reading what the stream sends. The server stays
authoritative: if a component is added to Allow_List, Dojo_Page renders it without a code
change; if one is removed, Dojo_Page stops showing it because the stream stops sending it.

**This corrects a defect in the ported version.** That version specified verification as
*"a test greps the built page for hardcoded component names and fails if any appear"* —
which directly contradicts the design's own `RENDERERS` map, described as *"presentation
refinements keyed by component name."* Those keys **are** hardcoded component names. The
grep forbids the exact mechanism the design requires, so the two could not both hold.

The requirement is therefore restated **behaviourally**. The load-bearing invariant is
not that no component name appears in the page text; it is that **no name list gates
rendering**. Presentation refinements keyed by name are permitted and expected — they
affect how a component looks, never whether it renders. The grep is explicitly retired:
it tested spelling rather than behaviour, and it would have failed a correct
implementation while passing an incorrect one that hardcoded a gate under a different
identifier.

Two consequences of that restatement shape the criteria below. First, the prohibition is
stated as an **observable outcome** — every delivered `GENERATIVE_UI` frame produces
exactly one visible view — rather than as a list of forbidden code shapes. A name list, a
known-prefix test, a props-shape precondition, a `switch` without a `default`, and a
`try`/`catch` that drops on error are all different spellings of the same defect, and all
of them fail the outcome. Second, "renders via Generic_Renderer" is only testable if the
fallback path is **distinguishable in the rendered output**, so criterion 1 fixes what
that output must contain; an implementation that swallows an unknown component into an
empty container fails it.

Removal behaviour is a **consequence, not a criterion**. Dojo_Page cannot observe a
server-side removal; what is assertable is that the set of views displayed is exactly the
set of frames delivered (criterion 2), from which "removed from Allow_List ⇒ no longer
displayed" follows without a separate test.

CP-2 (dispatch totality) is the property-based executable form of criteria 1 through 6:
the criteria define the observable contract for a single frame, and CP-2 quantifies that
contract over generated component names and props.

##### Acceptance Criteria

1. WHEN a `GENERATIVE_UI` frame arrives carrying a component name for which no
   presentation refinement is registered, THE Renderer SHALL render the frame via
   Generic_Renderer, producing a view that displays the component name as text together
   with one labelled field per top-level key of the frame's props, and WHERE the props
   object has no keys, THE Renderer SHALL still display the named view with zero fields
   rather than no view.
2. THE Renderer SHALL produce exactly one visible view for every `GENERATIVE_UI` frame
   delivered by Transport, whatever the component name or props content, so that the set
   of views displayed is exactly the set of frames delivered and no view appears for a
   component Transport did not deliver.
3. IF a `GENERATIVE_UI` frame carries a component name absent from Allow_List, THEN THE
   Renderer SHALL render that frame, and the resulting view SHALL have the same structure
   as the view rendered for a name present in Allow_List carrying the same props and
   having no registered refinement.
4. WHERE a presentation refinement is registered for a component name, THE Renderer SHALL
   use that refinement for appearance only, rendering the same frame's props whether or
   not the refinement is registered.
5. WHEN a `GENERATIVE_UI` frame arrives carrying a component name that is an empty string,
   consists only of whitespace, or exceeds 512 characters, THE Renderer SHALL render the
   frame via Generic_Renderer — substituting a fixed placeholder label for an empty or
   whitespace-only name, truncating a longer name for display only — and SHALL render the
   frame's props unchanged.
6. THE Renderer SHALL insert every component name and every props key and scalar value
   into Dojo_Page as text and never as markup, so that a name, key, or value containing
   HTML metacharacters is displayed literally and originates no element, no attribute, and
   no script execution.
7. THE CI pipeline SHALL verify criteria 1 through 6 by behavioural test, over a frame set
   that includes a component name absent from Allow_List, an empty name, a name of 512
   characters, and a name containing HTML metacharacters, asserting for each frame that
   one view is rendered and that no element originates from the name text; and SHALL NOT
   verify them by lexical search of Dojo_Page.

#### FR-7 — Metadata-only, verifiably

No message body may appear in Trace_Fixture. Body_Fields names the fields the surface
strips; the fixture must be asserted free of them, so a recording mistake cannot publish
agent output into a public repository.

The assertion must recurse. A top-level key check or a string grep would miss a body
field nested inside a `STATE_SNAPSHOT` payload, which is precisely where one would
appear.

##### Acceptance Criteria

1. THE Trace_Fixture SHALL contain no key named `delta`, `content`, `message_body`, or
   `stdout` at any nesting depth within any frame.
2. THE CI pipeline SHALL assert criterion 1 by recursive traversal of every parsed frame.
3. IF any Body_Fields key is found at any depth, THEN THE CI pipeline SHALL fail and name
   the offending frame index and JSON path.

#### FR-8 — Reference docs, separate from the narrative

The Dojo must be documented in `docusaurus/docs/` as maintained reference material,
distinct from the blog post that announces it.

A blog post is dated and narrative; docs are current and maintained. Conflating them is
how [#448](https://github.com/awslabs/cli-agent-orchestrator/pull/448) drifted into three
factually wrong claims and blocked itself for 46 days. The post links to the docs; it does
not replace them.

##### Acceptance Criteria

1. THE repository SHALL contain a reference page for the Dojo under `docusaurus/docs/`,
   registered in `sidebars.ts`.
2. THE blog post announcing the Dojo SHALL link to the reference page rather than restate
   its content.
3. THE `docusaurus.config.ts` navbar SHALL expose Dojo_Page, mirroring how
   `pathname:///course/index.html` is registered.
4. WHEN `scripts/validate_markdown_links.py` runs, THE new documentation SHALL pass link
   validation.

#### FR-9 — Ship in reviewable increments

Live mode and the demo agent plugin depend on
[#584](https://github.com/awslabs/cli-agent-orchestrator/pull/584); replay mode and the
static page depend on nothing. They must be separate pull requests.

[#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387) bundled a full stack
into one review and was closed unmerged at +16,288 lines. That outcome is the reason this
requirement is normative rather than advisory.

##### Acceptance Criteria

1. THE replay-mode increment SHALL be submitted as a pull request containing no live-mode
   implementation.
2. THE live-mode increment SHALL be submitted as a pull request separate from the
   replay-mode increment.
3. THE replay-mode increment SHALL depend on no unmerged pull request.

#### FR-10 — Blog governance is a build gate, not a formality

`docusaurus.config.ts` sets `onInlineAuthors: 'throw'` and `onInlineTags: 'throw'`.
`plauzy` is **not** in `blog/authors.yml` (registered: `cao-maintainers`, `haofeif`,
`fanhongy`, `anilkmr-a2z`, `gutosantos82`, `sujoydc`, `guojing1217` — the ported version
of this document listed only four of these seven; the substantive point that `plauzy` is
absent is unchanged), and no `ag-ui` tag exists (available: `tutorial`, `deep-dive`,
`orchestration-patterns`, `providers`, `mcp`, `case-study`, `community`).

The docs build **fails** until the author is registered and every tag resolves. Either
reuse existing tags or add one in the same PR with a justification, which `tags.yml`
explicitly permits.

##### Acceptance Criteria

1. THE `docusaurus/blog/authors.yml` file SHALL register every author referenced by the
   Dojo blog post before that post is committed.
2. THE Dojo blog post SHALL reference only tags defined in `docusaurus/blog/tags.yml`.
3. WHERE a new tag is introduced, THE same pull request SHALL add it to
   `docusaurus/blog/tags.yml` with a justification in the pull request description.
4. WHEN `npm run build` runs in `docusaurus/`, THE build SHALL succeed, demonstrating
   author and tag registration are complete.

---

### Non-functional requirements

#### NFR-1 — No new runtime dependency for the page

Dojo_Page must remain openable from `file://` with no server and no package install,
matching the viewer's existing zero-dependency property.

##### Acceptance Criteria

1. THE Dojo_Page SHALL load and render in replay mode with zero network requests after
   the document itself is loaded.
2. THE Dojo_Page SHALL reference no external script, stylesheet, font, or CDN asset.

#### NFR-2 — Fixture size bounded

Trace_Fixture must stay small enough to review in a diff. Because FR-3 embeds it into the
shipped page, its size also governs page weight, so the bound is load-bearing twice over.

##### Acceptance Criteria

1. WHERE a representative run exceeds the reviewable size bound, THE Trace_Fixture SHALL
   be truncated at a run boundary rather than mid-stream.
2. WHERE Trace_Fixture is truncated, THE `_meta.truncated` value SHALL be `true` and
   Dojo_Page SHALL display that the recording is truncated.

#### NFR-3 — Does not slow the docs build materially

`build.sh` runs on every `npm start` and `npm run build`. Dojo assembly must stay a
file-concatenation step.

##### Acceptance Criteria

1. THE Dojo_Build SHALL assemble Dojo_Page using file concatenation and copying only,
   invoking no compiler, bundler, or package installation.

---

## Out of scope

- **Expanding `GENERATIVE_UI_COMPONENTS`.** Owned by
  [#582](https://github.com/awslabs/cli-agent-orchestrator/issues/582), whose non-goal —
  *expanding the allow-list before compatibility is established* — is adopted here.
- **Hosting a live CAO instance** for the public site. Ruled out by the static constraint
  above, not deferred: `cao-server` is an unauthenticated command-execution surface, so a
  public instance is a non-starter regardless of cost.
- **The `UiIntentProjection` seam** and external UI specs (A2UI, MCP Apps) — later
  milestones of the AG-UI roadmap track.
- **Replacing [ag-ui#2216](https://github.com/ag-ui-protocol/ag-ui/pull/2216).** This
  complements the upstream Dojo contribution; it does not substitute for it.
- **Within-run progression.** `run_plane_stream` calls `snapshot_fn` once per run, so the
  fixture shows one step per turn. Fixing that is a separate roadmap milestone; this spec
  must not work around it by fabricating intermediate frames.

---

## Correctness properties

The ported version verified everything by example — a grep, a presence assertion, "asserts
each component renders". Those checks confirm one path works; they do not constrain
behaviour over the input space. The following properties are stated with their generator
domains so they can be executed as property-based tests.

### CP-1 — Transport-seam indistinguishability

**Property:** for any sequence of AG-UI frames, driving Renderer through Replay_Transport
and driving it through Live_Transport produce identical final rendered state.

**Generator domain:** arbitrary-length sequences of AG-UI frames, drawn from
`STATE_SNAPSHOT`, `STATE_DELTA`, and `GENERATIVE_UI` event shapes, including the empty
sequence, single-frame sequences, and sequences with repeated frames.

**Why it is the load-bearing property:** this is what makes replay *honest*. If Renderer
cannot distinguish its Transport, then a fixture exercises the same code path as a live
stream, and FR-5's replay-mode CI gate is evidence about live mode too. If it can
distinguish them, replay proves nothing about the product and the whole page reduces to a
mock-up.

### CP-2 — Dispatch totality

**Property:** for any component name and any JSON-serialisable props object, dispatch
renders some output, and never throws and never silently drops the frame.

**Generator domain:** component names including every member of Allow_List, names absent
from Allow_List, empty strings, and names containing punctuation and non-ASCII characters;
props including `{}`, flat scalar maps, arrays, and objects nested to arbitrary depth.

**Relationship to FR-6:** CP-2 is the executable form of FR-6 criteria 1 and 3. It is
what the retired grep was reaching for, expressed over the input space instead of over the
page's spelling.

### CP-3 — State-delta application soundness

**Property, determinism:** applying a `STATE_SNAPSHOT` followed by a sequence of RFC-6902
`STATE_DELTA` operations yields the same state on every evaluation.

**Property, order-dependence:** state is a function of delta *order*; the property asserts
that reordering non-commuting operations changes the result, guarding against an
implementation that accidentally merges deltas order-insensitively.

**Property, atomicity:** if a patch is malformed or non-applicable, prior state is left
intact — no partially-mutated view is ever rendered.

**Generator domain:** arbitrary snapshot objects; sequences of RFC-6902 operations
(`add`, `remove`, `replace`, `move`, `copy`, `test`) over paths both present and absent in
the snapshot; deliberately malformed patches, including invalid paths, missing `op`, and
type-mismatched values.

### CP-4 — Fixture prefix validity

**Property:** any line-truncated prefix of a valid Trace_Fixture is itself a valid
Trace_Fixture.

**Generator domain:** a valid fixture together with every line-boundary truncation point,
including truncation to the `_meta` header alone and truncation to zero lines.

**Why it is a property, not a rationale sentence:** append-only prefix validity is the
stated reason NDJSON was chosen over a JSON array, and it is what makes NFR-2's truncation
allowance safe. Asserting it makes the format choice verified rather than merely argued.

### CP-5 — Metadata-only invariance

**Property:** no Body_Fields key occurs at any depth in any frame of Trace_Fixture.

**Generator domain:** every frame of the committed fixture, traversed recursively through
objects and arrays to arbitrary depth. The property is additionally exercised against
generated poisoned fixtures — body fields injected at randomly chosen depths and paths —
to confirm the check detects them wherever they occur.

**Relationship to FR-7:** CP-5 subsumes a top-level key check and a string grep. A grep
over serialised JSON would also match a body field appearing as a *value*, producing false
positives, while missing keys whose serialisation is split across lines.

---

## Acceptance criteria

These are the release gates for the feature as a whole. Criteria 1, 3, 4, 5, 6, 7, and 8
gate PR 1 (replay mode); criterion 2 gates PR 2 (live mode).

1. `cd docusaurus && npm run build` produces `static/dojo/index.html`; the page opens
   from `file://` and renders the fixture with no server running and no network access,
   because Dojo_Build embedded the fixture at build time and the page performs no runtime
   fetch.
2. With `cao-server` running and `CAO_AGUI_ENABLED` set, switching to live mode renders
   the reader's own fleet; with nothing listening, the page states that no server was
   reachable and how to start one, distinctly from a mid-stream disconnection.
3. The committed fixture is byte-traceable to a recorded run via its `_meta` header, CI
   regenerates or verifies it, no Placeholder_Trace reaches the released artifact
   (`_meta.placeholder` is `false` on the committed fixture and on the copy embedded in
   the built page), and the copy embedded in the built page is derived from the committed
   copy by Dojo_Build alone.
4. A CI job drives the built page over `file://` and fails if an expected component stops
   rendering.
5. No Body_Fields key appears at any depth in any fixture frame, asserted by recursive
   traversal (CP-5) rather than by grep.
6. A behavioural test feeds a component name absent from `GENERATIVE_UI_COMPONENTS` and
   asserts it renders via Generic_Renderer; no lexical check of the built page's component
   names is present in CI.
7. The reference page exists in `docusaurus/docs/`, is registered in `sidebars.ts` and the
   navbar, passes `validate_markdown_links.py`, and the blog post links to it.
8. `npm run build` succeeds, proving author and tag registration are complete;
   `/static/dojo/` is gitignored so no build output is committed; exactly one copy of the
   Renderer exists in the tree.
9. Replay mode and live mode ship as separate pull requests.
10. CP-1 through CP-5 are implemented as property-based tests and pass.
