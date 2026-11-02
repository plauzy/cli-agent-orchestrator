<!-- Recorded by the supervisor from the reviewer seat's callback (terminal 7a7e31f0, 2026-11-01 ~14:00 -06:00).
     The body below the rule is the reviewer's text as delivered. The supervisor wrote this file only
     as a record; it authored none of the findings. Untracked; not part of the PR. -->

---

# Review 6: agent-plugin-lifecycle spec (#1153), frozen-input review

> **Issue of record:** #1153 · **Parent:** #1154 · **Sibling:** #1152
>
> **Reviewer:** an independent read-only reviewer seat. It has no write tools and no shell. **Advisor:** consulted (see the end). **Reviewed:** 2026-11-01.
> **Pinned input, as supplied. I did NOT verify the hashes.** I could not run `shasum -a 256`, either at the start or before reporting, because this seat has no command execution.
> - `requirements.md`: 668 lines, `50259d7ee4830972b4c537d4f6e7c8f17d97c6bce360d813ea537ec925459166`
> - `design.md`: 493 lines, `642c9035f413f16417e60fb0a57e5880c56d2706eddf2214e0f5a5a55417ea1d`
> - `tasks.md`: 822 lines, `5d2aa04967075d5ef4eddf66f8c91af3a378fb99e439687811a537d7a40b6cf4`
>
> (Supervisor note: the supervisor verified these three hashes with `shasum -a 256` at dispatch, 2026-11-01, after the author's freeze and with no pending inbox messages to the author.)
>
> **Verdict: NOT CLEARED.** One blocking finding, R6-B-1. R5-1 is fixed. B-1 through B-6 all landed in full. Every release-path claim checks out against the repository. Fourteen non-blocking findings follow.

## Blocking

**R6-B-1: Gate 1, and the "bundled validator SHALL report it as passing" clauses of 1.10 and 2.9, are carried by no task.**
`design.md:284`/`:332` define gate 1 as `uv run --script skills/cao-agent-plugin-audit/scripts/validate_agent_plugin.py --skills-dir skills/`; 1.10 (`requirements.md:222`), 2.9 (`:242`), 4.3 (`:280`), 11.9 (`:443`) rest on it. `tasks.md` never mentions `--skills-dir`. T2's validator criteria (`:280`) test package-root mode only; T2's command (`:290-297`) does not run the validator; T1 lists 1.10 (`:197`) but cannot run it; T6 treats non-zero audit exit as not a failure (`:582`); hazard 2 (`:67`) has no command or expected exit. Consequence: T1–T7 can all finish green while gate 1 cannot run and both skills fail their own validator. Nothing says how skills-dir mode treats `skills/plugin.json` or `skills/vendor/`.
**Fix:** (1) T2 criterion: implement `--skills-dir <dir>`; each immediate child containing `SKILL.md` is a skill; `plugin.json` and non-skill children such as `vendor/` are ignored, stated explicitly; a temp-dir over-limit fixture must make it exit non-zero naming the skill. (2) T5's (or T4's) "Command that must pass": add gate 1 verbatim from `design.md:284`, exit 0, plus package mode against `./agent-plugin/cao-agent-plugin-lifecycle`, exit 0. (3) T1: "Requirements addressed" -> 1.10's first clause only; T5 carries the validator clause.

## Non-blocking (summary of the reviewer's text; full reasoning delivered in the callback)

- **N-1** Rendered list numbering differs from written numbering: Req 2 writes 12 before 11 (`requirements.md:244-245`), Req 4 has two "4." (`:281-282`), Req 10 writes 9 before 8 (`:416`, `:423`). Renumber sequentially and update every `N.M` reference across all three files.
- **N-2** 10.9 names the wrong test (`requirements.md:420`, `design.md:278`, `tasks.md:153`): the renderer un-escapes `\|`, so test "as it sits in the source file, under the shell a reader will paste it into".
- **N-3** 2.12 criteria gaps (`tasks.md:282-284`, `:266`): fixture generated in `mktemp -d`, never committed under `skills/`; `:283` fixture otherwise conformant, assert exit 0; `:284` label `[review-checked]`; add 2.12 to `:266`; T2 command grep (`:295`) misses `/Users/` and `validate-plugin.py` named at `:277-278`.
- **N-4** Staged deletion/rename passes the scope check (`tasks.md:112-121`, `:161`, `:163`, T3/T6 copies): add `git diff --cached --name-only --diff-filter=DR` to DELETED; run git with `-c core.quotePath=false`; relabel table rows "closed for unstaged changes" until done.
- **N-5** Check 4 can fail a clean tree (`tasks.md:125-129`, `:406-410`, `:690-694`): in check 4 only, `find "$f" -newer "$STAMP" -print 2>/dev/null || true`.
- **N-6** Correct runs reported as failures: supervisor/implementer edits to spec-dir files during a wave; file untracked at stamp then committed before end block. State: no spec-dir edits during a wave, end block runs before any commit (or exclude named supervisor-owned files).
- **N-7** T6 command passes when the audit never ran (`tasks.md:621-649`): T2 defines exit contract 0 clean / 1 findings / else error; T6 adds `test "$AUDIT_EXIT" -le 1` and uses `uv run --quiet --script`. (Drafted blocking, downgraded.)
- **N-8** T3 experiment block (`tasks.md:357-366`): absolute fixture path, run from the worktree (`git -C … rev-parse --show-toplevel` or `uv run --project`); record `CAO_HOME` contents rather than assert empty until observed.
- **N-9** Two more test sites: `test/test_agent_plugins_docs.py:139-164` (red from T5 until T7; neither task names it; T5 command runs only `test/agent_plugins/`) and `test/test_agent_plugin_pin_boundedness.py:484-493` (vacuous pass with a third config). Add the boundedness site to 8.11 and P-69; docs test to hazard 1 as expected red for T5 and to T7's must-pass command.
- **N-10** Decided-versus-open staleness in `design.md` (ships in PR): `:5`, `:6`, `:11`, `:20`, `:36`, `:161`, `:195`, `:225`, `:409`, `:413`, `:418`, `:422`, `:431`, `:450-472`, `:483`, `:493`; in `requirements.md`: `:10`, `:107`. One sweep.
- **N-11** A third-party UI-framework product name at `design.md:418-419`, `requirements.md:580`, `:582`, `tasks.md:192` contradicts the "only three carve-outs" claim in STATUS. **User's call:** ratify as a fourth carve-out or rewrite generically.
- **N-12** 13.8's test checks only `git log -1` (`requirements.md:492`): check every commit in `upstream/main..HEAD` for exactly two `Co-authored-by` values and `%G?` = `G`.
- **N-13** Task numbering: tasks.md's T8 is now the two independent reviews (`:59`, `:763`) and no T9 exists, so "without T8" would drop the required reviews. STATUS should say "waves 1–5 including T8 (the independent reviews); the blog task is deferred".
- **N-14** Record the creator skill's commit sha as 15.5's reference point; give T5's in-process build a fenced runnable block asserting `2.5.3` before writing (`tasks.md:487`); Requirement 2's traceability (`:247`) omits B-6 and 2.12.

## Item rulings

- 02:34 delta: 10.9 rule right (N-1, N-2); runnable-forms block cleared as a transcription; T2 2.12 criteria landed (N-3).
- B-1…B-6: all landed in full; B-6 verified this round (wording residual at `requirements.md:539`, "promise" -> "describe skills it does not ship").
- R5-1: cleared. All 13 blocks interpreter-independent; stamps created by the relying step; `tee`/`AUDIT_EXIT` correct when tee exits 0. Caveat: add to T2 that its script never reads stdin (`bash -s`).
- Release path: P-67, 8.12, the ten `test_packages.py` sites, 8.13's wording, P-68, P-70, T5 defects 9-10 all hold (plus N-9, N-14).
- Four stale claims: all **fix now, non-blocking**; `tasks.md:822` is the most important ("Any push").

## Advisor consultation

Agreed: R5-1 fixed, tee analysis, B-1…B-6, release path, four stale claims. Added and adopted: N-5, N-6, N-3's grep gap, N-10 list, T5 runnable build, `bash -n` critique. Pushed back: R6-B-1 the only blocker; N-7 downgraded (T6 `:577` and the review task would catch a crash); N-4 kept non-blocking.

## Assessment

Not cleared. One fix away: one T2 criterion plus two lines in T5's command. Before the PR fix N-1, N-9, N-10 and `tasks.md:822`.

---

## Disposition

*Appended by the author seat, 2026-11-01. Nothing above the rule was edited. Line numbers below are for the files after this round's changes; the new hashes are in `STATUS.md` § "Checkpoint 2026-11-01".*

| Finding | Disposition | Where, after the change |
|---|---|---|
| **R6-B-1** (blocking) | **Fixed, all three parts.** (1) T2 has a `--skills-dir <dir>` criterion: each immediate child containing `SKILL.md` is a skill; a top-level `plugin.json` and non-skill children such as `vendor/` are ignored, stated explicitly; a `mktemp -d` fixture exits 0 when conformant and non-zero, naming the skill, once a 2000-character description is added. Requirement 4.3 now specifies the same mode. (2) T5's "Command that must pass" runs gate 1 verbatim from `design.md:284`, plus package mode against `./agent-plugin/cao-agent-plugin-lifecycle`, inside its `bash -euo pipefail` block, both required to exit 0. (3) T1's Requirements line is narrowed to 1.10's first clause and names T5 as carrying the validator clause. Hazard 2 now names the command and the expected exit. | `tasks.md:301`; `requirements.md:280`; `tasks.md:600`, `:603`, `:570`; `tasks.md:215`; `tasks.md:67`; `design.md:332` |
| **N-1** | **Fixed.** Req 2 and Req 10 were reordered with their numbers unchanged (identity map). Req 4's duplicate "4." was renumbered, and every reference was updated by meaning. One reference was already wrong before the renumber: `tasks.md` T2 defect 5 cited 4.3 for the PEP 723 rule, which is 4.4. | `requirements.md:244-245`, `:281-286`, `:288`, `:416-417`; references at `design.md:19`, `:169`, `:171`, `:239`, `:340`, `:392`, `:405`, `:446`; `tasks.md:277`, `:278`, `:280`, `:281`, `:285`, `:308`, `:358` |
| **N-2** | **Fixed.** The 10.9 test is now "as it sits in the source file, under the shell a reader will paste it into", because the renderer un-escapes `\|`. | `requirements.md:421`; `design.md:278`; `tasks.md:169` |
| **N-3** | **Fixed.** The fixture is generated in `mktemp -d` and never committed; the advisory-only fixture is otherwise conformant and must exit 0; the no-verdict check is labelled `[review-checked]`; 2.12 was added to T2's Requirements line; T2's command grep now also matches `validate-plugin.py` and `/Users/`. | `tasks.md:304`, `:305`, `:306`, `:285`, `:317` |
| **N-4** | **Fixed and proved.** Every git call goes through `git -c core.quotePath=false`. DELETED adds `git diff --cached --no-renames --name-only --diff-filter=D`, which catches `git rm` and the old path of `git mv`. A name git still quotes is reported, so the check fails closed. The table rows were rewritten to match. | `tasks.md:91` onward (end block), `:177-178`; T3 copy `:397`; T6 copy `:727` |
| **N-5** | **Fixed and proved.** In check 4 only, `find … 2>/dev/null` is followed by a warning and never changes the exit status. | end block check 4; `tasks.md:186` |
| **N-6** | **Fixed.** The rules are stated: no edits to the spec directory during a wave, including `STATUS.md`, and the end block runs before the task commits. A table row covers the false-failure case. | `tasks.md:158`, `:69`, `:187` |
| **N-7** | **Fixed.** T2 defines the exit contract (0 clean, 1 findings, else error). T6 uses `uv run --quiet --script` and `test "$AUDIT_EXIT" -le 1`, and the criterion text matches. | `tasks.md:302`, `:690`, `:698`, `:649` |
| **N-8** | **Fixed.** The fixture path must be absolute, the block runs from inside the worktree (`cd "$(git rev-parse --show-toplevel)"`, which fails loudly outside it), and `CAO_HOME` contents are recorded rather than asserted. | `tasks.md:378`, `:359`, `:338` |
| **N-9** | **Fixed.** The boundedness site was added to 8.11 and P-69. The docs test is in hazard 1 as an expected red from T5 until T7, and in T7's command. | `requirements.md:367`, `:202`; `tasks.md:65`, `:844` |
| **N-10** | **Fixed in one sweep.** | `design.md:5`, `:6`, `:11`, `:20`, `:36`, `:161`, `:169`, `:195`, `:225`, `:406`, `:409`, `:431`, `:450-469` (table rewritten as decided/deferred/open), `:482`, `:492`; `requirements.md:10`, `:107` |
| **N-11** | **NOT CHANGED — the user's decision.** The product-name text is untouched in all three files. Listed in `STATUS.md` as an open user question: ratify a fourth carve-out, or rewrite generically. | — |
| **N-12** | **Fixed.** 13.8 checks every commit in `upstream/main..HEAD`, fails on an empty range, and has a runnable block, which exits 1 "no commits in upstream/main..HEAD" under zsh and bash today. | `requirements.md:492-509` |
| **N-13** | **Fixed in `STATUS.md`** with the mapping sentence. | `STATUS.md` |
| **N-14** | **Fixed.** 15.5's reference point is the commit sha that adds the creator skill, and T1 records it. T5's in-process build has a fenced runnable block that asserts `2.5.3` before writing. Requirement 2's traceability names B-6 and 2.12. | `requirements.md:578`; `tasks.md:243`, `:526`; `requirements.md:247` |
| Four stale claims | **Fixed.** "Any push" row; the staged-state row; the `GENERATIVE_UI` fact, the "zero occurrences" claim and the `research.md:213` carve-out (which quotes no such claim; the real one is `:241`); T4 defect 2. | `tasks.md:909`; `design.md:353`; `design.md:413`, `:418`, `:422`; `tasks.md:481` |
| B-6 residual | **Fixed.** "promise what it does not ship" became "describe skills it does not ship". | `requirements.md:556` |
| `bash -s` stdin caveat | **Fixed.** A T2 criterion says the script never reads stdin, verified by reading the script. | `tasks.md:303` |
| **Found while fixing, not raised by review 6** | The first draft of the N-4 fix put `case "$f" in \"*) … ;; esac` inside `$( … )`, and `/bin/bash` 3.2.57 cannot parse a `case` pattern's `)` there ("syntax error near unexpected token `;;'"). The proof run caught it on every case, exit 2; `zsh -n` accepts the same text. It was replaced by an `if` with a comment saying why. The integrity check now runs `bash -n` on each heredoc **body**, not only the outer block, because the outer check cannot see inside a quoted heredoc. | `tasks.md:119`, `:425`, `:755` |
