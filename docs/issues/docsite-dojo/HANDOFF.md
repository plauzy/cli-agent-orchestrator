# Handoff prompt — CAO docs-site Dojo (PR 1)

Paste everything below the line into a fresh Kiro CLI session. It is written to be
self-contained: it assumes no memory of the session that produced the spec.

---

## Your task

Implement **PR 1** of the spec at `docs/issues/docsite-dojo/` in this repository:
a static, zero-dependency interactive "Dojo" page on the CAO docs site that renders the
AG-UI event stream in **replay mode** from a committed trace fixture.

Read all three spec files before writing any code:

- `docs/issues/docsite-dojo/requirements.md` — 10 `FR-N` + 3 `NFR-N`, plus acceptance criteria
- `docs/issues/docsite-dojo/design.md` — architecture, file layout, algorithms, alternatives already rejected
- `docs/issues/docsite-dojo/tasks.md` — PR 1 is tasks 1.1 through 1.14

The spec is the contract. If you believe a requirement is wrong, say so and stop —
do not silently redesign around it.

## What this is, in one paragraph

CAO's AG-UI surface ([#436](https://github.com/awslabs/cli-agent-orchestrator/pull/436),
[#485](https://github.com/awslabs/cli-agent-orchestrator/pull/485), both merged) claims
that a stock AG-UI client renders a live multi-agent CAO run with zero CAO-specific
client code. Today that claim is only demonstrated by a CI job that exports a GIF. This
page makes the claim runnable on CAO's own docs site — which matters because
[ag-ui#2216](https://github.com/ag-ui-protocol/ag-ui/pull/2216), which would put CAO in
the official AG-UI Dojo, is open pending maintainer review we do not control.

## Facts already verified — do not re-derive these

Each was checked against this tree. Trust them; re-verify only if something contradicts
one.

| Fact | Evidence |
|---|---|
| The interactive-HTML build pattern to mirror | `docusaurus/course-src/build.sh` — concatenates `_base.html` + `modules/*.html` + `_footer.html` into `static/`, invoked by the `prebuild`/`prestart` npm scripts |
| Modules are **`.html`** fragments, not `.js` | `build.sh` globs `"$SRC/$name"/modules/*.html`; each fragment carries its own `<script>` block |
| Build output is gitignored, pattern established | `docusaurus/.gitignore:13-15` already lists `/static/course/`, `/static/course-advanced/`, `/static/course-assets/`. You must add `/static/dojo/` |
| The renderer to reuse | `examples/ag-ui/ag-ui-eventsource-viewer/index.html` — 499 lines, zero dependencies, consumes `/agui/v1/stream` via `EventSource` |
| The recorder **does not** persist SSE frames | `examples/ag-ui/ag-ui-eventsource-viewer/tools/record-demo.mjs` drives Playwright and pipes screenshots to ffmpeg. Frame capture is new work (FR-4) |
| Allow-list source of truth | `GENERATIVE_UI_COMPONENTS`, enforced at `src/cli_agent_orchestrator/services/agui/base.py:339` |
| Body fields the surface strips | `_BODY_FIELDS = frozenset({"delta","content","message_body","stdout"})` at `services/agui/base.py:28` |
| Navbar registration idiom for a static page | `docusaurus/docusaurus.config.ts` uses `href: 'pathname:///course/index.html'` |
| Blog author gate is real | `onInlineAuthors: 'throw'`; `blog/authors.yml` registers only `cao-maintainers`, `haofeif`, `fanhongy`, `sujoydc`. Not needed for PR 1 (no blog post), but do not add one without registering |

## Three corrections already made — do not regress them

The spec was revised after grounding against the code. If you find yourself doing any of
these, you are undoing a decision:

1. **Do not iframe or copy the existing viewer.** Two hand-maintained copies will drift.
   `dojo-src/` becomes the single source, and
   `examples/ag-ui/ag-ui-eventsource-viewer/index.html` is *generated from the same
   parts*.
2. **Do not hand-write the trace fixture.** It must come from a real recorded run
   (FR-4). A fabricated fixture makes the page a mock-up that asserts its own
   correctness.
3. **Do not give the Dojo its own list of component names.** Dispatch on whatever
   component arrives with a generic fallback renderer, so the server stays
   authoritative (FR-6). There is a guard test for this — do not weaken it.

## Sandbox constraints — read before planning

If you are running in a web sandbox or any environment without a full local CAO install,
**tasks 1.1 and 1.2 may not be completable**, because capturing a real fixture needs a
running `cao-server` with `CAO_AGUI_ENABLED`, plus Playwright's Chromium and `ffmpeg`.

That is expected. Handle it like this:

- Attempt them. If blocked, **say exactly what was unavailable** and continue with
  tasks 1.4 onward, treating the fixture as a defined interface you code against.
- Use the fixture format in `design.md` (NDJSON, one AG-UI event per line, `_meta`
  header record) as the contract.
- If you must create a placeholder to make the build run, name it
  `fleet-run.example.ndjson`, mark it clearly as a placeholder in the file and in your
  summary, and **do not** let it satisfy FR-4 or land as `fleet-run.ndjson`.
- Never report the fixture work as done if you could not record it.

## Order of work, and the one dangerous step

Follow `tasks.md`. Two points of emphasis:

**Task 1.3 is RED-first.** Write the metadata-only test and confirm it *fails* against a
deliberately poisoned copy of the fixture before it passes against the real one. A test
that has never failed proves nothing.

**Task 1.6 is the dangerous one.** Regenerating
`examples/ag-ui/ag-ui-eventsource-viewer/index.html` from the shared parts modifies a
file that an existing green CI job (`AG-UI demo (shift-left recording)`) depends on. If
it breaks, the failure will look unrelated to a docs PR. Do 1.6 alone, confirm the
recorder still works, and only then continue.

## Verification — run these, do not assume

```bash
# Docs site builds and produces the artifact
cd docusaurus && npm ci && npm run build
test -s static/dojo/index.html && echo "artifact present"

# The page must open with no server at all (this is FR-3)
# open static/dojo/index.html   # or a headless check

# Repo gates that a docs change actually trips
cd .. && uv run python scripts/validate_markdown_links.py   # every new .md is in scope
uv run black --check src/ test/ && uv run isort --check-only src/ test/
uv run pytest test/ -q --no-cov -k "dojo or agui"

# Working tree must stay clean after a build
git status --porcelain docusaurus/    # must be empty -> proves /static/dojo/ is ignored
```

A note that has cost real time on this repo: **CI's `-m "not e2e"` overrides local
pytest `addopts`, so integration tests run in CI but may be deselected locally.** A green
local run can hide a red CI. Compare deselected counts, not just pass counts.

## Rules

- **Do not push, open a PR, or comment on GitHub.** Commit locally and report. Publishing
  is the human's decision.
- **Do not commit build output.** `docusaurus/static/dojo/` must be gitignored.
- **Do not touch the AG-UI service, the stream contract, or the allow-list.** This PR is
  a consumer of that contract. Any change under `src/cli_agent_orchestrator/services/agui/`
  is out of scope — except the *new test file* asserting fixture hygiene.
- **Do not bundle live mode, the agent plugin, or the blog post into this PR.** Those are
  PRs 2, 3, and 4. FR-9 makes the split normative, because
  [#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387) bundled a full stack
  and closed unmerged at +16,288 lines.
- If `git commit` fails with a husky/`core.hooksPath` error, the hook is misconfigured in
  some checkouts of this repo. Run the quality gates manually first, then
  `git commit --no-verify`, and say that you did.
- Conventional Commits for the subject line. Sign commits if the repo expects it.

## Report back with

1. Which tasks completed, and which were blocked with the exact reason.
2. The verification output — real command output, not a summary of it.
3. Anything in the spec you found wrong, with evidence.
4. Whether the fixture is real or a placeholder. State this explicitly; it is the single
   easiest thing to misreport and the most damaging.
