# STATUS — Agent Plugin lifecycle skills, dogfood package, and blog post

## Checkpoint 2026-11-02

Facts verified by the supervisor at 11:17 on 2026-11-02, recorded before a fleet restart.

- **Local HEAD:** `7ef0c0efe38331665bb89945ae2f8cd21a601e4a`, `%G?` = G: "docs(1153): drop the external creator-skill dogfood (OQ-17), per the user's 2026-11-02 decision". Its parent is `e92a97fc` (#1152).
- **The OQ-17 "dropped" commit exists (`7ef0c0ef`).** Its gates passed in a clean detached worktree: links, black, isort, ruff, mypy ratchet (174), `sync_skills --check`, and 13.8 under zsh and bash, all exit 0.
- **It is NOT pushed.** `origin/feat/agent-plugin-lifecycle` is still at `e92a97fc`.
- **Uncommitted:** only the untracked spec working files. These are `STATUS.md`, `tasks.md`, `research.md`, `blog-outline.md`, `review-1/2/6/7/8.md`, `t8-axis1/2.md`, `t3-overlimit-experiment.md`, `audit-report.md` and `audit-raw.txt`. They stay untracked by design, and there are no tracked changes.

**Exact next step.** After the restart, run the cold-start script (`fleet-up.sh`). Then the supervisor:

1. checks #1200's PR body for any "follows separately in harness-oss" wording, and fixes it;
2. pushes `7ef0c0ef` to origin only (`git push origin feat/agent-plugin-lifecycle`), never to upstream;
3. confirms CI is green on #1200, and posts the single PR checklist comment if it has not been posted yet;
4. adds "Closes #1152" to #1200's body.

**Open:**

- **OQ-1b:** the maintainer's call. It gates only the merge.
- **CI dogfood coverage of the third package via `run.sh`:** the user's decision. It is not in scope.


## PUSHED as draft #1200

**Pushed by the supervisor as draft PR #1200 from plauzy's fork. It is a draft.** The new commit below is **not pushed**; pushing it is the supervisor's job.

- **Local head:** `7ef0c0efe38331665bb89945ae2f8cd21a601e4a` (`G`, plauzy, exactly the two trailers): "docs(1153): drop the external creator-skill dogfood (OQ-17), per the user's 2026-11-02 decision". It changes `requirements.md` and `design.md` only.
- **OQ-17 is DROPPED** (the user, 2026-11-02; `/Volumes/workplace/open-source/.agents/plans/agent-plugin-lifecycle/decisions-oq17-n11.md`, "Update 2026-11-02"). No harness-oss work is planned, and #1200 must not promise it. The creator skill is not dogfooded on an external package, and the audit skill is still exercised on CAO's own packages. Requirement 15 is cut to the decision, its reason, and three criteria. The charter deviation stands.
- **Gates at `7ef0c0ef`**, run in a clean detached worktree (`/tmp/gate-oq17`, removed afterwards), under bash, with `UV_PROJECT_ENVIRONMENT=/tmp/ci-venv-1153`: links 0; black 0; isort 0; ruff 0; mypy ratchet 0 (174 errors, matching the baseline); `sync_skills.py --check` 0. Requirement 13.8's block, from `git show HEAD:` at `requirements.md:500-520`: zsh 0, bash 0.
- **The branch history was rewritten upstream of this seat**, before this commit. It was rebased onto `upstream/main` `ab9bbaab`. Old → new, matched by subject:
  - `6bcd9a14` → `c71f6d05` (the spec commit, `requirements.md` and `design.md`)
  - `da8a6315` → `08d0c8d3` (merge of `upstream/main`)
  - `58c9bbe1` → `897d2e92` (style: black and the two `# type: ignore[call-arg]`)
  - `80704d6f` → `e92a97fc` (#1152, `--keep-committed-pin`)

  The wave commits `c1704528` … `09ef4462` keep their shas, and all are still ancestors of `HEAD`. The old shas still resolve as objects, but they are no longer on the branch.
- **PR checklist comment:** the items in "PR checklist comment" below still need to be posted as **one** comment on #1200, if they have not been already. **That is the supervisor's job.**
- **#1152 (`--keep-committed-pin`)** is in the branch as `e92a97fc`.

Updated by the author seat on 2026-11-02. Before this update the head was recorded as `58c9bbe1`, with the commits `6bcd9a14`, `da8a6315` and `58c9bbe1` since `09ef4462`; those shas are now superseded as listed above.

## READY TO PUSH (history: the state before the push)

**Not pushed. The push and the draft PR are the supervisor's, after the user's approval.**

Branch `feat/agent-plugin-lifecycle`, worktree `/Volumes/workplace/open-source/cao-agent-plugin-lifecycle`.
`HEAD` is `09ef446227de6c7dd161bf29bf31c2dc7ae8b24c`, on base `upstream/main` `2731179845f9bd332a22e72fa44cc55345561c99`.
Written 2026-11-01 by the author seat, which edited only this file in this step. Everything below this
section is history.

### Commits, oldest first

From `git log --reverse --format='%H|%G?|%an|%s' upstream/main..HEAD`, run by this seat. Every commit is authored by `plauzy`.

| sha | `%G?` | Task | Subject |
|---|---|---|---|
| `c17045289260ca2fdc458579181adaa4aa54fabf` | G | T1 | feat(skills): add cao-agent-plugin-creator for authoring an Agent Plugin from scratch |
| `bf817a90899cbc84173bf225ea7acbdee6420354` | G | T2 | feat(skills): add cao-agent-plugin-audit with a bundled Agent Plugin validator |
| `5b1dbc818eea17a5cffed4afec9e3fb09ff71584` | G | T4 | build(skills): ship cao-agent-plugin-creator and cao-agent-plugin-audit in the wheel |
| `fa2240ef1e1d11a4e1fda3c6c477bdb00a2fe5c8` | G | T5 | feat(agent-plugin): add the cao-agent-plugin-lifecycle package |
| `a2953880c1c6a241ece4f7962fbf2dedd74a3ce6` | G | T7 | docs(agent-plugins): document the cao-agent-plugin-lifecycle package and its skills |
| `40ed5b1e83fa62bee5c0eb26a8d1255638cb121d` | G | T2-fix | fix(skills): mark the audit skill's name-rule admission as inferred and tighten its validator |
| `dd36f44f0cd70c91c7fb98706eb4ee125f513d87` | G | T1-fix | fix(skills): harden the creator skill's limits snippet and correct its evals |
| `32dde12f0b3dddae4a990c59d7e7a7750d3e5472` | G | T4-resync | build(skills): re-sync the shipped mirror of the two Agent Plugin skills |
| `644696c6daf2a902064061a60c0e523144ea425b` | G | T5-rebuild | fix(agent-plugin): rebuild the lifecycle package and tie its tests to PACKAGES |
| `09ef446227de6c7dd161bf29bf31c2dc7ae8b24c` | G | T7-fix | docs(agent-plugins): say the lifecycle package's self-audit was a recorded run, not a CI gate |

T3 and T6 make no commit; their reports are untracked in this directory.

### Gates, each with its command and latest exit status

Gates 1–9 are the ones `design.md`'s runnable-forms block defines. Runs marked "this seat" were made at
`09ef4462` immediately before this section was written. In those runs `uv run` was given `--frozen`, so
`uv.lock` could not be rewritten; gate 1 is the exception, because `uv run --script` takes no lockfile.

| Gate | Command | Latest result |
|---|---|---|
| 1 skill limits | `uv run --script skills/cao-agent-plugin-audit/scripts/validate_agent_plugin.py --skills-dir skills/` | **exit 0**, `summary: 0 fatal, 0 skipped, 0 limit, 0 warning, 0 advisory; exit 0`. This seat, at `09ef4462`; the supervisor also saw exit 0 |
| 1, package mode (axis 2's condition) | the same script, run with a package path, against `./agent-plugin/cao` and `./agent-plugin/cao-agent-plugin-lifecycle`, gate on and gate off | **exit 0** for both packages, `summary: 0 fatal, 0 skipped, 0 limit, 0 warning, 1 advisory; exit 0`. Supervisor, at `09ef4462` |
| 2 mirror drift | `uv run python scripts/sync_skills.py --check` | **exit 0**, `OK: 16 shipped skills are in sync.` This seat and the supervisor, at `09ef4462` |
| 3 schema pin | `uv run python scripts/vendor_agent_plugins_schemas.py --check` | **exit 0**, `OK (local): 2 vendored Agent Plugins 1.0.0 schemas match PIN.json`. This seat, at `09ef4462` |
| 4 package drift and conformance | `uv run python scripts/build_agent_plugin.py --check` (`make check-agent-plugin`) | **exit 0**, `OK: agent plugin packages in sync and loadable at the version they were built at, 2.5.3 (cao, cao-contributor, cao-agent-plugin-lifecycle). pyproject.toml is now at 2.5.4…`. This seat and the supervisor, at `09ef4462` |
| 5 validate each package | `CAO_AGENT_PLUGINS_ENABLED=1 uv run cao plugin validate ./agent-plugin/<pkg>` | **exit 0** for `cao`, `cao-contributor` and `cao-agent-plugin-lifecycle`. This seat, at `09ef4462` |
| 5b negative control | `CAO_AGENT_PLUGINS_ENABLED=1 uv run cao plugin validate ./test/agent_plugins/fixtures/corpus/manifest-missing-name` | **exit 1**, as required: `FATAL §5.2 manifest.invalid [plugin.json]: 'name' is a required property`. This seat, at `09ef4462` |
| 5c gate-off demonstration | `env -u CAO_AGENT_PLUGINS_ENABLED uv run cao plugin validate ./agent-plugin/cao` | **exit 1**, 0 bytes on stdout, JSON parse fails, as required. This seat, at `09ef4462` |
| 6 markdown links | `uv run python scripts/validate_markdown_links.py` | **exit 0**. This seat, at `09ef4462`, after this edit |
| 7 targeted tests | `uv run pytest -q -p no:cacheprovider test/agent_plugins/test_packages.py test/agent_plugins/test_schema_pin.py test/agent_plugins/test_conformance_corpus.py test/test_cao_contributing_skill_accuracy.py`, under `env -u TMUX TMUX_TMPDIR="$(mktemp -d)"` | **exit 0**, `220 passed`. This seat, at `09ef4462`. The supervisor separately ran `test_resolver.py` plus `test_packages.py`, isolated: 85 passed |
| 8† trigger evals | a local measurement, not a gate | **Not run**, and no criterion depends on it |
| 9 docs site build | `cd docusaurus && npm ci && npm run typecheck && npm run build` | **Not run locally**, at any sha. It is enforced by `gh-pages.yml` on `pull_request` (`P-62`) |
| Existing packages byte-unchanged | `git diff --quiet 27311798 HEAD -- agent-plugin/cao agent-plugin/cao-contributor` | **exit 0**. Supervisor, at `09ef4462` |
| Scope end blocks | hazard 4's end block, one per task | `t6`: `scope OK: t6`, exit 0, under zsh and bash (this seat, before T6 finished, at `fa2240ef`). `t7`: `scope OK: t7`, exit 0, under zsh and bash (this seat, before T7's commit `a2953880`). `t1`–`t5`, and the five fix commits: run by the implementer seats; their results are in those seats' callbacks, and **this seat did not re-run them** |
| **13.8, the pre-push gate** | Requirement 13.8's block, `requirements.md:505-525`, extracted by line range (21 lines) | **zsh exit=0, bash exit=0**: "all commits in upstream/main..HEAD signed (G) by plauzy with exactly the two trailers". Supervisor, at `09ef4462`; this seat re-ran it at `09ef4462` with the same result |
| Tree state | `git log --oneline -1`; `git status --porcelain --untracked-files=all` | `09ef4462`; nothing outside `docs/issues/1153-agent-plugin-lifecycle/`. Supervisor |

**Full suite.** Run **once**, in shards, at **`a2953880`**, with tmux isolated. Coverage was **92%**
against a gate of 80, exit 0. **73 nodes failed, none under `test/agent_plugins/`, and all 73 fail the
same way at the base `27311798`.** The causes are: the agui extra not installed (58), the otel extra not
installed (9), the rust toolchain (1), an AF_UNIX path length (1), and order-dependent `wiki_lint` tests
(4). **The full suite was NOT re-run after the five fix commits** (`40ed5b1e` to `09ef4462`). After them,
only the task must-pass blocks and the agent-plugin tests were run.

**The seven tmux-sensitive tests** (Wave 2's list) fail at the base `27311798` without isolation and pass
with it; this is now shown at the base sha. They are a pre-existing upstream hermeticity defect. **A
separate upstream issue is recommended and not filed.**

**One flaky run.** During the T5 fix round's must-pass block,
`test_resolver.py::TestGitSource::test_clone_records_the_resolved_commit` failed once. It then passed
alone three times and in a re-run of the block. **The suspected cause, concurrent pytest temp-dir
pruning, is inferred, not traced.**

### T8 verdicts

- **Axis 1** (correctness, security, evidence honesty and test honesty): **APPROVE**, pinned to `09ef4462`.
- **Axis 2** (logic and spec conformance): **APPROVE**, pinned to `09ef4462`. Its condition was a package-mode run at this HEAD. **It is met:** the supervisor ran the validator against `agent-plugin/cao` and `agent-plugin/cao-agent-plugin-lifecycle`, gate on and gate off, and every run gave exit 0 (gate table above).
- **The priority question: mechanical, not a wrapper.** Both reviewers cite `validate_agent_plugin.py:68-71` (the constants) and `:278-285` (the checks). **Those line numbers match the file at `bf817a90` (T2).** Since `40ed5b1e` the same code sits at `:77-80` and `:299-309`, and it is unchanged. Quoted at `09ef4462`:
  - `:77-80`: `SKILL_NAME_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")`, `NAME_MAX = 64`, `DESCRIPTION_MAX = 1024`, `BODY_MAX = 500`
  - `:302`: `if not SKILL_NAME_RE.fullmatch(name):`
  - `:304`: `if len(name) > NAME_MAX:`
  - `:306`: `if len(description) > DESCRIPTION_MAX:`
  - `:308`: `if body_lines > BODY_MAX:`

  Each of these raises a `LIMIT` finding. Earlier rounds are recorded in `t8-axis1.md` and `t8-axis2.md`.

### harness-oss

**harness-oss branch: none; OQ-17 dropped by the user, 2026-11-02. harness-oss untouched at c422584.**

### User decisions

Resolved by the user on 2026-11-01, after review by the advisor and the devops agent; recorded verbatim in `/Volumes/workplace/open-source/.agents/plans/agent-plugin-lifecycle/decisions-oq17-n11.md`:

- **OQ-17 — DROPPED (the user, 2026-11-02).** This supersedes option (c) of 2026-11-01. No harness-oss work is planned, the creator skill is not dogfooded on an external package, and the charter deviation stands (Requirement 15).
- **N-11 — RESOLVED, option (b).** The vocabulary rules are rewritten generically, with no product name; every banned phrase is kept word for word except constraint 2's, whose phrase contained the name (see the note below).

Still open:

- **OQ-1b:** the maintainer's question, whether to reverse, narrow or uphold #573's D4. It **gates the merge only**, not the push or the draft PR.
- **CI dogfood coverage:** whether to extend `run.sh` so the CI dogfood job covers the third package (`P-67`, Requirement 8.12). Until then the claim is "gated in CI by `make check-agent-plugin`".

**Spec files changed after T8's review, for these two decisions only.** `requirements.md`, `design.md` and `tasks.md` were edited on 2026-11-01 to record OQ-17 (c) and apply N-11 (b); no criterion outside Requirements 15 and 16, the decisions tables and the traceability row changed. Requirement 13.8's block moved from `requirements.md:505-525` to `:502-522` (same 21 lines). The T8 reviews were pinned to the code at `09ef4462` and did not see these spec edits. **N-11 constraint 2:** the banned phrase "renders in any AG-UI or [product name] client" could not be kept word for word, because it is the phrase that carried the product name. It is now "renders in any AG-UI-compatible client", as the user suggested, plus "nor that it renders in every client built on a third-party UI framework", so the rule still forbids the claim the old wording named.

### PR checklist comment

To be posted as **one** comment on the draft PR, not as separate issues:

- [ ] **T8A-R-9 / T8B-R-4:** the audit flattens CAO's severities to WARNING.
- [ ] **T8A-R-10 / T8B-R-2:** the creator skill's snippet exits 1 on a YAML error or on frontmatter that is not a mapping.
- [ ] **T8A-R-12:** the credential heuristic under the gate.
- [ ] **T8B-R-3:** the "discovered skills:" label.
- [ ] **T8B-R-5:** `tasks.md:304`'s dependence on the gate.
- [ ] **T8A-R-6 / T8B-R-6:** rows of the exit table.
- [ ] **T8A-R-14 / T8B-R-1:** the docs pin to `fa2240ef`'s audit. It was re-run at `09ef4462` with the same summary.
- [ ] **T8B-N-5:** the double FATAL, and the strip mismatch.
- [ ] **T8B-N-6:** README template text inherited by the new package.
- [ ] **T8B-N-8:** T4's `diff -r -x __pycache__` criterion.
- [ ] The seven non-hermetic tmux tests: recommend a separate upstream issue.

### PR body

**The PR body must lead with the fact that it revisits #573's D4** (go-ahead, OQ-1; `requirements.md`
§ "Relationship to #573 decision D4" is the source text, and Requirement 14 stays in force). The PR is a
proposal a maintainer can decline. Under OQ-1b, if D4 stands, the PR is withdrawn unmerged.

---

> **History below.** The checkpoint sections that follow record the path to this state and are not current.

> **(History) CHECKPOINT 2026-11-01 was the state before READY TO PUSH. Read it first, starting with the latest "Wave" section.** It records
> steps 2 and 3 of the 2026-10-30 checkpoint's "The exact next step", then review 6's fix list, and
> supersedes that checkpoint's tree-state table. Everything below it is history. **Nothing is READY:
> the spec is cleared by review 8; waves 1–4 are done (commits T1, T2, T4, T5, T7; T3 and T6 are untracked
> reports). The spec was fixed between waves 4 and 5. T8, the independent reviews, is next; nothing is pushed.
> NOT READY TO PUSH.**

## Checkpoint 2026-11-01

Steps A–D of the resume brief, done in the worktree on `feat/agent-plugin-lifecycle`. **No commit, no
push**, and the specification files are still untracked. The three specification files are **frozen
for review 6** at the hashes below.

### Wave 4 note — spec fixed between waves 4 and 5 (current; read this first)

Recorded by the author seat between waves 4 and 5. Only the untracked spec directory was edited:
`git status --short` shows only `?? docs/issues/1153-agent-plugin-lifecycle/`, and `git diff --quiet
HEAD` exits 0. The supervisor verified T7 `a2953880` (G, 3 files, +28/-4). **NOT READY TO PUSH.**

1. **The stale `test_packages.py:309` citations, recorded as `P-77`.** `TestPackagesInstallThroughTheRealPipeline` moved to `:345` when T5 (`fa2240ef`) extended the file; `git show fa2240ef:test/agent_plugins/test_packages.py | grep -n 'class TestPackagesInstallThroughTheRealPipeline'` → `345:`. **Updated, each naming both positions:** `P-63`, `design.md`'s install-smoke-test paragraph, T5's list of two-package sites, and T6's description and criterion. The report's finding is marked resolved. **Kept as historical:** line numbers of sites T5 edited, in `P-63`, `P-69` and 8.11, which stay pinned to `27311798`.
2. **T7's spec finding, recorded as `P-78`.** The per-token whitespace check is withdrawn. Requirement 10.5 and T7's criterion now use the repository's own phrase-level rule, `_UNQUALIFIED_PLUGIN` (`test/agent_plugins/test_naming_migration.py:74`, re-read), with `_prose_of`'s stripping (`:60-70`). T7 now carries a runnable check block: it reads the rule out of the guard file with `ast` so it cannot drift, and fails on any occurrence the commit adds.
   - Run as published, under zsh and bash, it exits **0** on `a2953880`, reporting "new unqualified occurrences: 0".
   - In throwaway commits it exits **1** on a planted "This plugin is planted…" sentence and **1** on a mixed line ("An agent plugin … bare plugins …"). It exits **0** on qualified-only prose and **0** on wrapped inline code and links.
   - **Its first draft was wrong, and running it showed that.** It stripped code line by line, so T7's `cao plugin validate` span, which wraps across a line, was flagged (exit 1 on `a2953880`). It now strips the whole text in `_prose_of`'s order, keeping newlines.
   - For contrast, the old per-token check on the same commit printed `plugins,`, `plugin`, `plugin`, `plugin`.
3. **T6's misreading hazard is stated plainly.** T6's description gained "How to read `audit-raw.txt`": the audit step runs with the gate unset, so `cao plugin validate: not run` is the skill's own optional wrapper, and CAO's verdict comes from step 2. `audit-report.md` says the same at the top of its captured-output section, and its quoted raw lines are unchanged. T6's command block, re-run as published (zsh), exits **0** with `audit exit=0` and `validate exit=0`, and `audit-raw.txt` is byte-identical.

**Next: T8**, the two independent read-only reviews (wave 5).

### Wave 4 — T7 done; recorded after T7's commit

Recorded by the author seat after T7's end block passed and its commit was made, so this edit is
outside T7's scope window. **NOT READY TO PUSH:** wave 5 (T8, the independent reviews) remains, and
nothing is pushed.

**T7: `a2953880c1c6a241ece4f7962fbf2dedd74a3ce6`**, `G`, `plauzy <4451274+plauzy@users.noreply.github.com>`.
Trailers, from `%(trailers:unfold,only)`: exactly `Co-authored-by: plauzy <4451274+plauzy@users.noreply.github.com>`
and `Co-authored-by: Kiro Agent <244629292+kiro-agent@users.noreply.github.com>`. Staged by path:
`CODEBASE.md`, `docs/skills.md`, `docs/agent-plugins.md`. The message does not mention tmux.

**Requirement 13.8's block**, copied verbatim from `requirements.md:503-523`, exits **0** under zsh and
under bash over all five commits (`c1704528`, `bf817a90`, `5b1dbc81`, `fa2240ef`, `a2953880`).

**What T7 changed:**

- **`CODEBASE.md`:** the `agent-plugin/` row names `cao`, `cao-contributor` and `cao-agent-plugin-lifecycle`.
- **`docs/skills.md`:** the builtin-skills table has rows for `cao-agent-plugin-creator` and `cao-agent-plugin-audit`.
- **`docs/agent-plugins.md`, "CAO's own packages":**
  - a row for the third package, keyed to "an author";
  - the intro no longer states a package count;
  - "Every package is generated…";
  - a sentence that the third package ships no `mcp.json`.
- **`docs/agent-plugins.md`, "Verified by dog-fooding":** a paragraph saying the recording installs only `cao`, and that the third package is **gated in CI by `make check-agent-plugin`** and **audited by a skill it carries**. It gives the audit command, its summary line and exit `0`, and CAO's `loadable: true`, exit `0`. **It does not claim the package is "dogfooded in CI"** (Requirement 8.12).

**Runs:**

- T7's start block, hazard 4 with id `t7`, ran before any edit → `stamp taken: /tmp/cao-apl-t7.stamp`, exit 0.
- **T7's must-pass block, unchanged,** run under `env -u TMUX TMUX_TMPDIR="$(mktemp -d)"`: zsh **0** and bash **0**, `29 passed`. The docs test is green.
- The same block **without** isolation: **0**, `29 passed`.
- `test/agent_plugins/`, checked because T7's edits touch documents that its tests read:
  - under the same isolation: **1226 passed, 2 skipped**, exit 0;
  - **without isolation**: **7 failed, 1219 passed**, exit 1. The 7 are exactly the tmux-dependent tests recorded in Wave 2, and no other test failed.
- T7's end block, before the commit → **`scope OK: t7`**, exit 0, zsh and bash. It warned, as a warning only, about gitignored `.hypothesis/` files written by the test run.
- The documented commands, re-run:
  - the audit → `summary: 0 fatal, 0 skipped, 0 limit, 0 warning, 1 advisory; exit 0`, exit 0;
  - `cao plugin validate --json` → `loadable True findings []`, exit 0. The package last changed at `fa2240ef`.
- `uv run --frozen python scripts/validate_markdown_links.py` → exit 0.

**T7 criteria, with evidence:**

- **The `CODEBASE.md` row names all three packages, and the third name equals the manifest name.** Both strings were extracted and compared: `True`.
- **`docs/skills.md` names both skills.** `grep -c 'cao-agent-plugin-creator\|cao-agent-plugin-audit' docs/skills.md` → `2`.
- **"CAO's own packages" names both skills, and "Verified by dog-fooding" cites a command with its exit status.** Met.
- **The links validator exits 0.** Met.
- **The unqualified-"plugin" check, run per token as published:**
  - The `grep -oh '\S*plugin\S*'` tokens on lines T7 added that the published regex rejects are listed as **exceptions**: `plugins,` and `plugin` in "agent plugins," and "an agent plugin". Each is qualified by the preceding word, but whitespace tokenization separates the two words.
  - The other two are `plugin` inside the backticked command `cao plugin validate`.
  - The repository's own phrase-aware rule (`_UNQUALIFIED_PLUGIN`, `test/agent_plugins/test_naming_migration.py`), applied to the added prose, finds **no** unqualified occurrence. The isolated `test/agent_plugins/` run, which includes that guard, passed.
  - **The published criterion is not satisfiable as written.** Its per-token tokenization can never match `agent plugin` with a space. Across the three files the non-matching token totals are 13 → 13, 15 → 16 and 135 → 137 against `HEAD^`. The entire increase is the exceptions above.
- **No new M1 claim.** A grep of the added lines for M1 and for "dogfooded in CI" finds nothing.
- **`git diff --quiet HEAD -- docusaurus/sidebars.ts` exits 0.** Met.
- **The orphaned severity rows (`docs/agent-plugins.md:304-305` at base) are unchanged.** The diff hunks are only at `@@ -484`, `@@ -518` and `@@ -709`.
- **No count of lines, files, tests or commits is introduced.** A grep of the added lines finds none. The removed "two agent plugins" count was replaced with wording that states no count.
- **Scope.** Start printed the stamp; end printed `scope OK: t7`.

`git status --short` after the commit: `?? docs/issues/1153-agent-plugin-lifecycle/` only.

### Wave 3 — T6 done; recorded between waves 3 and 4

Recorded by the author seat after T6's end block passed, so this `STATUS.md` edit falls outside T6's
scope window (hazard 4's rule 1). T6 makes no commit: both of its files are untracked. `git status
--short` = `?? docs/issues/1153-agent-plugin-lifecycle/` and `git diff --quiet HEAD` → 0.

**T6 verdict: CLEAN; nothing blocks T7.** The `Dogfood_Package` is **audited by** a skill it carries:
0 fatal, 0 skipped, 0 limit, 0 warning, and 1 advisory, the description/skills listing that 2.12
requires. **audit exit=0.** CAO's own verdict is `"loadable": true`, `"findings": []`, validate exit=0.
The same validator, run on a `mktemp -d` over-limit fixture, raised two `LIMIT` findings and exited 1,
while `cao plugin validate` on that fixture gave `loadable True findings []`, exit 0. That cites T3, and
shows the audit can fail. **No finding needs a T5 follow-up.**

| Output | Path | Lines |
|---|---|---|
| Report | `docs/issues/1153-agent-plugin-lifecycle/audit-report.md` | 149 |
| Captured audit output | `docs/issues/1153-agent-plugin-lifecycle/audit-raw.txt` | 9 |
| Outcome | `workflow_outcomes` row `d808da17-8833-4e4e-93a7-73dd2617b44b`, found by id (exactly one row); `launch_linked: true` | — |
| Lesson | memory key `pair-self-audit-with-failing-fixture`, agent scope `oss-docs`, `feedback`, ending `Applies when: dogfooding an audit or validator skill against the package that ships it.` | — |

**Runs, every block copied verbatim from `tasks.md`:**

- T6's start block, run with `zsh` → exit 0, `stamp taken: /tmp/cao-apl-t6.stamp`.
- T6's command block, run 1 with `zsh` → **exit 1** at step 3, `missing from report: …`. That was intended: the report is written only after the audit, which is T6's defect 1.
- After the report was written: run 2 (`zsh`) → **0**; run 3 (`bash`) → **0**; a final `zsh` run on the finished report → **0**. Each run printed `audit exit=0` and `validate exit=0`, and `audit-raw.txt` was byte-identical across all four runs (`cmp`).
- T6's end block → **`scope OK: t6`**, exit 0, under `zsh` and under `bash`.

**Findings reported to the supervisor, not fixed (spec-side only):**

1. T6, `design.md` and `P-63` cite the install smoke test at `test/agent_plugins/test_packages.py:309`. Since T5 it is at `:345`. The report cites both.
2. In the block's audit step the gate is unset, so the skill's own CAO wrapper prints `cao plugin validate: not run`. The CAO verdict comes from step 2. That is correct as written, but it is easy to misread in `audit-raw.txt` alone.

### Wave 2 — done; recorded between waves 2 and 3

Recorded by the author seat between waves, with no other seat writing. Only `STATUS.md` was edited in
this step, and the spec hashes are unchanged from the wave-1 freeze (`82ab558e` / `6a072700` / `65f182d3`).

| Task | Result |
|---|---|
| **T4** — wheel shipping | **`5b1dbc818eea17a5cffed4afec9e3fb09ff71584`** |
| **T5** — dogfood package | **`fa2240ef1e1d11a4e1fda3c6c477bdb00a2fe5c8`** |

Seen by this seat: `git log --format='%h %G? %an' upstream/main..HEAD` lists `fa2240ef`, `5b1dbc81`,
`bf817a90`, `c1704528`, all `G plauzy`. `git diff --quiet 27311798 HEAD -- agent-plugin/cao
agent-plugin/cao-contributor` exits 0. The supervisor verified that all four commits carry exactly the
two trailers and that `make check-agent-plugin` reports OK at 2.5.3 for all three packages; this seat
did not re-run those.

**T5's build, as Requirement 8.13 requires:** it ran in-process at `2.5.3`, and `make agent-plugin` was
never run. Both existing packages are byte-unchanged: the `git diff --quiet` above exits 0 for
`agent-plugin/cao` and `agent-plugin/cao-contributor`.

**Tmux isolation record: a pre-existing upstream test-hermeticity defect, outside this PR's scope.**
These seven tests read the **live tmux server** through `affected_sessions()` →
`session_service.list_sessions()` → `get_backend().list_sessions()`, so an attached CAO session on the
machine makes them fail:

- `test_api.py::TestListPlugins::test_installed_plugins_report_findings_and_projected_skills`
- `test_cli.py::TestRemove::test_remove_deletes_and_unprojects`
- `test_cli.py::TestRemove::test_purge_data_is_reported`
- `test_cli.py::TestRemovalConfirmation::test_no_prompt_when_nothing_is_affected`
- `test_installer.py::TestAffectedSessions::test_no_live_sessions_means_nothing_affected`
- `test_last_mile_contracts.py`, both `TestAffectedSessionsToleratesRealWorldState` cases

The evidence that they predate this PR comes from the supervisor; this seat did not re-run the
baseline:

- They fail at the pre-T5 baseline `5b1dbc81`. That commit's change is a wheel mirror and a
  `SHIPPED_SKILLS` edit, which touches neither these tests nor their code path.
- The supervisor reproduced one of them.
- T5's must-pass block, run unchanged under `env -u TMUX TMUX_TMPDIR=$(mktemp -d)`, gave **1263
  passed**. Without that isolation, the only failures were the same seven.

**Recommendation: a separate upstream issue**, so these tests stop depending on the machine's tmux
state, for example by stubbing the backend's `list_sessions`. It is **not filed**. **The final
full-suite run uses the same isolation**, `env -u TMUX TMUX_TMPDIR=$(mktemp -d)`, and must say so.
Any non-isolated failures must be reported alongside it, and only these seven may appear.

**Hazard 1's expected red is confirmed.** `uv run --frozen pytest -q -p no:cacheprovider
test/test_agent_plugins_docs.py --no-cov` gave `1 failed, 28 passed`, exit 1. The only failure is
`TestPrerequisitesAndPosture::test_package_skill_lists_match_the_build_configuration`, whose message is
`assert 'cao-agent-plugin-creator' in "# Agent Plugins …`. It is expected until T7 documents both
skills.

### Wave 1 — done; recorded between waves 1 and 2

Recorded by the author seat on 2026-11-01, between waves, with no other seat writing (`tasks.md`
hazard 4's rule 1). **Only the untracked spec directory changed:** `git status --short` shows only
`?? docs/issues/1153-agent-plugin-lifecycle/`, and `git diff --quiet HEAD` exits 0. Nothing was
committed or pushed by this seat. **NOT READY TO PUSH:** waves 2–5 remain.

| Task | Result |
|---|---|
| **T1** — creator skill | **`c17045289260ca2fdc458579181adaa4aa54fabf`**, committed 2026-11-01 14:50:20 -0600. **This is Requirement 15.5's reference point** (`tasks.md:248`): no harness-oss artifact may be described as authored with the creator skill unless its commit is later than this one |
| **T2** — audit skill and validator | **`bf817a90899cbc84173bf225ea7acbdee6420354`**, committed 2026-11-01 15:01:26 -0600 |
| **T3** — over-limit experiment | **`P-6` OBSERVED** for the two length limits. A 2000-character description and a 600-line body are admitted: `"loadable": true`, `"findings": []`, exit 0. The name regex and the 64-character bound were not tested and stay inferred. Report: `docs/issues/1153-agent-plugin-lifecycle/t3-overlimit-experiment.md`, 240 lines, untracked |

`git log --format='%h %G? %an' upstream/main..HEAD` gives `bf817a90 G plauzy` and `c1704528 G plauzy`,
read by this seat. The supervisor verified the two trailers and that gate 1 over `skills/` prints
"summary: 0 fatal … exit 0"; this seat did not re-run those.

**The three wave-1 findings, now in the spec as provenance rather than as silent rewrites:**

1. **Spec-versus-code correction, found by the T1 implementer** (`P-72`, `requirements.md:205`). The spec said CAO treats an unknown manifest key as FATAL. That is true only for a **nested** key: `author.twitter` gives FATAL `manifest.invalid`, exit 1. An unknown **top-level** key gives WARNING `manifest.unknown_field` (§5.2); the key is ignored and the package stays loadable, exit 0. The code is `_apply_manifest_tolerances` (`src/cli_agent_orchestrator/agent_plugins/validation.py:462` onward, called at `:288`). The expectation is in `test/agent_plugins/fixtures/corpus/cases.json:61-69`, the fixture the old `P-23` cited.
   - **Re-verified by this seat**, by reading and by running both cases: the corpus fixture gave exit 0 with one `warning`; a temporary nested-key package gave exit 1 with `fatal`.
   - **Corrected at:** `P-23` (`requirements.md:155`); 1.4 (`:222`); `design.md` error-handling table (`:376-377`) and "named cases" (`:247`); T1's description (`tasks.md:199`); T5 defect 7 (`:583`).
   - **Not corrected:** `research.md:128` repeats the error and is not edited (Requirement 13.7); `P-72` names it.
2. **T3 finding, `CAO_HOME_DIR`** (`P-73`, `requirements.md:207`). A fresh `CAO_HOME_DIR` gains three empty directories, `fifos/`, `logs/` and `logs/terminal/`, and no files. The cause is inferred to be startup directory creation and has not been traced. This seat reproduced it during the re-verification run.
   - **Fixed at:** `tasks.md:351` (T3 description), `:372` (criterion), and `:404`, the experiment block's label, which said "expected empty".
   - **`P-6` updated to OBSERVED** at `requirements.md:50`, `:138` and 2.7's branch (`:246`); `design.md:159`, `:383`, `:391`, `:435` (with a new `:436` row for `P-73`); `tasks.md:281`, `:347` and T8's `:899`.
3. **T2 findings** (`P-74`, `P-75`, `P-76`, `requirements.md:206-209`). No decision changed.
   - **Bundled schema copies.** The validator bundles byte-identical copies at `skills/cao-agent-plugin-audit/schemas/1.0.0/`, which this seat compared with `cmp`. It refuses to run, exit 2, on a hash mismatch or a disagreeing `PIN.json`. So T4's mirror and T5's package each carry another copy. This is stated in `design.md:173` and as expectations in T4 (`tasks.md:492`) and T5 (`:571`).
   - **Requirement 4.8's caveat is partly closed.** A nonexistent path and a regular file both give parseable JSON, `loadable` false, `plugin.root_invalid`, exit 1; this seat re-ran both. Other raise paths stay unchecked (`requirements.md:291`).
   - **Exit 1 on a CAO WARNING.** The validator exits 1 on `manifest-unknown-field` while CAO exits 0, which follows the exit contract (1 = findings). This seat re-ran it and saw `summary: 0 fatal, 0 skipped, 0 limit, 1 warning, 1 advisory; exit 1`. It is stated at `requirements.md:291`, `design.md:175` and T5 `:571`.

**T4 and T5 re-read after these edits.** They still read correctly. Each gained one "Expected, not drift" paragraph, and T5's defect 7 now states the corrected behaviour. No criterion, command, ownership or decision changed in either task.

**Checks:**

- `uv run --frozen python scripts/validate_markdown_links.py` → exit **0**.
- 17 ```` ```bash ```` blocks were read in place, all with fences at column 0. Each passes `/bin/bash -n` and `zsh -n`, every heredoc closes at column 0, and every body passes `/bin/bash -n`. fail=0.
- Zero duplicate `##` headings; fences 2 / 8 / 30, all even; no indented fence and no indented `EOF` or `PY`; no duplicate provenance id (rows now run to `P-76`).
- Attribution counts are unchanged in all three files.
- `git status --short` = the untracked directory only; `git diff --quiet HEAD` → 0.
- Pre-edit copies are at `/tmp/cao-apl-w1-{requirements,design,tasks,STATUS}.before.md`.

### Frozen (between waves 1 and 2, current)

| File | Lines | `shasum -a 256` |
|---|---|---|
| `requirements.md` | 701 | `82ab558e41c365cf117a41af53f1a0b00164facfa0e32eccb65da3d3773301cc` |
| `design.md` | 500 | `6a07270059a1772ae4fbb20e0807f6336194533ec4318e6d040630c27c05164b` |
| `tasks.md` | 929 | `65f182d3544a9c1123551b3bbd1318a178621db68cb8f0e39270fed6cdecccf7` |

### Round 4 — review 8's conditions (history)

**Spec cleared by review 8; condition met.** Review 8 (`review-8.md`, pinned to `fbf51ba0` / `f0f38f9f`
/ `7c24334a`) returned **CLEARED FOR IMPLEMENTATION**, on condition that R8-N-1 is fixed before the
first implementation commit. R8-N-1 is fixed, and cases (a)–(c) below came out exactly as required.
R8-N-2, R8-N-3 and R8-N-4 are applied too. The per-finding disposition is appended to `review-8.md`,
whose original body is byte-identical. **Still NOT READY TO PUSH:** nothing is implemented or committed.
N-11 is still the user's decision and is unchanged. The Round 3 section below is history.

**Changed:**

- **R8-N-1:** 13.8's block reads every trailer with `%(trailers:unfold,only)`, requires exactly two lines, and rejects any key other than `Co-authored-by`. All the earlier checks are kept (`requirements.md:493`, `:513-515`).
- **R8-N-2:** hazard 3 gives the two exact lines and says to run 13.8's block after every task commit (`tasks.md:69`). T8 names 13.8's block as the supervisor's pre-push gate (`:901`).
- **R8-N-3:** T1's limits block is wrapped with a `TOP=` line (`:224-237`). Every ```` ```bash ```` block in `tasks.md` is now heredoc-wrapped.
- **R8-N-4:** the boundedness fixture writes one manifest per `bap.PACKAGES` entry (`:565`, `:605`).
- `design.md` is unchanged this round.

**The Kiro Agent trailer, exactly:** `Co-authored-by: Kiro Agent <244629292+kiro-agent@users.noreply.github.com>`.
It is the value 13.8's `AGENT` variable accepts. It is also the only Kiro form on `upstream/main`:

- `git log upstream/main --format='%(trailers:key=Co-authored-by,valueonly)' | sort | uniq -c` lists `16 Kiro Agent <244629292+kiro-agent@users.noreply.github.com>`.
- `git log upstream/main --format='%(trailers:unfold,only)' | grep -i kiro | sort | uniq -c` lists one line, `16 Co-authored-by: Kiro Agent <244629292+kiro-agent@users.noreply.github.com>`.

The author line is `Co-authored-by: plauzy <4451274+plauzy@users.noreply.github.com>`, which equals
`%an <%ae>` under the user's git configuration.

**Proof (throwaway `git clone --shared`, deleted afterwards; this worktree has no commits,
`upstream/main..HEAD` = 0).** Blocks were copied byte-for-byte from the source, with their fences at
column 0, and run under zsh 5.9.2 and `/bin/bash` 3.2.57. Each case below gave the same result in both
shells.

| 13.8 case | Exit | Message |
|---|---|---|
| **(a)** signed commit, exactly the two hazard-3 lines | **0** | "all commits … signed (G) by plauzy with exactly the two trailers" |
| **(b)** (a) plus `Session: https://example.invalid/x` | **1** | "not exactly two trailer lines in total". `%(trailers:unfold,only)` listed the `Session:` line, so git does parse it as a trailer |
| **(c)** (a) plus a third `Co-authored-by` | **1** | "not exactly two Co-authored-by values" |
| extra: lowercase `co-authored-by:` key | **1** | "a trailer key other than Co-authored-by". The `key=` filter matched it case-insensitively; the new key check did not |
| Round 3: empty range | 1 | unchanged |
| Round 3: duplicated Kiro Agent trailer | 1 | unchanged |
| Round 3: wrong author | 1 | unchanged |
| Round 3: unsigned | 1 | unchanged |
| Round 3: only the Kiro Agent trailer | 1 | unchanged |
| Round 3: last commit unsigned | 1 | unchanged |
| Round 3: first commit unsigned | 1 | unchanged |

**T1's wrapped block:** run from `/tmp`, **2**; from the root or `scripts/` with a conformant
fixture, **0**; from the root with a 2000-character description, **1**. Same in both shells.

**A correction to Round 3's proof labels:** that harness printed each block's last line number one
short. The text it ran was complete, as the column-0 `EOF` exits show; only the printed range was off.

**Checks:**

- `uv run --frozen python scripts/validate_markdown_links.py` → exit **0**.
- 17 ```` ```bash ```` blocks were read in place from the source: 16 heredoc-wrapped, plus `design.md`'s plain gate list. All fences are at column 0. Each passes `/bin/bash -n` and `zsh -n`, each heredoc closes with a column-0 `EOF`, and each body passes `/bin/bash -n`. fail=0.
- Zero duplicate `##` headings; fences 2 / 8 / 30, all even; no indented fence and no indented `EOF` or `PY`; heredoc opens and closes 1/1 and 17/17; no duplicate provenance id.
- Attribution counts are unchanged, and the N-11 text is unchanged.
- Pre-round copies are at `/tmp/cao-apl-r8-{requirements,design,tasks,STATUS}.before.md`.

### Frozen (round 4, superseded by the wave-1 freeze)

| File | Lines | `shasum -a 256` |
|---|---|---|
| `requirements.md` | 696 | `b07296b1e5b76eadf42b899e2c210c9477d6fdefbe5f933a389561d0ac275277` |
| `design.md` | 494 | `f0f38f9fa28b4700c7d80e345d7f374eeffd6224c63317509c6685bcc4d106c9` |
| `tasks.md` | 925 | `de899240f3b1e3ac1b5564d3e131fea982c0abeff909797ac8f634c0f7b521c4` |

**Next:** implementation, waves 1–5 including T8 (the independent reviews), starting with T1, the
creator skill (Requirement 15.5). Run 13.8's block after every task commit. **Nothing is pushed.**

### Round 3 — review 7's fix list (history)

Review 7 (`review-7.md`, pinned to `db2d087e` / `d00dffef` / `2d91e8cf`) returned **NOT CLEARED**
with two mechanical blockers, R7-B-1 and R7-B-2, and R7-N-1 to R7-N-7. All are applied. The
per-finding disposition, with file and line after the change, is appended to `review-7.md`; the
original body of that file is byte-identical. **Still NOT READY: review 8 must clear.** N-11 is still
the user's decision and is unchanged. **The Round 2 section below is history, and its line numbers
have moved.**

**R7-B-2 was reproduced before it was fixed.** Four blocks were copied byte-for-byte from the source,
keeping their indentation, and run in a throwaway clone:

| Block, as it sat in the source | zsh | bash |
|---|---|---|
| Hazard 4 start (`tasks.md:76-85`, 3-space indent) | **127**: `stamp taken: …` then `bash: line 9: EOF: command not found`; the stamp was created | **127**, same |
| 13.8 (`requirements.md:495-506`, 3-space indent) | **1** "no commits"; **1** "signature is not G" after an unsigned commit; **128** with the `upstream/main` ref absent. The heredoc never closed, but an `exit` fired first | same |
| T1 limits (`tasks.md:222-232`, 2-space indent) | **1**, `IndentationError: unexpected indent` | **1**, same |
| Hazard 4 end (`tasks.md:91-155`) | **0**, `scope OK`: `exit "$FAIL"` ran before the stray `   EOF` | **0**, same |

`bash -n` passed all four. **That is the lesson:** a syntax check cannot see that a heredoc never
closes, because an unclosed heredoc is valid syntax. Every earlier round measured de-indented extracts,
which is how this survived rounds 1 and 2. **The fix:** every fenced block inside list-item indentation
moved to column 0. The sweep of all three files found exactly these four blocks, and none is left.

**R7-N-3: the measured `%G?` is `G`.** In a throwaway `git clone --shared`, never this worktree,
`git commit -S` with the user's normal configuration exited 0. That configuration is
`gpg.format=ssh`, `user.signingkey=~/.ssh/id_ed25519.pub`, `commit.gpgsign=true` and
`gpg.ssh.allowedSignersFile`. The results:

- `git log -1 --format='%G? %GS %an %ae'` gave `G 4451274+plauzy@users.noreply.github.com plauzy 4451274+plauzy@users.noreply.github.com`.
- `git verify-commit HEAD` gave "Good "git" signature … with ED25519 key SHA256:<redacted>", exit 0.

13.8 now accepts **`G` only**, recorded as `P-71`. Upstream's commits by the same author report `E`, because they are squash merges this machine cannot verify, which explains the `E` seen in round 1. **Signing works; nothing is blocked on it for implementation.**

**Proof, every block taken verbatim from the source with no de-indenting.** It ran in a throwaway
clone, which was deleted afterwards; no tracked worktree file was touched. The blocks were run as
files under `zsh` 5.9.2 and `/bin/bash` 3.2.57. The T3 and T6 start and end blocks are byte-identical
to hazard 4's except the task id.

- **Scope blocks** (hazard 4 as t1, T3, T6; each cell measured under zsh and under bash):

  | Case | Exit |
  |---|---|
  | clean tree | 0 |
  | untracked write | 1 |
  | tracked edit | 1 |
  | staged new file | 1 |
  | `rm` of a tracked file | 1 |
  | `rm` of untracked `research.md` | 1 |
  | broken symlink | 1 |
  | `git rm` | 1 |
  | `git mv` | 1 |
  | non-ASCII name | 1 |
  | name git quotes | 1 |
  | edit to `test_agent_plugin_pin_boundedness.py` | 1 (out of scope for waves 1 and 3) |
  | stamp missing | 2 |
  | check-4 `find` error | 0, warning only |

  Every **start** block exited **0**. Before the fix, hazard 4's start block exited 127.
- **R7-B-1:** the boundedness edit under t5 gives **0** in zsh and bash, so it is now in scope for wave 2.
- **Real worktree, clean, start then end:** hazard 4, T3 and T6 each gave **0** under both shells, `scope OK`.
- **T1 limits block:** with no skill, exit **1** (`FileNotFoundError`); with a conformant fixture, **0**; with a 2000-character description, **1**. Same in both shells.
- **13.8 block:** an empty range gives **1**. A signed commit by plauzy with the two correct trailers gives **0**. Each of these gives **1** in both shells: a duplicated Agent trailer, the wrong author, an unsigned commit, only the Agent trailer, an unsigned last commit, and an unsigned *first* commit, which `git log -1` would have missed.
- **T2 negative control: cannot be run meaningfully before T2 exists.** With the validator absent it exits **1**, "negative control: expected exit 1, got 2", in both shells, so it fails rather than passing. Its fixture generator was measured at exactly 2000 characters.
- **T3 experiment block (R7-N-1):** run from `/tmp`, it exits **2**, "run this from inside the worktree"; with a relative fixture, **2**. Before the fix, `cd "$(…)"` with a failed substitution ran `cd ""`, which exits 0 in both shells, and `set -e` did not stop it.

**Checks:**

- `uv run --frozen python scripts/validate_markdown_links.py` → exit **0**.
- Every ```` ```bash ```` block was read **as it sits in the source**: 17 blocks, all with the fence at column 0. Each passes `/bin/bash -n` and `zsh -n`. Each heredoc-wrapped block closes with a column-0 `EOF`, and its body passes `/bin/bash -n`. Overall fail=0.
- Zero duplicate `##` headings; fences 2 / 8 / 30, even; **no indented fence and no indented `EOF` or `PY` anywhere**; heredoc opens and column-0 closes are 1/1 (requirements) and 16/16 (tasks, counting T1's and T5's `PY`); no duplicate provenance id.
- Attribution counts are identical before and after this round, and the N-11 text is unchanged.
- Pre-round copies are at `/tmp/cao-apl-r7-{requirements,design,tasks,STATUS}.before.md`.

### Frozen for review 8 (round 3, superseded by round 4)

| File | Lines | `shasum -a 256` |
|---|---|---|
| `requirements.md` | 692 | `fbf51ba0744fe2396270b331d38bf870c1bf2bfd5c4a599149cf5187a83121f6` |
| `design.md` | 494 | `f0f38f9fa28b4700c7d80e345d7f374eeffd6224c63317509c6685bcc4d106c9` |
| `tasks.md` | 922 | `7c24334a207d85375be3eefc6646420edd398a15f58d94e6f3a268434e1b2823` |

The round-2 freeze table below is superseded. Before declaring the freeze, check that no `pending`
inbox message is addressed to the author seat.

### Round 2 — review 6's fix list (history)

Review 6 (`review-6.md`, pinned to the round-1 hashes `50259d7e` / `642c9035` / `5d2aa049`) returned
**NOT CLEARED** with one blocking finding, **R6-B-1**, and N-1 to N-14. The freeze was lifted for that
list only. **Every item is applied except N-11**, which is the user's decision. The per-finding
disposition, with file and line after the change, is appended to `review-6.md` under "Disposition",
and the original body of that file is byte-identical. **Still NOT READY:** review 7 must clear first.
**Line numbers in the round-1 subsections below are pinned to the round-1 hashes and have since moved.**

**Fixed:**

- **R6-B-1**, all three parts as written:
  - a T2 `--skills-dir` criterion (`tasks.md:301`), matched by Requirement 4.3 (`requirements.md:280`);
  - gate 1, verbatim, plus package mode, inside T5's `bash -euo pipefail` block (`tasks.md:600`, `:603`);
  - T1's Requirements line narrowed to 1.10's first clause, with T5 named as carrying the validator clause (`tasks.md:215`, `:570`);
  - hazard 2 now names the command and the expected exit (`tasks.md:67`).

  **Measured so the new gate can pass:** every skill in `skills/` at `27311798` passes the five limits
  when measured directly (name regex, ≤ 64, folder = `name`, description ≤ 1024, body ≤ 500).
  `cao-workflow`'s body, 486 lines, is the closest to a limit. `skills/plugin.json` and `skills/vendor/`
  are the two non-skill entries the `--skills-dir` contract ignores.
- **N-1**, renumbering map:
  - **Requirement 2:** identity. The written order "12, 11" was reordered to "11, 12" with the numbers unchanged, so no reference moves.
  - **Requirement 10:** identity. "9, 8" was reordered to "8, 9".
  - **Requirement 4:** 4.1–4.4 unchanged, where 4.4 is the PEP 723 criterion. The rest moved as follows:
    - the second "4." (vendored schema, no fetch) → **4.5**
    - 4.5 (no `harness-oss` validator) → **4.6**
    - 4.6 (schema versus allowlist) → **4.7**
    - 4.7 (JSON discriminator) → **4.8**
    - 4.8 (bundled script is the gate) → **4.9**

    Req 4's traceability is updated: Criterion 8 is made mechanical and Criterion 9 is added.
  - **References** were updated by meaning, not by number: `design.md:19`, `:169`, `:171`, `:239`, `:340`, `:392`, `:405`, `:446` and `tasks.md:277`, `:278`, `:280`, `:281`, `:285`, `:308`, `:358`.
  - **One reference was already wrong before the renumber:** T2 defect 5 cited 4.3 for the PEP 723 rule, which is 4.4.
  - **This checkpoint's own `N.M` references** (8.11–8.13, 9.6, 10.9, 12.13, 13.7, 16.2, 16.3) name no renumbered criterion, so none changed.
  - A script now confirms every requirement's criteria run 1…n. The only non-sequential list is Requirement 8's separate release-path list, which follows a prose paragraph and renders as its own list.
- **N-2** through **N-10**, **N-12**, **N-14**: the four stale claims, the B-6 residual at the old `requirements.md:539` (now `:556`), and T2's "never reads stdin" caveat (`tasks.md:303`). Per-item lines are in the disposition table.
- **N-13**, the task-numbering map: **the go-ahead's "minus T8 / T9's two reviews" maps to the current numbering as "waves 1–5 including T8 (the independent reviews); the blog task is deferred."** In today's `tasks.md`, T8 is the two independent read-only reviews and there is no T9. The old blog task was deleted. So "without T8" must not be read as dropping the reviews.

**Open user question added — N-11.** A third-party UI-framework product name appears in the
vocabulary constraints (`design.md` § Forward vocabulary constraints, rows 2–3; `requirements.md`
16.2, 16.4; `tasks.md` T1 defect 7). This contradicts the earlier statement that only three verbatim
carve-outs exist. **Ratify it as a fourth carve-out, or rewrite those constraints generically?** The text
is unchanged pending the user's answer. The attribution sweep below treats it as pre-existing.

**Found while fixing, not raised by review 6.** The first draft of the N-4 fix put `case "$f" in \"*) …
;; esac` inside `$( … )`. `/bin/bash` 3.2.57 cannot parse that, and reports "syntax error near
unexpected token `;;'"; `zsh -n` accepts the same text, exit 0. The proof run caught it: every case
exited 2. It is now an `if`, with a comment giving the reason. **The round-1 `bash -n` check would have
missed it**, because that check parsed the outer `bash … <<'EOF'` line, which cannot see inside a quoted
heredoc. The integrity check below parses each heredoc **body** with `/bin/bash -n`.

**Proof, re-run (throwaway `git clone --shared` at `27311798` with the spec dir copied in, deleted
afterwards; no tracked worktree file touched).** The published T3 and T6 start and end blocks were
extracted verbatim from `tasks.md` and run as files under `zsh` 5.9.2 and `/bin/bash` 3.2.57. The T3
and T6 copies are identical to hazard 4's blocks except the task id. Every cell below was measured for
T3 and T6, under each shell:

| Case | zsh T3 | bash T3 | zsh T6 | bash T6 | Message |
|---|---|---|---|---|---|
| (i) clean, in-scope write only | 0 | 0 | 0 | 0 | `scope OK` |
| (ii) untracked `scripts/zz_planted.py` | 1 | 1 | 1 | 1 | `OUT-OF-SCOPE WRITE` |
| (ii) tracked `Makefile` edit | 1 | 1 | 1 | 1 | `OUT-OF-SCOPE WRITE` |
| (ii) staged new file | 1 | 1 | 1 | 1 | `OUT-OF-SCOPE WRITE` |
| (ii) `rm CODEBASE.md` | 1 | 1 | 1 | 1 | `OUT-OF-SCOPE DELETION` |
| (ii) `rm` of untracked `research.md` | 1 | 1 | 1 | 1 | `UNTRACKED FILE DELETED` |
| (ii) broken symlink | 1 | 1 | 1 | 1 | `OUT-OF-SCOPE WRITE` |
| **(ii) `git rm CODEBASE.md`** | 1 | 1 | 1 | 1 | `OUT-OF-SCOPE DELETION: CODEBASE.md` |
| **(ii) `git mv Makefile Makefile.moved`** | 1 | 1 | 1 | 1 | `OUT-OF-SCOPE DELETION: Makefile` |
| **(ii) non-ASCII `scripts/zz_é.txt`** | 1 | 1 | 1 | 1 | `OUT-OF-SCOPE WRITE: scripts/zz_é.txt` |
| (ii) name git still quotes, `scripts/zz"q.txt` | 1 | 1 | 1 | 1 | reported quoted, fail closed |
| (iii) stamp removed | 2 | 2 | 2 | 2 | `MISSING STAMP …: run the start block first` |
| **(iv) check-4 `find` error: `chmod 000` dir under ignored `scripts/__pycache__/`** | 0 | 0 | 0 | 0 | `WARNING (not a failure): check 4 could not read all of scripts/__pycache__/`, then `scope OK` |

**Contrast:** the round-1 published T3 end block, run on the new cases under both shells, gave
`git rm` 0, `git mv` 0 and non-ASCII 0 (all `scope OK`, all wrong), and the check-4 `find` error 2,
which failed a clean tree. That confirms N-4 and N-5 were real. **Real worktree, clean, start then
end:** zsh T3 0, bash T3 0, zsh T6 0, bash T6 0. Only `/tmp` stamps were written, and they were deleted.
**13.8's new block** run in the real worktree: zsh exit 1 and bash exit 1, `no commits in
upstream/main..HEAD`, which is correct with no commits.

**Checks:**

- `uv run --frozen python scripts/validate_markdown_links.py` → exit **0**.
- Every ```` ```bash ```` block in the three files (17 blocks: 1 in `requirements.md`, 1 in `design.md`, 15 in `tasks.md`) passes `bash -n` on the outer text. Each of the 15 heredoc-wrapped blocks also passes `/bin/bash -n` on its body, and each closes with `EOF`.
- Zero duplicate `##` headings; fence counts 2 / 8 / 30, all even; heredoc opens and closes 1/1 (requirements) and 14/14 (tasks); no duplicate provenance id.
- **Attribution:** per-file provider, vendor and model name counts are identical before and after this round. The N-11 product-name text is unchanged in all three files. Only an adjacent "Why" cell in `design.md` changed, for the `GENERATIVE_UI` fix.
- Pre-round copies are at `/tmp/cao-apl-r6-{requirements,design,tasks,STATUS}.before.md`.

### Round 1 — steps A–D (history; line numbers pinned to the round-1 hashes)

### Tree state

| Fact | Value |
|---|---|
| `HEAD` | `2731179845f9bd332a22e72fa44cc55345561c99`, equal to `upstream/main` |
| How it got there | `git merge --ff-only upstream/main` from `00611d11`, exit 0, `Updating 00611d11..27311798`, `Fast-forward`. No fetch, no rebase, no reset |
| New commits | `5892e8e3` (#1170, the Kiro identity header) and `27311798` (#1176, the `joserfc` bump). Neither is plauzy's |
| `git status --short` | `?? docs/issues/1153-agent-plugin-lifecycle/` only, before and after |
| Local commits / pushes | none / none |
| `validate_markdown_links.py` | `uv run --frozen python scripts/validate_markdown_links.py`, exit **0** |
| Integrity | zero duplicate `##` headings in all three files; even fence counts (0 / 8 / 28); 13 `<<'EOF'` heredocs in `tasks.md`, each closed; 16 requirements, no duplicate number; no duplicate provenance id |

### A — fast-forward and citation re-check

The commit range changed only these paths: `CHANGELOG.md`, `docs/kiro-cli.md`,
`examples/robotics/cross-zone-transport/uv.lock`, `src/cli_agent_orchestrator/providers/kiro_cli.py`,
`src/cli_agent_orchestrator/providers/kiro_identity.py`, ten new `test/providers/fixtures/kiro_cli_tui_2_35_1_*.txt`
fixtures, `test/providers/test_kiro_cli_unit.py`, `test/providers/test_kiro_identity_header_columns.py` (new),
`test/services/test_kiro_agent_identity_launch.py` and `uv.lock`. A grep of `requirements.md`, `design.md`,
`tasks.md` and `research.md` for every one of those paths found these hits:

| Hit | What it cites | Outcome |
|---|---|---|
| `requirements.md:212` | `CHANGELOG.md` as a file CAO's builder generates **inside a package** | unchanged; not the repo-root file, no line number |
| `tasks.md:69` | the tracked `uv.lock`, rewritten by `scripts/security-scan.sh` without `--frozen` | unchanged; no line number, and `security-scan.sh` did not change |
| `tasks.md` T5 file-list criterion | `agent-plugin/cao-agent-plugin-lifecycle/…/CHANGELOG.md` | unchanged; a package file |
| `research.md:132` | package `CHANGELOG.md`, cited to `build_agent_plugin.py:92,689-691,707-710` | unchanged; `scripts/` did not change |
| `research.md:140` | `agent-plugin/cao/CHANGELOG.md` | unchanged |

No hit for `kiro-cli.md`, `kiro_cli.py`, `kiro_identity`, any `test_kiro_*` file, the fixtures, or the
`cross-zone-transport` lockfile. `git diff --name-only 00611d11 27311798 -- scripts Makefile .github agent-plugin skills test/agent_plugins docs/agent-plugins.md CODEBASE.md pyproject.toml`
printed nothing, so **no citation to any other file can have moved either**.

Base statements, updated where they state the base as current fact:
`requirements.md:5` (the Base line); `requirements.md:153` (`P-21` now says "was `HEAD` on
2026-10-30"); new row `P-66` at `requirements.md:199`; `design.md:263` and `:265` (gates "not re-run at
`00611d11` or at `27311798`"); `tasks.md:41` and `:44`; the T5 option-B paragraph ("an ancestor of
`HEAD`"). **One stale current-fact claim the 2026-10-30 rebase missed was fixed:** `design.md`'s
Dependencies row still said "Open PR #1121 edits the `CONTRIBUTOR` block". Kept as history:
`requirements.md` `P-15`, `P-16`, `P-52`, 12.9, 12.13; `design.md:180`, `:189`, `:464`; `tasks.md:42`.
**`research.md` was not edited**: its base statements are dated records, and no citation in it moved.

Requirement 12.13's trailer figure, recounted rather than carried: `git log 27311798
--format='%an%x09%(trailers:key=Co-authored-by,valueonly)'` gives 19 plauzy lines, 16 with the Kiro
trailer, 16 Kiro lines overall. **Unchanged at 16 of 19**, because neither new commit is his.

### B — release-path findings routed

| Finding | Where it landed | Evidence, re-verified at `27311798` |
|---|---|---|
| `run.sh` dogfoods only `agent-plugin/cao`; "dogfooded in CI" is forbidden, "gated in CI by `make check-agent-plugin`" is allowed; extending `run.sh` is an **open user question**, not added | `P-67`; Requirement **8.12**; new "CI dogfood coverage" row under "Still genuinely open"; `design.md` § 4 and the "Excluded from the ladder" row; T5 defect 9 and criterion; `tasks.md` out-of-scope row | `run.sh:93-94`, `:114-115`, `:272-273` name `agent-plugin/cao` and nothing else; `ci.yml:509-561`, `npm run record` at `:551`; `tools/package.json:8` is `node record-dogfood-demo.mjs` (not read) |
| Build the third package in-process at `2.5.3`, then `make check-agent-plugin`; never `make agent-plugin`; the `None` failure mode | `P-68`; Requirement **8.13** (9.6 points to it); `design.md` § 4; T5 description, defect 10 and two criteria | **Measured in memory, nothing written:** `committed_package_version()` → `'2.5.3'`; after appending a third config to `PACKAGES` with no directory → `None`; `package_version()` → `2.5.4`; `git status --short` unchanged. Code at `build_agent_plugin.py:319-348`. `make agent-plugin` is `Makefile:40-41`. `skills/cao-contributing/SKILL.md:233-242` (checklist item 7) says a contributor PR should not move the pin. **Wording corrected:** it does not forbid `make agent-plugin` outright; it says to restore the version strings afterwards |
| `test_packages.py` sites that pass with a third package while not covering it | `P-69`; Requirement **8.11** rewritten to name every site; `design.md` § 4 table, install-smoke-test paragraph and Dependencies row; T5 description and criterion | Read at this base: parametrised over `[OPERATOR_DIR, CONTRIBUTOR_DIR]` at `:42`, `:50`, `:54`, `:67`, `:83`, `:312`; `(config, package_dir)` pairs at `:216-219`; pairwise disjointness `:223-225`; `--check` names both at `:227-234`; side-by-side install `:326-340` (loop `:328`, set `:336`). **The 2026-10-30 checkpoint omitted `:312`, and review 5's "six parametrised sites" omitted `:216-219`** |
| Verified-safe, no action: the release job, `--require-bounded-client`, `--require-current-pin` | `P-70`; Requirement 8's release-path block now reads "answered" instead of "OPEN"; `design.md` relayed questions 2–4 marked answered | `publish-to-pypi.yml:503` (`regenerate-agent-plugin`), `:532`, `:572`; `build_agent_plugin.py:875`, `:876`, `:891`, `:1007-1015`; `agent-plugin/cao-contributor/CHANGELOG.md:12` "This package is pinned to CAO v2.5.3" |

### C — R5-1 fixed, and proved

What changed in `tasks.md`:

- Hazard 4 (`:71` onward) is now a **start block** and an **end block**, each `bash -euo pipefail -s tN <<'EOF' … EOF`. The start block creates `/tmp/cao-apl-tN.stamp` and an untracked-file snapshot. The end block runs `test -f` on both, exits **2** if either is missing, tests each git-listed candidate with `find "$f" -prune -newer "$STAMP" -print`, and exits **1** on any out-of-scope write, tracked deletion or untracked deletion. Per-wave paths moved inside the end block as a `case`, so only the task id is edited. No `-nt` remains in any command.
- **T3 now creates its stamp**: a "Before you start" block (`tasks.md:342`) and a filled-in "Scope check that must pass" (`:369`). The experiment command is wrapped too, and takes the fixture as an argument (`${1:?…}`).
- **T6**: "Before you start" (`:591`), the audit command rewritten under `bash -euo pipefail` with `AUDIT_EXIT=$?` after a `| tee` pipeline in place of `${PIPESTATUS[0]}`, `awk` in place of `grep | head` (to avoid `SIGPIPE` under `pipefail`), and a filled-in scope check (`:653`).
- Every "Command that must pass" (T1–T7, seven blocks) is wrapped in `bash -euo pipefail <<'EOF' … EOF`. T2's `! grep -rqn …` became an explicit exit-1 test, so grep's error status 2 now fails.
- The blind-spot table was re-derived. Untracked deletion, staged files and broken symlinks are now **closed**. A gitignored write is a **warning, not a failure**, via `git ls-files -o -i --exclude-standard --directory`.

**Proof.** The published blocks were extracted verbatim from `tasks.md` by a script and run as files,
under `zsh` 5.9.2 and `/bin/bash` 3.2.57. Each one ran from a throwaway `git clone --shared` of this
worktree at `27311798`, with the untracked specification directory copied in, and the clone was deleted
afterwards. No tracked file in the worktree was modified. The T3 and T6 copies differ from hazard 4's
blocks only in the task id (`diff` after normalising the id), and they were re-checked after the last edit
and are byte-identical to the tested files. Each case runs the start block, writes the task's own in-scope
file and a `__pycache__/zz.pyc`, applies the case, and then runs the end block:

| Case | zsh T3 | bash T3 | zsh T6 | bash T6 |
|---|---|---|---|---|
| (i) clean tree, in-scope write only | **0** `scope OK` | **0** | **0** | **0** |
| (ii) planted untracked file `scripts/zz_planted.py` | **1** `OUT-OF-SCOPE WRITE` | **1** | **1** | **1** |
| (ii) edit to tracked `Makefile` | **1** | **1** | **1** | **1** |
| (ii) staged new file | **1** | **1** | **1** | **1** |
| (ii) deleted tracked `CODEBASE.md` | **1** `OUT-OF-SCOPE DELETION` | **1** | **1** | **1** |
| (ii) deleted untracked `research.md` | **1** `UNTRACKED FILE DELETED` | **1** | **1** | **1** |
| (ii) broken symlink `scripts/zz_link` | **1** | **1** | **1** | **1** |
| (iii) stamp removed | **2** `MISSING STAMP /tmp/cao-apl-tN.stamp: run the start block first` | **2** | **2** | **2** |

The `__pycache__` write printed `WARNING (not a failure)` and did not change any exit status. In the
**real worktree**, start then end with nothing written between: zsh T3 **0**, bash T3 **0**, zsh T6
**0**, bash T6 **0**, all `scope OK`; only `/tmp` stamps were created, and they were deleted.
**Contrast, the pre-fix T3 lines** with no stamp and a planted write: zsh exit 1 with **empty output**,
which is that block's pass condition ("must print nothing"), so R5-1 reproduces. Bash printed every
candidate. All seven "Command that must pass" blocks pass `bash -n`. The T3 experiment block with no
fixture exits 1 under both shells with `pass the fixture directory as the argument`. The T6 block with
the script absent exits 1 under both shells, and zsh no longer reports `parameter not set`.

### D — review-5 non-blocking items folded in

| Item | Done |
|---|---|
| Deleting an untracked file was invisible | **Closed** by the start block's snapshot and the end block's check 3; proved by the `research.md` deletion case above |
| B-2's existence-check rationale was wrong | T6 criterion (`tasks.md:579`) and the block comment now say a quoted real path is never a redirect; only a literal `<name>` placeholder is (`review-1.md:211`, `review-2.md:46`). The real reason the check is needed: step 1 records the exit status rather than requiring 0 |
| Bare `OQ-1` references | `tasks.md` T2/T3/T4/T5/T6 status lines → `OQ-1a` decided / `OQ-1b` gates the merge; `requirements.md` outcome table header → "OQ-1b outcome"; "Still genuinely open" closing sentence → `OQ-1b`; traceability row → "OQ-1a (decided), OQ-1b (open)". The one remaining bare `OQ-1` is `requirements.md:102`, which names the parent question in order to split it |
| 16.3's nonexistent carve-out, and "zero occurrences" | 16.3 now names **one** carve-out, the #436 title at `research.md:241`, and says the "installed skill's description" carve-out does not exist. A grep of `research.md` for every Criterion 1, 2 and 4 form finds only that title. `research.md:288`'s "declarative" is recorded as a different sense. The Requirement 16 preamble now says one occurrence, not zero |
| 8.11 should name every parametrised site | Done, and widened to every two-package site (ten), see B |
| Gitignored-path warning | End block check 4, a warning only; shown firing on the clean case |

**Attribution sweep.** Per-file counts of provider, vendor and model names were identical before and
after these edits (`requirements.md`, `design.md`, `tasks.md`), so this pass added none. Pre-edit copies
are at `/tmp/cao-apl-{req,design,tasks}.before.md` if review 6 wants a diff.

### Found and NOT fixed, for review 6 to rule on

Outside this brief, so recorded and left alone:

- `design.md` § Forward vocabulary constraints, row 2, states "`GENERATIVE_UI` is not an AG-UI 1.0 event type" as a reason, while Requirement 16.2 forbids stating it as fact until `P-65` cites the AG-UI specification.
- `design.md` "Excluded from the ladder" says any check reading **staged** state is "unsatisfiable while OQ-16 is open". OQ-16 is decided, and the new scope check lists staged files as candidates (it requires none).
- `tasks.md` out-of-scope row "Any commit or push" still says "Until OQ-16 is answered there is no route to a PR".
- `tasks.md` T4 defect 2 says Requirement 13.8 forbids a commit "while OQ-16 is open".

### Frozen for review 6 (round 1, superseded by the round-2 freeze below)

| File | Lines | `shasum -a 256` |
|---|---|---|
| `requirements.md` | 668 | `50259d7ee4830972b4c537d4f6e7c8f17d97c6bce360d813ea537ec925459166` |
| `design.md` | 493 | `642c9035f413f16417e60fb0a57e5880c56d2706eddf2214e0f5a5a55417ea1d` |
| `tasks.md` | 822 | `5d2aa04967075d5ef4eddf66f8c91af3a378fb99e439687811a537d7a40b6cf4` |

Review 6 covered: this checkpoint's A–D; the 2026-10-30 delta (`requirements.md` 10.9, `design.md`'s
runnable-forms block, the T2 criteria); **B-6, which review 5 did not verify**; and whether the other five
review-4 fixes landed in full. Before declaring the freeze, check that no `pending` inbox message is addressed to the
author seat.

### Frozen for review 7 (round 2, superseded by round 3)

| File | Lines | `shasum -a 256` |
|---|---|---|
| `requirements.md` | 2 | `db2d087e072d2ca740b34957adbfcb38f1244689b333eab87263c48376301956` |
| `design.md` | 0 | `d00dffef15bf43ec8264ede35a42edb935cbdefe8745ffc55add01502270e3ad` |
| `tasks.md` | 17 | `2d91e8cf142a0b4ea2ed82e06779953bbbf642bbaf0c1601368b91ca7550d5d7` |

Review 7 must cover: R6-B-1's three parts; N-1's renumbering, including that every reference resolves
to the criterion it means; the rewritten hazard-4 end block (N-4, N-5, and the `case` to `if` change);
T5's two new runnable blocks; and the `design.md` decided/open sweep (N-10). **N-11 stays open for
the user.** Before declaring the freeze, check that no `pending` inbox message is addressed to the
author seat.

## Checkpoint 2026-10-30

Work stopped for the night on the user's instruction, mid-step. Resume from this section.

### Tree state — consistent, nothing in flight

| Fact | Value |
|---|---|
| Worktree | `/Volumes/workplace/open-source/cao-agent-plugin-lifecycle`, branch `feat/agent-plugin-lifecycle` |
| `HEAD` | `00611d119ce6e8c8a940929f4f59c58e34a8ea2e` — unchanged; also `upstream/main` |
| **Local commits** | **NONE.** `git rev-list --count upstream/main..HEAD` = **0**. No sha and no `%G?` to report, because no implementation commit was made. The `%G?` of `HEAD` is `E` (cannot be checked) and it is upstream's commit, not ours. |
| Pushes | none, to either repo |
| `git status --short` | `?? docs/issues/1153-agent-plugin-lifecycle/` only |
| Staged | nothing (`git diff --cached --name-only` empty) |
| harness-oss | **untouched** — clean status at `c422584`, no branch created, nothing written |
| `validate_markdown_links.py` | exit **0** |
| No half-applied edits | confirmed: every structural heading appears exactly once; 16 requirements with 0 duplicate numbers; 66 provenance rows with 0 duplicate ids; 8 tasks |

### Files at stop

| File | Lines | In the PR? |
|---|---|---|
| `requirements.md` | **660** | yes |
| `design.md` | **491** | yes (trimmed to final design + provenance) |
| `tasks.md` | **606** | no — untracked working record |
| `research.md` | 318 | no |
| `blog-outline.md` | 189 | no — deferred, stale by design |
| `review-1.md` / `review-2.md` | 291 / 167 | no |
| `STATUS.md` | this file | no |

### Done today

- **GO decisions applied.** OQ-1/3/4/5/6/7/12/13/16/17 converted from questions into requirements, each naming its authority as **the user, 2026-10-30**, with a preamble stating that **none is a maintainer answer**. 16 requirements; Requirement 15 (OQ-17 sizing) and Requirement 16 (AG-UI vocabulary) added.
- **Rebased onto `00611d11`; #1121 cited as merged.** Every `a64bbc76` / "open #1121" / `556726a4` reference purged or recorded as a deliberate supersession note. Nearly every `build_agent_plugin.py` citation re-verified by *reading*, since four locations changed content and not merely position.
- **Blog deferred out of the PR.** T8 deleted; Requirement 12 bannered **DEFERRED, NOT DELETED**; 12.14 (verbatim-quotation carve-out) kept in force because it governs quotations generally.
- **Review 4 returned six blocking findings; all six fixed.** B-1 scope recipe, B-2 T6 command, B-3 OQ-1 split, B-4 provenance claim, B-5 ladder header, B-6 Requirement 15 self-contradiction. Full non-blocking list applied.
- **Trailer figure corrected to 16 of 19** at `00611d11` (2026-10-30), recounted rather than relayed.
- **Attribution directive holds.** Sweep across all seven files for provider, vendor **and model** names returns only the three ratified verbatim carve-outs.

### In progress at the stop

- **Review 5 WAS DELIVERED, as a PARTIAL review. Verdict: NOT CLEARED — one blocking item (R5-1).**
  B-2, B-3, B-4 and B-5 are **cleared**; B-1 is cleared apart from R5-1; **B-6 was not verified** (only
  Requirement 2.12 at `:239` was confirmed — advisory, no detection claim). The reviewer could not pin
  cleanly to 653/443/603 because its reads ran 02:34–02:37 and straddled the writes, so some quoted
  lines come from the moved tree. **It did not review `design.md`'s +48 lines.**
- **Two further inbox messages** were unread at the stop (ids 370, 371).

### R5-1 — the one blocking item, and it is MEASURED, not inferred

**The gate scripts depend on which shell runs them, and this machine's login shell is `/bin/zsh`.**
The reviewer could not run commands and asked for confirmation; the supervisor ran it:

| Test | `zsh` (this machine) | `bash` |
|---|---|---|
| `[ file -nt /missing-stamp ]` | **false — nothing prints, so the scope check PASSES ON ANY TREE** | true — prints, fails loudly |
| `${PIPESTATUS[0]}` under `set -u` | **`parameter not set` → the block aborts** | works (`0`) |

- `echo $SHELL` and `dscl . -read ~/ UserShell` both report `/bin/zsh`.
- zsh's equivalent is lowercase `pipestatus`, 1-indexed (`${pipestatus[1]}` returns `0`).
- `bash` here is **3.2.57** (macOS's ancient build), so the reviewer's secondary concern — that `-nt`
  may compare whole seconds and miss a write inside the stamp's first second — also applies.
- **T6 (`tasks.md:452-494`) cannot pass under zsh** because of `${PIPESTATUS[0]}` at `:469` under `set -u`.
- **T3 (`:288-295`) passes on any tree under zsh**: it tests `-nt` against `/tmp/cao-apl-t3.stamp`,
  never creates it, and nothing checks it exists. Hazard 4 creates the stamp only in its own example.
- **Fix (verified to behave in both shells):** replace `[ "$f" -nt "$STAMP" ]` with
  `find "$f" -prune -newer "$STAMP" -print`, which errors loudly on a missing stamp in **both** zsh and
  bash, checks the link rather than its target (closing the broken-symlink blind spot), and compares
  sub-second mtimes. Additionally run every "Command that must pass" under an explicit
  `bash -euo pipefail <<'EOF' … EOF`, and add `test -f "$STAMP"` before each scope check.

**This is the ninth instance of the recurring class and a NEW mechanism: a check whose verdict depends
on the interpreter, which in the default shell passes on any input.** It is again inside the
fix-for-a-fix. The lesson for tomorrow: the fleet's "what makes it fail, what makes it pass" test
assumes a fixed interpreter, and this machine's interactive shell is not the one the scripts assume.

### Unreviewed delta — read this before trusting review 5

Review 5 was dispatched against `requirements.md` **653** / `design.md` **443** / `tasks.md` **603**, verified at dispatch. The live files are **660 / 491 / 606**, written at 02:34:04 and 02:34:28, *after* dispatch.

**Cause, recorded because it is a supervisor error and will otherwise be mistaken for worker drift:** the supervisor sent an amendment (message 361) while oss-docs was still processing the main fix list (360). CAO held it `pending` and delivered it the moment that seat went idle, so it was applied correctly, promptly, and inside the review window. The freeze protocol adopted earlier — *a worker acknowledges the specific instruction by message id before a reviewer is dispatched* — closes the case of a worker with unfinished work. It does **not** close the case of a **supervisor with an undelivered instruction in flight**. The missing rule: **before declaring a freeze, confirm there are no `pending` messages addressed to that worker.** The `inbox` table shows this plainly and it was not checked.

Consequence: **48 lines of `design.md`, plus additions to the other two files, have not been seen by any reviewer.** Whatever review 5 says is pinned to 653 / 443 / 603. The delta is now known precisely — three changes, reported by the author after the freeze:

1. **`requirements.md` — new Requirement 10.9**, making the no-executable-content-in-table-cells fix a requirement rather than a convention. It scopes itself to content *intended to be copied and run*, leaving a prose mention of a command name unaffected, and it carries the measurement (`echo a | grep -E 'a\|b'` exits 1; `echo a | grep -E 'a|b'` exits 0) plus the test that catches the class: **run the command as published, copied out of the rendered document.**
2. **`design.md` — a new authoritative runnable-forms fenced block after the gate ladder**, because the author swept every table and found **one more latent instance nobody had named**: the gate ladder is itself a table of commands, uncorrupted today only because no cell currently contains a pipe, and one added `| wc -l` from the same failure. The block carries all nine gates in copyable form (gate 1's `--skills-dir`, 5c's "catches nothing" note, gate 7's `-p no:cacheprovider` as observed, gate 8's **†**), and states that it is authoritative and the table is a summary.
3. **`tasks.md` — three T2 criteria that B-6 required and that had NOT landed.** Requirement 2.12 was written correctly but no task carried it, which is precisely the defect B-6 was raised to fix — an obligation no task carries cannot fail. The criteria test that the advisory listing **is emitted** (not that a mismatch is detected), that the finding is classified `advisory` and does not by itself change the exit status, and that the output renders no verdict on meaning.

Tomorrow's round must cover these three. Note that item 3 means fix list 360 was **incompletely applied** until the amendment pass, so review 6 should re-check the other five blocking fixes landed in full rather than assuming they did.

**The unreviewed surface is exactly those three spans, proven by arithmetic rather than asserted:**
`+7` (Requirement 10.9, `requirements.md:409-415`), `+48` (the runnable-forms block, `design.md:276-322`)
and `+3` (the T2 criteria, `tasks.md:231-233`) sum exactly to the observed 653→660, 443→491, 603→606.
**There is therefore no fourth unaccounted edit.** Review 5 saw everything else unchanged, including all
six blocking fixes B-1…B-6; the amendment added one requirement, one authoritative command block, and
the missing task criteria for an obligation that had already been reviewed. It changed no verdict, no
decision and no provenance row. Integrity at the stop: zero duplicate `##` headings in all three files,
and fenced-block delimiters even in every file (0 / 8 / 14), so nothing is left mid-block.

`requirements.md`'s remaining command-bearing table cells are deliberate: they are provenance *evidence*
recording what was run, not instructions to copy, and Requirement 10.9's scope says so.

### The exact next step

1. **Read the inbox** (ids 370, 371, and any review 5 result).
2. **Route the parked release-path findings to oss-docs** — they were deliberately withheld so they would not move the tree during review 5. Two of them change what the document may claim:
   - The dogfood CI job (`ci.yml:509-561` → `run.sh`): **at `00611d11`, `run.sh` names `agent-plugin/cao` and no other package** (`:93-94`, `:115`, `:272-273`). So **any claim that the third package is "dogfooded in CI" is false** without an edit to `run.sh`. "Gated in CI by `make check-agent-plugin`" is true with no edit.
     - *Scope of that evidence, stated because an earlier draft of this checkpoint overstated it.* The verified claim is about the file **at this sha**, not about history. "Has never covered `cao-contributor`" was a claim about the past that nobody checked, and it was written here by the supervisor rather than by the seat that did the reading — the seat flagged it and the wording is corrected. `tools/record-dogfood-demo.mjs` was also not read, so it may carry assertions of its own. The conclusion is unchanged either way.
   - The third package **must be first built at the held 2.5.3 pin**, via in-process `build_package(config, committed_package_version(), PACKAGES_DIR)` then `make check-agent-plugin` — **never `make agent-plugin`**, which writes all packages at 2.5.4, moves the pin, and is forbidden for a contributor PR by `cao-contributing`'s checklist item 7. If the packages disagree, `committed_package_version()` returns `None` and **every** package reports CONTENT DIFFERS.
   - Also: `test_packages.py`'s parametrize lists (`:42`, `:50`, `:54`, `:67`, `:83`, `:216-218`, `:224-226`, `:326-339`) **pass with a third package while not covering it**. Requirement 8's "one line of data plus `CODEBASE.md:53`" is incomplete; five further sites name exactly two packages.
   - Safe, verified, no action: the release job and `--require-bounded-client` handle a third package (the MCP gate is global — `any(config.ships_mcp …)`), and `--require-current-pin` is **not** a defect (the `version` field means "the CAO release this package is pinned to", documented in the generated CHANGELOG, with precedent on `main`).
3. **Fix R5-1** (above) — the shell-dependence blocking item. Measured, so no further investigation is
   needed before fixing it.
4. **Then review 6**, which must cover: the parked release-path findings; the three unreviewed changes
   of the 02:34 delta, **especially `design.md`'s +48 lines**; **B-6, which review 5 did not verify**;
   and R5-1's fix. Freeze first — and this time check for `pending` messages to the worker before
   declaring the freeze.
5. **Only then implement** waves 1–5 without T8, `cao-agent-plugin-creator` first because Criterion 15.5
   makes the ordering a requirement. Signed commits (`-S`), author plauzy, exactly two trailers,
   **no push**. Full suite once at the end in shards (`/tmp/1121-shards2.sh`; a single process exhausts
   this Mac's file-descriptor limit).
6. Finish with this file set to `READY TO PUSH`, listing commit shas with `%G?`, every gate with its
   exit status, the two T9 verdicts, and the harness-oss branch.

**Non-blocking items review 5 raised, worth folding in during step 3:** deleting an *untracked* file is
still invisible (`-d` covers tracked files only), which includes the seven untracked spec files that
13.7 protects; B-2's existence-check rationale is wrong as written, since a quoted real path is never
read as a redirect — that only happened with the literal placeholder; bare `OQ-1` references still blur
the halves at `tasks.md:190`, `:248`, `:302`, `:349`, `:406` and `requirements.md:620`, `:651`,
`:106-107`; 16.3 cites a `research.md` carve-out that does not exist ("renders in any" appears only in
our own prohibitions) and `:568` still claims "zero occurrences"; and 8.11 should name all six
parametrised sites. The reviewer also **accepted** the gitignored-path trade, with the reasoning that an
ignored file cannot be staged without `git add -f` and so cannot reach a commit, which is what the scope
check exists to protect — its suggested mitigation is to run the same filter over
`git ls-files -o -i --exclude-standard` and print the result as a **warning**, not a failure.

### Open questions

**Blocking the merge, not the work:**
- **OQ-1b — does the maintainer reverse, narrow or uphold #573 D4?** Open. OQ-1a (the user's decision to *proceed*) is decided; the two were split precisely so a user decision could not masquerade as a maintainer answer. Requirement 14.1 now says that if D4 stands the PR is **withdrawn unmerged**, and 14.4 gates the **merge**, not the work.

**Needing a user decision:**
- **OQ-17's scope.** Decided in principle, **open in scope**. Measured as **three to five tasks plus two approval gates** (~1,900 repository lines by the plan's own estimate) in a different repository with its own gates and no `upstream` — roughly the size of this entire specification. The floor that is still a real dogfood is M2 + M4, labelled a floor. Not picked by the fleet, per the GO's instruction to report rather than shrink.
- **GO versus the relayed devops review.** That review says *"Holding the 2,000-line spec until D4 resolves — correct, keep it."* The GO proceeds and implements now. The GO is later and it is the user's call. B-3 is written so **either** outcome survives: the work proceeds, the merge is gated, and the PR reads as a proposal a maintainer can decline.
- **Whether to claim CI dogfooding** for the third package, which requires the `run.sh` edit above and is new scope.

**Unverifiable without authorisation:**
- Whether 2.5.4's published sdist passes `verify_bounded_client` — decides whether the held pin can move. Needs a networked run the GO does not authorise.
- `record-dogfood-demo.mjs`'s own assertions — only matters if CI dogfooding is accepted.

**Informational:** OQ-2, OQ-11. **Resolved:** OQ-15 (#1153 is the issue of record, parent #1154, sibling #1152).

---

> **Issue of record:** [awslabs/cli-agent-orchestrator#1153](https://github.com/awslabs/cli-agent-orchestrator/issues/1153)
> · **Parent tracker:** [#1154](https://github.com/awslabs/cli-agent-orchestrator/issues/1154)
> · **Sibling:** [#1152](https://github.com/awslabs/cli-agent-orchestrator/issues/1152)
>
> **Phase:** specification only. **Nothing is implemented, committed or pushed.**
> **Worktree:** `/Volumes/workplace/open-source/cao-agent-plugin-lifecycle`, branch
> `feat/agent-plugin-lifecycle`, HEAD `556726a4` (unchanged since the fleet started).
> Fork-bound: `origin` = plauzy, `upstream` = awslabs. **Never push to `upstream`.**
> **Written:** 2026-10-29.

## SPEC READY FOR USER REVIEW

Three review rounds by an independent read-only reviewer seat (with an advisor) returned **no
remaining blocking findings**. The reviewer pre-committed the condition in review 3: *"When they are
fixed, 'ready for user review' is warranted."* All three items it named — B-1, B-2 and B-4 — are
closed and independently verified (see [Verification](#verification-what-was-actually-run)).

**Ready for user review does not mean ready to implement.** Three open questions block
implementation and are the user's or the maintainer's to answer, not the fleet's.

## The deliverable

| File | Lines | Purpose |
|---|---|---|
| [`requirements.md`](requirements.md) | 531 | 14 requirements, EARS form, `Requirement N.M` citations; 65-row Provenance table; 17 open questions; traceability matrix |
| [`design.md`](design.md) | 427 | Skill layouts, the shift-left gate ladder, correctness properties P1–P8, the three-option host trade-off, carried-forward unknowns |
| [`tasks.md`](tasks.md) | 616 | 9 tasks in 5 waves, disjoint file ownership, adversarial defect lists, exact commands with expected output |
| [`blog-outline.md`](blog-outline.md) | 189 | Title options, thesis, section plan with per-row evidence, figures, evidence appendix, unevidenced-claims list |
| [`research.md`](research.md) | 318 | The factual record every other file cites |
| [`review-1.md`](review-1.md) | 291 | Review 1 verbatim + the binding attribution directive |
| [`review-2.md`](review-2.md) | 167 | Review 2 verbatim + supervisor verification of disputed items |

## Open questions — the user's decisions

**Blocking.** Implementation cannot start until these are answered.

- **OQ-1 — Does the maintainer reverse, narrow, or uphold #573 decision D4?** D4
  (`573/design.md:151`, repeated `:862`, `:1172`) records that a CAO agent-plugin authoring skill is
  **out of scope**. This specification is the thing D4 scoped out. It is written so all three outcomes
  are reachable, and **Requirement 14 makes "not implemented" a specified outcome** rather than a
  failure. #1153 leads with this question so it reaches the maintainer who recorded it.
- **OQ-16 — May the implementation phase produce a commit, and later a push?** An earlier
  Requirement 13.8 forbade a commit in "the change", which made the implemented feature **impossible
  to turn into a pull request**. Proposed re-scope: bind the prohibition to the specification phase,
  with a separate explicit user approval for a commit and another for a push. The charter forbids
  commits, so this cannot be re-scoped without the user. **Until it is answered this feature has no
  route to a PR.**
- **OQ-17 — Accept that only the audit half is dogfooded?** `Audit_Skill` is dogfooded;
  `Creator_Skill` is **not**, because no task uses it to author the package. Charter goal 2 names both.
  The spec records this as a deviation and rejects both ways of concealing it — re-claiming "guided
  by", and inventing a throwaway package to author, which "would manufacture evidence for a claim
  rather than earn it". The smallest honest fix is a scope increase for the user to approve.

**Also blocking a specific requirement:** OQ-4 (which validator `Audit_Skill` wraps), OQ-7 (host
location for the dogfood package — a third `PackageConfig` recommended; extending `cao-contributor`
conflicts with open #1121 at head `a64bbc76`; `harness-oss` rejected), OQ-12 (the package's name,
which may pre-empt #573's open M2/M4 namespace decisions).

**Open, with recommendations:** OQ-2, OQ-3, OQ-5, OQ-6, OQ-8, OQ-9, OQ-10, OQ-13, OQ-14. OQ-11 is
informational; **OQ-15 is resolved** by #1153 itself.

## Attribution directive — applied, and what it cost

The user's standing rule (2026-10-27) **overrides the charter's blog goal**. No sentence in this
repository's PRs, issues, docs or blog posts may state that any coding agent other than Kiro wrote,
reviewed or co-developed anything; no foreign trailers, no session lines, no fleet seat described by
provider. An "exclusively kiro-cli" substitution is equally forbidden. Recorded in full at
[`review-1.md`](review-1.md) `## Attribution directive`.

Applied across all seven files. A sweep for provider, vendor and **model** names returns only three
carve-outs, each a verbatim third-party artifact: the `migrate-agent-plugin` fixture description
(`requirements.md:67`), the merged `#1107`/`#1115` PR titles (`research.md:243-244`), and the
spec-mandated `.claude-plugin/` path. **Requirement 12.14 generalises the carve-out:** a quotation of
a third-party artifact is reproduced verbatim, because a naming rule applied to a quotation corrupts
the evidence it was quoted for.

**Declared evidence loss.** Recorded so a reader can tell material removed *by rule* from material
never found. None of it changes the trailer figures.

1. Provider, profile and session attribution of the four PR #1121 fleet seats.
2. A model pin for one seat.
3. A quoted user request from a session log.
4. **The existence of a commit on `main` carrying an additional non-Kiro co-author trailer** — withheld
   without naming the commit. Listed explicitly because this specification's authorship evidence *is*
   trailer data, so a reader should know that one trailer fact was removed by rule.

Also withdrawn: CAO's `terminals` rows showing the #1121 fleet's seat composition by provider. It was
the strongest single piece of evidence the supervisor contributed, and it evidences a claim that may
no longer be made. Requirement 12.11 carries an explicit **"SHALL NOT be reintroduced"** note, because
`review-2.md`'s own F-6 fix text would otherwise instruct a future revision to add it back.

Planning-folder filenames that encode an agent are **withheld**, and those artifacts are cited by
role. The role-to-filename mapping is deliberately **not recorded in this repository**. The briefs
live in `.agents/plans/pr1121/` and are available to the user.

**Authorship, as the trailers record it.** 15 of plauzy's 18 commits on `main` at
`9d029f9d4db16df2725bd04751756fd0b7d27440` (2026-10-29) carry the Kiro co-author trailer, and all 15
Kiro-trailer commits on `main` are his. Recount with
`git log 9d029f9d --format='%an%x09%(trailers:key=Co-authored-by,valueonly)'`. Requirement 12.13
requires the post to **re-run this at the sha it publishes against** and not inherit the figure —
including from this document — and to state that the count measures authorship only if the trailer is
applied where a Kiro session actually co-authored the commit.

## Verification — what was actually run

- `uv run python scripts/validate_markdown_links.py` → **exit 0** (`docs/issues/` is not excluded, so
  all seven files and their internal anchors are checked).
- `git status --short` → only `?? docs/issues/1153-agent-plugin-lifecycle/`. `git log --oneline -1` →
  `556726a4`. **No commit, no push, no implementation.**
- Attribution sweep for provider/vendor/model names across all seven files → only the three carve-outs.
- **B-1's defect and its fix were both measured, not argued:** appending to an already-untracked file
  produces **no difference** in a `git status --porcelain --untracked-files=all` diff, so the previous
  scope check was blind to content edits — and because nothing commits while OQ-16 is open, every file
  in the tree is untracked, including the seven specification files that Requirement 13.7 protects. The
  replacement `find -newer` recipe was shown to detect exactly that edit.
- **B-2's remedy contained the defect it was fixing, and this was measured:** `grep -F -f` treats an
  empty pattern line as matching anything, so the supervisor's proposed check passed on a report whose
  only content was unrelated text (exit 0); with blank lines stripped it correctly failed (exit 1).
  Reproduced independently by the supervisor.
- Gate exit statuses in `design.md` are split into **observed** and **not repo-reproducible, or not
  observed**. Gate 9 (the Docusaurus build) is **never presented as a pass**; CI enforces it on
  `pull_request` for `docusaurus/**`.

## Known non-blocking residuals

Listed rather than silently carried.

- `tasks.md:524` (T8 defect 7) still describes Requirement 12.11 as forbidding a count "as a measure of
  effort or scale" and permitting others. 12.11 is now **exhaustive at four kinds**, so that
  description is stale. Routed to the owning seat; it misdescribes a requirement rather than weakening
  a gate.
- **Round 9's new text was not independently re-reviewed.** The `find -newer` recipe, its six
  documented blind spots, the `PIPESTATUS` audit capture, the blank-stripped pattern check, OQ-17, and
  the 12.13 measurement-integrity clause postdate review 3. The reviewer pre-committed that closing
  B-1, B-2 and B-4 warrants readiness, and both closures were empirically verified above — but the
  fleet's own history is that **a fix introduces a defect of the same class as the one it fixes**
  (B-1 inside F-2's fix; the `grep -F` hole inside B-2's fix). A fourth review round is the obvious
  next step if the user wants that risk closed before implementation.
- `research.md`'s unresolved items are carried in `design.md` rather than resolved: whether
  `cao plugin validate` admits an over-limit skill is **inferred from code, not run** (T3 is the
  experiment that would settle it), and the provenance of the two installed source skills is genuinely
  unknown — no git history anywhere.

## What this fleet learned about itself

Recorded because the specification's own subject is shift-left gates.

- **Six blocking findings were one recurring defect:** a check that cannot fail and a check that
  cannot pass are the same error — a gate whose exit status is decorative. Instances: `git diff`
  omitting untracked files; a count over a table other actors write to; per-task snapshots under
  concurrent siblings; one exit code for two indistinguishable causes; a status-line diff blind to
  content edits; and `grep -F` with an empty pattern. The working rule: **before writing a check, ask
  what input makes it fail and what input makes it pass; if either answer is "none", it is
  decoration.** It must be applied to fixes, not only to original work.
- **An identifier that can go stale is weaker evidence than the thing it points at.** A line number
  pinning the quotation carve-out, a provider-encoding profile name, and an abbreviated sha each looked
  like precision and were hostages to change. The carve-out is now self-identifying *at the quote*.
- **Compliance can create an overclaim.** Removing foreign attribution left a gap that read as Kiro
  authorship (B-4), and citation *asymmetry* — naming one seat's artifacts while withholding
  another's — disclosed by omission what no sentence stated. Neither is detectable by a keyword sweep.
- **A `completed` terminal status is not evidence a result was delivered.** Review 1 was produced and
  never sent; it was recovered from the still-idle reviewer's context, because the pane scrollback was
  gone and the persisted terminal log is raw capture unsafe for quoting a finding.
