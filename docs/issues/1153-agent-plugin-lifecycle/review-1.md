# Review 1 — spec review of the agent-plugin-lifecycle spec

> **Issue of record:** [#1153](https://github.com/awslabs/cli-agent-orchestrator/issues/1153) ·
> **Parent tracker:** [#1154](https://github.com/awslabs/cli-agent-orchestrator/issues/1154) ·
> **Sibling:** [#1152](https://github.com/awslabs/cli-agent-orchestrator/issues/1152)
>
> **Reviewer:** an independent read-only reviewer seat — `fs_read`, `fs_list`, `@cao-mcp-server`; no
> write tools and no command execution. Identified by terminal `d883ee05`, session `cao-apl`. The seat's
> profile name and provider are deliberately omitted, because the profile name itself encodes a
> provider — see the **Attribution directive** below.
> **Advisor:** consulted. See [Advisor consultation](#advisor-consultation).
> **Reviewed:** 2026-10-29, concluded 16:46 local, 10m38s.
> **Verdict:** **not ready for user review** — six blocking findings, each a one-revision fix.
>
> **Transcription provenance.** The reviewer seat cannot write files, so the supervisor (`oss-sup`,
> terminal `9feec10a`) transcribed this file, as the charter directs. The review is reproduced
> **verbatim** from the reviewer's own three-part resend; the reviewer confirmed the supervisor's
> independent reconstruction of F-1, F-2, the advisor section, the evidence section and the assessment
> matched its conclusions before this file was written.
>
> **Delivery note, recorded because it is a reusable lesson.** The reviewer completed its work and
> returned to its prompt **without calling `send_message`**, so CAO recorded the terminal as
> `completed` with no inbox row and no callback. The pane scrollback was later lost (47 lines
> retained) and the persisted terminal log is raw capture with words mangled by redraws — not a safe
> source for quoting a blocking finding. The review was recovered by asking the still-idle reviewer to
> resend from its own context. **A `completed` status is not evidence that a result was delivered.**
>
> **Paths.** This directory was renamed from `docs/issues/agent-plugin-lifecycle/` to> `docs/issues/1153-agent-plugin-lifecycle/` after the review was written. Line numbers in the
> findings below are unaffected; only the directory moved.

---

## Attribution directive (binding, overrides the charter)

Relayed 2026-10-29 by the PR #1121 supervisor, from the user's standing rule of 2026-10-27 for
`awslabs/cli-agent-orchestrator` and `ag-ui-protocol/ag-ui`. **This overrides the charter's blog goal**,
which had asked the post to show Kiro driving other providers' sessions as reviewers.

1. **Nothing authored by another coding agent may be visible anywhere** in this repository's PRs,
   issues, docs or blog posts: no foreign trailers, no session lines, and **no sentence stating that
   another agent wrote, reviewed or co-developed anything**. Commits carry exactly two trailers,
   `plauzy` and `Kiro Agent`.
2. **Remove** every claim and evidence row asserting foreign-agent authorship or review, **including
   the #1121 fleet seats described by provider**. The post may describe **kiro-cli authoring and CAO
   orchestration only**.
3. **Do not substitute an "exclusively kiro-cli" claim either.** Describe what the Kiro trailers show:
   **15 of 18** of plauzy's commits on `main` at **`9d029f9d`** (2026-10-29), date-stamped, with the
   recount command given so a reader can reproduce it.
4. **Spec-only still applies**, and #1153 is blocked on D4, so no implementation planning beyond the
   current draft.

**One carve-out, so compliance does not corrupt evidence.** `requirements.md:54` quotes the
**verbatim upstream description** of the `migrate-agent-plugin` fixture, which enumerates client names
("Migrate an existing Claude, Copilot, Codex, Cursor, Kiro, VS Code, or other client-specific agent
plugin…"). That is a quoted third-party artifact listing *clients a tool supports*, not a claim that
any agent authored or reviewed work here. It **stays verbatim**. Silently editing a quotation to
satisfy a naming rule would be an evidence-integrity failure of exactly the kind F-1 and N-A catch, and
would make the D4 argument rest on a doctored quote.

**Consequence for this review.** The provider and model attribution of the reviewer seat is removed
from both review files, and the strongest single piece of evidence the supervisor contributed — CAO's
`terminals` rows showing the #1121 fleet's seat composition by provider — is **withdrawn from the
spec and the blog outline**. It was good evidence for a claim that is no longer permitted to be made.

---

## Blocking findings

**F-1: The D4 argument's "stronger half" can be rebutted with the very file it cites.** `requirements.md:52`, `:63`; Requirement 14.6; `design.md:15`, `:57`.
- **What's wrong:** The heading says the auditing gap is one "that no existing skill fills", and `:63` says "D4's premise says nothing about auditing". The skill D4 names says otherwise, in two places:
  - Its description (`…/migrate-agent-plugin/SKILL.md:3`) ends "Use when auditing, converting, or modernizing an agent plugin."
  - Its bundled `references/validation-checklist.md` audits three of Requirement 2.4's five checks: the name length and character rules (`:13`), Agent Skills naming rules (`:22`), and folder-equals-`name` (`:22`). It also checks that the description says what and when (`:23`).
- **What is still genuinely uncovered:** the 1024-character description limit, the 500-line body limit, and *mechanical* enforcement by anything CAO ships. The checklist is prose for a person to tick, not an enforced check.
- **Why it blocks:** D4's author only has to open the fixture the spec cites to show the stronger half is overstated.
- **Minimal fix:** Narrow the claim in `:52`/`:63` and in 14.6 to: "No artifact CAO ships mechanically enforces the 1024-character and 500-line limits, or the name regex. The D4-named skill's checklist covers naming manually and claims an auditing trigger." Cite `validation-checklist.md:13,22`. The text of D4 does speak only to authoring, so that sentence can stay, but it can no longer carry the argument alone.

**F-2: Spec-level acceptance criteria that read git state are vacuous or can never pass on this tree.** `tasks.md:93`, `:146`, `:291`, `:395` (vacuous); `:231`, `:191`/`:198` (can never pass); Requirement 13.8.
- **Vacuous:** `git diff --name-only` does not list untracked files. T1 and T2 create only new, untracked files, so their "lists only paths under skills/…" check prints nothing and passes whatever else got written. T5 and T7 have the same hole for their new directories.
- **Can never pass (T4):** `git ls-files src/cli_agent_orchestrator/skills/ | grep -c SKILL.md` keeps printing 14 until the mirror is staged. Nothing ever stages it: Requirement 13.8 forbids commits and `tasks.md:50` discourages staging.
- **Can never pass (T3):** `test -z "$(git status --porcelain)"` fails today. The five spec files are untracked: `.gitignore` has no `docs/issues` entry, and the charter keeps them uncommitted.
- **The root cause is Requirement 13.8.** It forbids a commit in "the change", which makes the implemented feature impossible to turn into a PR.
- **Why it blocks:** this is P5's own hazard (a gate whose exit status looks authoritative but measures nothing) in the spec's own checks.
- **Minimal fix:**
  - Replace the scope checks with `git status --porcelain --untracked-files=all`, diffed against a snapshot taken before the task.
  - Replace T4's `ls-files` count with `find src/cli_agent_orchestrator/skills -name SKILL.md -maxdepth 2 | wc -l`.
  - Make T3's check "porcelain unchanged from before", not "empty".
  - Re-scope 13.8 to the spec phase, with commit and push needing a separate explicit user approval.

**F-3: The ladder's first gate depends on the hole the feature exists to fill.** `design.md:255` (gate 1), `:264` (gate 8); Requirements 1.10, 2.9, 11.2; `tasks.md:85`, `:97`, `:135`, `:150`.
- **What's wrong:** `<validator>` and `<runner>` are never resolved. research.md:194 shows the validator is `$S/cao-skill-creator/scripts/validate_skills.py`. That script is not tracked in the repo (P-11), its provenance is unknown (P-14), and it is not on a fresh clone. `requirements.md:58-60` names exactly this as the gap.
- **The contradiction:** Requirement 6.2 says the source skills are "design input only", yet 11.2 and T1/T2's "Command that must pass" run their script.
- **Why it blocks:** a maintainer's first question is "where is `validate_skills.py`?", and the honest answer is "on one machine". 1.10 and 2.9 cannot be tested from the repository.
- **Minimal fix:** Name the installed path explicitly as a bootstrap gate, with the provenance caveat. State that T2's bundled script (option B or C) replaces it once it exists, and order T1's validator check after T2 lands. Spell out the path in place of the placeholder everywhere.

**F-4: The ladder breaks its own Requirement 11.1.** Requirement 11.1; `design.md:251`, `:264-265`.
- **What's wrong:** 11.1 says the ladder holds "only commands whose exit status has been observed", and `design.md:251` repeats "Every command below has an observed exit status". Gate 9 is marked **not run**. Gate 8's "varies (P-38)" was observed only on the *installed* `cao-skill-creator`, never on these skills.
- **What is right:** gate 9 is correctly never shown as a pass.
- **Why it blocks:** the spec breaks its own acceptance criterion on the property it is selling.
- **Minimal fix:** Split the table into "observed" and "to execute (not observed)", or amend 11.1 to "observed, or explicitly marked not run". gh-pages.yml runs on `pull_request` for `docusaurus/**` (`:30-32`, build `:69`), so gate 9 is enforced before merge in CI. Say so.

**F-5: Charter-required content is silently missing, and the dogfood claim has no task behind it.**
- **The claim:** `requirements.md:15` says the package is "produced by the skills it carries", and `design.md:179,181` says "built by the skills it ships".
- **The tasks don't do that:** Requirement 8.1 and T5 produce it with `build_agent_plugin.py`. No task runs `Creator_Skill` or `Audit_Skill` against the `Dogfood_Package` or records a scorecard.
- **The charter asks for more:**
  - Charter :18-20 puts `cao-learning` (outcomes and lessons) in the lifecycle.
  - Charter :60-63 asks `design.md` to cover where outcomes and lessons are recorded, an install smoke test, and the fleet story.
  - A grep for `learning|fleet|smoke` across requirements, design and tasks returns nothing.
- **Why it blocks:** the blog's central claim and a charter deliverable are not reached by any task.
- **Minimal fix:**
  - Add a task, between T5 and T6, that runs `Audit_Skill` on `agent-plugin/<new-pkg>` and records the findings, then records `report_outcome` or a lesson per `cao-learning`.
  - Name gate 7's `test_packages.py:310-341` real-pipeline install as the install smoke test.
  - Either specify the fleet story or point to `blog-outline.md` §8 explicitly. Otherwise record each item as a Non-Goal with a reason.
  - Soften "produced by" to "guided by / audited by".

**F-6: Requirements 12.10 and 12.11 contradict each other, and 12.11 contradicts the charter.**
- 12.10 says `blog-outline.md` governs the post's content.
- 12.11 forbids "a count of commits, files, lines or tests".
- The outline publishes exactly that: row 12, F6, and the appendix (15 of 18 trailers), row 5 ("169 passed") and row 7 ("1512 passed").
- Charter :32-35 *requires* the authorship claim to cite the recounted trailers.
- **Why it blocks:** T7 cannot meet both 12.10 and 12.11.
- **Minimal fix:** Amend 12.11 to "SHALL NOT state a count as a measure of effort. A dated trailer recount with its denominator, or a gate's verbatim output, is permitted." That edits requirements.md, not the outline, which belongs to another seat.

---

## Non-blocking findings

**N-1: Requirement 3 needs a boundary against `migrate-agent-plugin` (your consequence 2).** Your mitigation is weaker than stated.
- CAO's installer projects this skill into the store and the skill catalog: `test_installer.py:82-83`, `test_conformance_corpus.py:144`.
- `573/design.md:1172` names the upstream `agent-plugins-example` package as the documented route. A user who follows D4 therefore gets it installed through `cao plugin add`, the same projection P-54 shows for harness-oss.
- "Never competes in a real catalog" holds only for a default install.
- **Fix:**
  - Add 3.8: `Creator_Skill` says "Not for migrating an existing client-specific plugin to v1 (`migrate-agent-plugin`)".
  - `Audit_Skill` scopes itself to auditing an existing v1 package's conformance and limits, not auditing before a migration.
  - Record the mitigation with its qualifier.

**N-2: Updates from your fresh evidence.**
- **Consequence 1:** P-3 → **OBSERVED**, quoting `SKILL.md:3` and `:11`. `requirements.md:50`'s "characterises rather than quotes" is now stale.
- **OQ-2 narrows but stays open.** The body defers to the unread spec prose (`:15`), so whether the spec defines greenfield authoring is still unknown.
- **Consequence 3 — I disagree with the brief.** D4 never claimed CAO ships the skill. `:1172` points at an external package, and the NOTICE (`:4-8`) says nothing in it ships in the wheel. "CAO doesn't ship it" restates D4's premise rather than refuting it. D4's "CAO dogfoods it" refers to the conformance fixture (`test_conformance_corpus.py:130`).
- Requirement 14.5 also restricts the case to "exactly two grounds", so adding a third breaks 14.5. Put it under ground 1 as context: "CAO carries it only as a test fixture; it is not in `SHIPPED_SKILLS` or any `PackageConfig`."

**N-3: Testability gaps.**
- **Listed as "addressed" by T1/T2 but with no mechanical check:** 1.4–1.7, 2.5, 2.6, 3.3, 3.5, 4.1, 4.6, 4.7.
- **Properties of the document, checkable only by reading:** 5.6, 6.2, 6.5, 6.6, 14.3–14.5. Label these "review-checked" so they don't pose as commands.
- **10.8** would make shipped docs (`docs/skills.md`) cite `research.md`. That is wrong for shipped documentation and cannot be tested; scope it to this directory.
- **T6:335** ("verified by reading each occurrence") is a judgement call. A regex works instead: every line matching `plugin` must also match `(Agent|agent|event)[ -]plugin|plugin\.json|\.claude-plugin`, with listed exceptions.
- **`design.md:281`** sets a baseline "our descriptions must beat", but no criterion enforces it, and 3.6 only records the result.

**N-4: Gate 5c's "Catches" column is false.**
- 5c exits 1 whether or not anything is wrong, so it demonstrates the gate-off behaviour; it catches nothing.
- Gate 5 is safe because it sets the variable inline, not because the ladder can tell the two exit-1 cases apart.
- Requirement 4.7 needs a mechanical discriminator. Under `--json`, stdout parses with a `loadable` key (research.md:190). With the gate off there is no JSON, only the "not released yet" refusal (research.md:168).
- Minor: `gate.py:42` lowercases and strips the value, so `TRUE` works. 1.8 and 4.2 could say so.

**N-5: Citations into research.md have drifted.** Most are off by one line; research.md probably changed after the spec cited it. Every claim is still supported by a nearby line.
- P-28 `:191` → `:192`; P-29 `:188-190` → `:189-191`; P-31 `:192` → `:193`; P-32 `:193-195` → `:194-196`; P-33 `:198` → `:199`; P-34 `:199` → `:200`; P-35 `:197` → `:198`; P-38 `:196` → `:197`; P-6 `:300` → `:301`; P-47 `:302` → `:303`; `requirements.md:29` `:300` → `:301`.

Several miss by more:
- **P-17's `:272-273`** points at the terminals table; the red phase is `:280`.
- **P-3's `:154`** points at the M1 bullet; the `migrate-agent-plugin` characterisation is at `:153`.
- **P-20's `:114`** should be `:111`.
- **P-36's `:89`** should be `:87`.
- **P-53's `:145`** should be `:142`.

**N-6: P-30 is mislabelled `OBSERVED (run)`.** The sibling flags were never run, and research.md never mentions `--skip-publish-check`. The flags do exist (`build_agent_plugin.py:963,972,982`). Split the row: `--check` run, exit 0; flags read.

**N-7: P-46 is a false `OBSERVED`.** `2026-08-26-welcome-to-the-cao-blog/index.md:2` has `slug:`, so "exactly four keys in all six" holds for five posts. Requirement 12.2 is still a reasonable choice.

**N-8: Gate citation gaps.**
- Gate 3 (`vendor_agent_plugins_schemas.py --check` exit 0) has no provenance row of its own. P-26 and P-30 are both about something else; the run is research.md:188.
- Gate 7's command drops `-p no:cacheprovider`, so it is not exactly the observed command.
- `design.md:146` cites P-23 for "skipped, not fatal"; that fact is P-4 / research.md:130.

**N-9: The narrowed-D4 path is not actually written (advisor).** 14.2 says Requirements 2–13 "remain in force", but: 3.x, 5.x, 6.x and 7.x name `Creator_Skill` throughout; T4 hardcodes `16` and `True True`; T5's `find` check and 8.8 require both skills. Add a "void the `Creator_Skill` references, counts become 15" clause.

**N-10: P1 is worded as an activation property, but what validates it is vocabulary.** P-36 says no activation test exists. Also, the repo copy of `cao-plugin`'s description contains both "Agent" ("CLI Agent Orchestrator") and "plugin". Under a stemmed-token heuristic, "agent plugin" is not absent vocabulary; only the bigram is. Prefer `plugin.json`, `mcp.json` and `manifest` in 3.2.

**N-11: The spec uses unqualified "plugin" itself.**
- `requirements.md:206`: "CAO's plugin surface". Under the spec's own rule at `:22`, that requirement is "defective".
- `tasks.md:68`: "a kind of plugin".
- `tasks.md:124` and `design.md:308`: "while loading a plugin".
- `design.md:290`: "Plugin surface gate".
- Routing note for the outline's owner: `blog-outline.md:12` and `:54` ("A plugin package").
  - *Supervisor annotation, not part of the review:* routed and **resolved** by `kiro-researcher`.
    `:12` now reads "Agent Plugin packages"; the `:54` occurrence now reads "An Agent Plugin package"
    and sits at `:61` after a 7-line naming-rule note was added at `:5-11`. A third instance was fixed
    at `:137` (`(plugin)`/`(mcp)` → `(plugin.schema.json)`/`(mcp.schema.json)`). The new note names
    every remaining line that fails the regex, each a legitimate exception: the CLI verb `cao plugin`
    and the env var (`:35`, `:68`), file and script names (`:66`, `:125`, `:126`, `:142`, `:146`), the
    filename `plugin.schema.json` (`:137`), and the note itself (`:6-8`, `:11`). `blog-outline.md` is
    now 187 lines, was 179 — the only line-count change in this round, and nothing cites that file by
    line except this finding.

**N-12: Mis-citations in tasks.md.** `tasks.md:270` and `:452` cite Requirement 13.7 for the stale #448 comments. 13.7 is about not editing `research.md` and `blog-outline.md`; the right citations are 10.7 and 13.9.

**N-13: No task adds a lasting test.**
- `design.md` Testing strategy items 1–3 map to no task. T3 runs in a temp directory only.
- `test_packages.py:313,329` cover only `cao` and `cao-contributor`, so a third package is never installed by the suite, and T5 owns no test file.
- Either give T5 those test files, or accept the gap explicitly.

**N-14: Seat inconsistencies.**
- T8's criterion at `:436` runs `git log` and `git status`, but T8's seats run no commands. Give it to the supervisor.
- T3's report has no named home. Name `research.md` (its owner's file) or a new report file.

**N-15: Author entry wording.** Requirement 12.5 says "`title` left blank" while T7 says "no `title` key". Follow the file's practice and omit the key, as the `haofeif` through `yinsong1986` entries do. Also, the outline's "after `yinsong1986`… `:99`" is correct.

---

## What I checked and found clean

- **`<new-pkg>` cannot pass silently.** Left literal in the shell, `<new-pkg>` is an input redirect from a file that doesn't exist, so the command fails loudly.
- **Wave ownership is disjoint.** T3 and T8 are assigned no files and no write work.
- **Scope:** no task or criterion touches `src/cli_agent_orchestrator/plugins/` or `test/plugins/`, and nothing implements, commits or pushes.
- **Two plugin systems:** the Terminology table keeps them distinct.
- **No self-defeat on these points:** the spec never describes #1121 as merged, never repeats the harness-oss claim as fact (P-9 and `design.md:187` correct it), and never says a skill "activates".
- **Option 7.7 (plugin-only) is safe.** `sync_skills.py:104` and `test_skill_packaging_parity.py:57-111` only iterate `SHIPPED_SKILLS`.

---

## Questions for the devops agent

Relayed to the aws-devops-agent via the PR #1121 supervisor. **Not empty — five questions.**

1. Is `gh-pages.yml`'s `pull_request` docs build a required status check on `awslabs` `main`, and does it run for PRs from forks?
2. Does `publish-to-pypi.yml:503-572` (`regenerate-agent-plugin`, `--require-bounded-client` at `:532`, `--check --require-current-pin` at `:572`) handle a third package automatically, given the script iterates `PACKAGES`? And does `--require-bounded-client` apply to a package with no `mcp.json`?
3. A third package would be first built at the held 2.5.3 pin and never released at that version. Does the release-time `--require-current-pin` repin it cleanly, or does it need a release-sequencing note?
4. Does the `agent-plugins-dogfood` CI job (`ci.yml:509-559`) list packages by name, so that a third package would need a job edit to be covered?
5. Under option B: what merge order with #1121 (head `a64bbc76`) avoids a conflicting hunk in the `CONTRIBUTOR` block?

---

## Advisor consultation

**What I asked:** after reading all five files and the charter, and checking a dozen claims against the repo, I sent my draft findings for review before writing.

**Where we agreed:** gate 9 against Requirement 11.1 (F-4); Requirement 6.2 against gate 1's validator (F-3); the missing `cao-learning` / smoke-test / fleet content (F-5); P-46, the off-by-one citations, the gate 3 provenance gap, the under-written narrowed path, P1's activation wording, the unqualified "plugin" uses, T8's commands, T3's report home, and making the 5b/5c discriminator mechanical; and that `<new-pkg>` cannot pass silently.

**Where the advisor pushed back on the brief:** your consequence 3 restates D4's premise (`573/design.md:1172` already points at an external package) rather than strengthening the case against it, and adding it as a third ground would break Requirement 14.5. Your consequence 2 mitigation is weaker than stated because CAO's installer projects the skill (`test_installer.py:82-83`). I adopted both points (N-1, N-2). It also suggested two more reads, both done: `markdown_links.py` past `:36` adds only the `agent-plugin/` skills exclusion, so `docs/issues/` is checked; and `gh-pages.yml` does build the docs on PRs.

**Where we differ:**
- **The auditing overlap.** The advisor rated the `migrate-agent-plugin` overlap non-blocking, framed as a Requirement 3 boundary issue. I agree for Requirement 3 (N-1). I separately rate the D4 *argument text* as blocking (F-1), because the skill's `validation-checklist.md` audits naming and folder-equals-`name`, which goes beyond the description overlap. The advisor's input was not given that file.
- **Two blocking findings of mine that the advisor did not raise:** F-2 (git-state checks) and F-6 (12.10 against 12.11). I kept both; each rests on lines I read directly.

---

## What I verified vs what I read

- **Read in full:** all five spec files and the charter.
- **Checked against the repo with Read and Grep:** the fixture's `SKILL.md`, `NOTICE` and `validation-checklist.md`; every `migrate-agent-plugin` hit (only `573/design.md` and `test/agent_plugins/`, which matches your grep); `sync_skills.py`, `test_skill_packaging_parity.py`, `test_packages.py:300-344`, `markdown_links.py:15-45` and `gate.py:28-43`; the three flags' definitions in `build_agent_plugin.py`, `CODEBASE.md:53`, the headings of `docs/agent-plugins.md` (`:485`, `:669` confirmed), `pyproject.toml:157`/`:352-375`, `authors.yml:25-104`; the front matter of all six posts, `.gitignore`, and the workflow greps.
- **Not run:** I ran no commands. I cannot run git, so the claims that the spec files are untracked and that `git ls-files` prints 14 come from reading `.gitignore` and `git diff`'s documented behaviour, not from running them.
- **Judged from text only:** every exit status in the ladder and in the provenance table. I checked that each `OBSERVED (run)` row has a matching research.md gates row (with the line drift in N-5). I did not re-execute any.
- **Not checked:** `CODEBASE.md:141-160` and `tags.yml` line references.

---

## Assessment

**No, not ready for user review.** The D4 section is honest in tone, and Requirement 14 genuinely makes "not implemented" a planned outcome. Nothing downstream assumes approval, apart from the under-written narrowed path (N-9). But the spec breaks its own shift-left rules in six places:

- The auditing argument can be rebutted with the fixture it cites (F-1).
- Its git-state checks pass on nothing or can never pass (F-2).
- Its first gate depends on a script outside the repository (F-3).
- Its ladder includes a gate that was never run, against its own Requirement 11.1 (F-4).
- Its dogfood and learn steps have no task behind them (F-5).
- Its blog requirements contradict each other and the charter (F-6).

Each is a one-revision fix. Once they are fixed, I expect a clean round 4.

---

## Supervisor note: a retraction, recorded because the spec was nearly built on it

`N-1` and `N-2` refute the supervisor (`oss-sup`), not the author. In Round 2 the supervisor instructed
`oss-docs` to **lead** the D4 argument with "CAO ships `migrate-agent-plugin` to nobody", called it
sharper than the migration-versus-authoring distinction, and directed that Requirement 14.5 carry three
ordered grounds. All three parts of that instruction were wrong:

1. **The argument restates D4's premise instead of refuting it.** D4 never claimed CAO ships the skill —
   `573/design.md:1172` points at the external `agent-plugins-example` package, and D4's "CAO dogfoods it"
   refers to the conformance fixture (`test_conformance_corpus.py:130`).
2. **The supervisor's mitigation was weaker than claimed.** CAO's installer projects the skill into the
   store and the skill catalog (`test_installer.py:82-83`, `test_conformance_corpus.py:144`), so a user
   following D4's documented route obtains it via `cao plugin add`. "Never competes in a real catalog"
   holds only for a default install.
3. **The instructed fix would have violated the spec.** Requirement 14.5 restricts the case to exactly
   two grounds, so adding a third breaks it. The not-shipped point belongs under ground 1 as context.

The surviving ground is the one `oss-docs` built from evidence and labelled honestly — the auditing gap —
narrowed per F-1 to *mechanical* enforcement of the 1024-character limit, the 500-line limit, and the name
regex. `oss-docs` held rather than writing the instructed restructuring, which is why no revision was spent
on it.
