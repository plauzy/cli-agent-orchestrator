<!-- Recorded by the supervisor from the reviewer seat's callback (terminal 7a7e31f0, 2026-11-01 ~14:36 -06:00).
     Condensed; the supervisor authored none of the findings. Untracked; not part of the PR. -->

# Review 8: agent-plugin-lifecycle spec (#1153), re-review of the review-7 fix pass

> Reviewer: independent read-only seat, no shell. Advisor consulted. HEAD `27311798`.
> Pinned input (supervisor-verified with `shasum -a 256`; author idle; no pending messages; mtimes stable since 14:24:52):
> requirements.md 692 `fbf51ba0…3121f6` · design.md 494 `f0f38f9f…d106c9` · tasks.md 922 `7c24334a…1b2823`
>
> **Verdict: CLEARED FOR IMPLEMENTATION.** No blocking findings. R7-B-1 and R7-B-2 closed; R7-N-1…N-7
> landed; no regressions. **Condition: fix R8-N-1 before the first implementation commit.** N-11 excluded.

## Item rulings

- **R7-B-1 closed.** File carried at `tasks.md:56`, `:531`, `:562`, `:602`, `:603`, `:613`, the `t4|t5` pattern at `:95`, `:412`, `:744`, and `requirements.md:368`. The criterion fails on an agreeing-manifests fixture. The whole boundedness test file stays offline (autouse `urlopen` refusal `:71-88`; only live test marked `e2e` `:364`; deselected by `pyproject.toml:519`).
- **R7-B-2 closed.** Reviewer's own greps: no indented fence, `EOF` or `PY`; no `cd "$(`; 15 `TOP=` sites. List structure and rendered numbering hold (inferred from CommonMark). The author's reproduction (exit 127; `IndentationError`) is credible.
- **13.8** (`requirements.md:498-514`) fails on every case it tests; passes one wrong case (R8-N-1); can fail a correct set only if the author trailer form differs from the block's assumption (R8-N-2).
- **No regressions:** T6 block, scope blocks, T5 build block, and everything reviews 6 and 7 cleared.
- **Readiness:** waves 1–5 including T8 can be implemented as written, starting with T1 (the creator skill).

## Non-blocking

- **R8-N-1 (fix before the first commit).** 13.8 counts only `Co-authored-by` values (`requirements.md:508-511`), so a commit with the two correct trailers plus a trailer under another key (for example a session link that tooling may append) passes, against the attribution directive (`review-1.md:39-42`) and 12.12 (`requirements.md:471`). Fix: require all trailer lines to number exactly two (`git log -1 --format='%(trailers:unfold,only)' "$c" | sed '/^$/d' | wc -l` = 2), reject any key other than `Co-authored-by`, leave body attribution review-checked. (Trailer-parser treatment of a bare URL line is inferred.)
- **R8-N-2.** Hazard 3 (`tasks.md:69`) does not give the exact trailer lines that 13.8 requires (`plauzy <4451274+plauzy@users.noreply.github.com>`), and no task says when 13.8 runs (`13.8` appears only at `:69`, `:922`; T8 tree-state `:898` doesn't name it). Fix: exact two `Co-authored-by:` lines in hazard 3; "run 13.8's block after every task commit"; name 13.8 as the supervisor's pre-push gate in T8.
- **R8-N-3.** T1's limits block (`tasks.md:224-234`) uses a relative path and no `TOP=` line. Fix: state "from the repository root" at `:221`, or wrap it like the others.
- **R8-N-4 (optional).** Build the boundedness fixture's manifest names from `bap.PACKAGES` rather than hard-coding three (`tasks.md:562`, `:602`).

## Advisor consultation

Agreed on all closures and readiness. Added and adopted: the offline check of the boundedness file, R8-N-2's "when does 13.8 run", R8-N-3. On R8-N-1 it recommended non-blocking; adopted with "fix before the first commit". Case for blocking recorded: the most likely trigger is tooling known to add that very line.

## Assessment

Cleared. Remaining work concerns commits only: make 13.8 reject other trailer keys, state the exact trailer lines, and say when 13.8 runs, before T1's first commit.

---

## Disposition

*Appended by the author seat, 2026-11-01. Nothing above the rule was edited. Line numbers are for the files after this round; the hashes are in `STATUS.md` § "Round 4".*

| Finding | Disposition | Where, after the change |
|---|---|---|
| **R8-N-1** (fix before the first commit) | **Fixed; the existing checks are kept.** 13.8's block now reads every trailer with `%(trailers:unfold,only)`, requires exactly two lines in total, and rejects any line whose key is not `Co-authored-by`. The criterion text records this and leaves body attribution `[review-checked]`. **Proved, block run as it sits in the source, under zsh and bash.** (a) A signed commit with exactly the two hazard-3 lines gave **0**. (b) (a) plus `Session: https://example.invalid/x` gave **1**, "not exactly two trailer lines in total"; git does parse that line as a trailer, as `%(trailers:unfold,only)` showed. (c) (a) plus a third `Co-authored-by` gave **1**, "not exactly two Co-authored-by values". A lowercase `co-authored-by:` key, which the `key=` filter matches case-insensitively, gave **1**, "a trailer key other than Co-authored-by". Every Round 3 case gave the same result as before. | `requirements.md:493`, `:513-515` |
| **R8-N-2** | **Fixed.** Hazard 3 gives the two exact lines, `Co-authored-by: plauzy <4451274+plauzy@users.noreply.github.com>` and `Co-authored-by: Kiro Agent <244629292+kiro-agent@users.noreply.github.com>`, and says to run 13.8's block after every task commit. **Where the Kiro Agent value comes from:** it equals 13.8's `AGENT` value, and `git log upstream/main --format='%(trailers:key=Co-authored-by,valueonly)' \| sort \| uniq -c` shows `16 Kiro Agent <244629292+kiro-agent@users.noreply.github.com>`. `git log upstream/main --format='%(trailers:unfold,only)' \| grep -i kiro \| sort \| uniq -c` shows a single form, `16 Co-authored-by: Kiro Agent <244629292+kiro-agent@users.noreply.github.com>`. T8's tree-state criterion names 13.8's block as the supervisor's pre-push gate. | `tasks.md:69`, `:901` |
| **R8-N-3** | **Fixed by wrapping.** T1's limits block is `bash -euo pipefail <<'EOF'` with a `TOP=` line. **Proved:** run from `/tmp` it exits **2** ("not a git repository"); from the root or from `scripts/` with a conformant fixture it exits **0**; with an over-limit fixture it exits **1**. Same under zsh and bash. | `tasks.md:221`, `:224-237` (`TOP=` at `:225`) |
| **R8-N-4** | **Fixed.** The fixture writes one manifest per `bap.PACKAGES` entry, with names taken from the configs. | `tasks.md:565`, `:605` |
