# Handoff — spec audit, Claude Code

**How to use:** clone `https://github.com/plauzy/cli-agent-orchestrator`, check out
`spec/docsite-dojo-claude-code-audit` — your own branch — open Claude Code, then paste
everything below the `---`. Commit findings to that branch. The shared baseline is
`spec/docsite-dojo`; diff against it.

**This is not the hardening pass.** `HANDOFF-claude-fable.md` and `HANDOFF-gemini-pro.md`
ask a reviewer to *attack five authored decisions* — a judgment exercise. This asks a
different question: **does the spec survive contact with a real environment?** It is
verification, not critique. Run the two jobs separately; they find different things.

**Why Claude Code specifically:** this audit is mostly *executable*. It needs `npm`,
Node, a browser, and a working CAO checkout. The environment the spec was written in had
none of those — no `node`, no `npm`, no `ffmpeg`, no `cmp`, no Chromium, no `cao-server` —
so every claim about what happens when the build actually runs is currently unverified.

---

You are auditing a specification for factual and executable correctness. **Do not
implement the feature.** Do not write production code. Write tests and throwaway probes
freely — that is how you audit — but the deliverable is a findings report.

## Where the spec is

`.kiro/specs/cao-docsite-dojo/` on the branch named in the preamble:

- `requirements.md` — FR-1..FR-10, NFR-1..NFR-3, CP-1..CP-5, 62 EARS acceptance criteria
- `design.md` — architecture, Properties 1-9, verification table, alternatives, risks
- `tasks.md` — 4 PRs, 45 tasks, 32 in PR 1

**`.kiro/` is gitignored here** (`.gitignore:56-59`). These files are tracked only because
they were force-added. Every edit needs `git add -f` or it silently fails to stage.

## What the feature is

A static, zero-dependency page at `docusaurus/static/dojo/index.html` rendering the AG-UI
event stream in **replay** mode (default, from a trace fixture embedded at build time) and
**live** mode (from the reader's own `cao-server`). It is a pure consumer of the stream
contract — no new route, no CAO Python imported, only new test code.

## Already verified — do not spend effort re-deriving these

Checked mechanically against the tree at commit `289d229`:

| Claim | Result |
|---|---|
| All 14 pinned `file:line` citations | **14/14 exact.** `index.html:103/137/178/216`, `agui_stream.py:91`, `base.py:28/339`, `pyproject.toml:369/404`, `ci.yml:259`, `package.json:7-10`, `.gitignore:13-15`, `record-demo.mjs:219,257,267,271` |
| Acceptance-criteria coverage | **62/62** named individually in the design's verification table |
| Property → CP mapping | Agrees with all nine `Validates:` lines; mapping is **non-positional** (P5→CP-3, P8→CP-4, P9→CP-5; P3/P4/P6/P7 design-added) |
| Dangling CP identifiers | none — CP-6..CP-9 were referenced and are now removed |
| `scripts/validate_markdown_links.py` | passes |

A caution about that table: it was produced by scripts that returned **three false
positives** before returning the truth — a parser that mis-attributed a criteria list, a
`\b` that fails on `CP-5_` because `_` is a word character, and range notation
(`FR-8.1-FR-8.4`) read as endpoints only. Treat the table as a starting point, not
gospel. If you re-derive any row and disagree, say so — you may be right.

## What only a real environment can settle — this is the audit

### A. Does the build actually work

1. `cd docusaurus && npm ci && npm run build`. Does `static/dojo/index.html` appear?
   Note: `dojo-src/` **does not exist yet** — the spec is unimplemented. So the honest
   test is whether the *specified* `build.sh` design is realisable. Write a minimal
   `dojo-src/` and prove the pipeline, or state precisely why it cannot work as specified.
2. NFR-3 claims escaping + extraction + comparison stays inside "concatenation and copying
   only" using `sed` and `cmp`. **Is `cmp` present in the CI images this repo uses?** It
   was absent from the authoring environment. If it is not universally available, NFR-3's
   adjudication rests on a tool that may not be there.
3. `git status --porcelain docusaurus/` after a build must be empty (FR-1.5). Confirm the
   `/static/dojo/` gitignore entry is sufficient.

### B. The fixture-embedding round trip — the claim most likely to be wrong

`design.md` specifies embedding the NDJSON fixture in
`<script id="dojo-fixture" type="application/x-ndjson">` and escaping six sequences:

| In fixture | Embedded as |
|---|---|
| `</script` | `<\/script` |
| `<script` | `\u003cscript` |
| `<!--` | `\u003c!--` |
| `-->` | `--\u003e` |
| U+2028 | `\u2028` |
| U+2029 | `\u2029` |

**Test this empirically, and test this specific ambiguity.** Property 6 claims the reverse
transform recovers the committed fixture *byte for byte*. But the forward map is not
obviously injective: if a source fixture **already contains** the literal characters
`<\/script` (a legal JSON solidus escape), the forward `sed` will not touch it — yet the
reverse transform `<\/script` → `</script` would corrupt it. Construct that fixture and
find out whether the round trip holds. If it does not, Property 6 as stated is false and
either the escaping or the property needs changing.

Also confirm empirically, in a real browser, that:
- an unrecognised script `type` is genuinely never executed;
- `textContent` on that element returns the raw bytes without HTML-entity decoding;
- a fixture containing every one of the six sequences survives to `JSON.parse` intact.

### C. Does `file://` actually work

FR-3 and NFR-1 require the built page to open from `file://` with no server, no network,
and render the fixture. The whole build-time-embedding decision exists because `fetch` is
blocked on `file://` origins. Verify the *positive* claim, not just the negative one:
open the page over `file://` and confirm it renders with zero network requests after
document load. Report the browser and version.

### D. Is the test strategy realisable

1. `hypothesis>=6.0` is claimed available (`pyproject.toml:369`). Confirm the three
   specified Python test files can actually be written and run:
   `test/examples/test_dojo_fixture_{is_metadata_only,prefix_validity,provenance}.py`.
   Note CAO requires Python 3.10+; confirm the suite runs.
2. `@playwright/test` 1.56.1 is claimed in
   `examples/ag-ui/ag-ui-eventsource-viewer/tools/package.json`. Confirm it installs and
   that a spec can drive a `file://` URL. Playwright and `file://` have historically been
   awkward — if it cannot, FR-5.3's "assert against build output over `file://`" fails and
   the verification strategy needs rework.
3. `window.__dojo` is the seam every browser property depends on. Prove `page.evaluate()`
   can drive it usefully — in particular that Property 1 (drive the same sequence through
   two transports in one page and compare final state) is expressible.
4. **CI's `-m "not e2e"` overrides local `addopts`** (`-m 'not e2e and not integration'`,
   `pyproject.toml:404`). Compare *deselected* counts, not just pass counts. A green local
   run can hide a red CI.

### E. The riskiest task, tested before it is done

Task 1.19 regenerates `examples/ag-ui/ag-ui-eventsource-viewer/index.html` from shared
parts. The currently-green `AG-UI demo (shift-left recording)` job (`ci.yml:259`) drives
that page and depends on `#components`, `.gcard`, `.gtype`, `#components iframe`, and the
"connected" status text (`record-demo.mjs:219,257,267,271`).

Run the recorder against the page **as it stands today** and capture a baseline. That
baseline is what makes 1.19 safe. Report whether the recorder runs at all in your
environment — it needs `cao-server` with `CAO_AGUI_ENABLED`, Chromium, and `ffmpeg`.

### F. Internal consistency, re-derived independently

Do not trust my table in the section above. Independently check: every acceptance
criterion has a verification route; no requirement contradicts another; no property's
generator domain is narrower than the criterion it claims to validate; every task's
dependency-graph wave is consistent with its stated prerequisites; the two documented
behavioural defects in the existing viewer are real (`ALLOWED_COMPONENTS` gating dispatch,
`applyPatch` mutating in place and returning mid-iteration).

## Constraints

- **Do not expand `GENERATIVE_UI_COMPONENTS`** — owned by
  https://github.com/awslabs/cli-agent-orchestrator/issues/582.
- **Do not change anything under `src/cli_agent_orchestrator/services/agui/`.** New test
  files only.
- **Do not push to `awslabs/cli-agent-orchestrator` and do not open a pull request there.**
  This work lives on the fork, `plauzy/cli-agent-orchestrator`, on your audit branch.
- If `git commit` fails with a husky or `core.hooksPath` error, run the gates manually,
  then `git commit --no-verify`, and say that you did.
- Conventional Commits.

## Output contract

1. **Verified / falsified table.** One row per claim in sections A-E. State
   `holds` / `fails` / `could not test`, with the command and its real output. Paste output;
   do not summarise it.
2. **Defects**, severity-ordered. Classify each as *factually wrong* (a claim about the
   tree or a tool that is untrue), *unrealisable* (specified but cannot be built as
   described), or *unfalsifiable* (asserted but nothing can check it). Give the fix.
3. **The round-trip question in section B**, answered definitively with the constructed
   adversarial fixture.
4. **What you could not test, and exactly which prerequisite was missing.** Be specific:
   "no `ffmpeg`" beats "environment limitations".
5. **Confidence**, per section.

If you edit the spec, keep edits surgical, preserve FR/NFR/CP and Property numbering, and
list every file and line touched. Remember `git add -f`.

## The one thing not to do

Do not report a check as passing because it looks right in the document. Every finding in
this audit should be backed by output from a command you ran. The spec's own FR-5 exists
because "an unverified claim on a docs site is worse than no claim, because it is quoted" —
the same standard applies to an audit of it.
