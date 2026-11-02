<!-- Recorded by the supervisor from the reviewer seat's callback (terminal 7a7e31f0, 2026-11-01 ~14:20 -06:00).
     Blocking findings are close to verbatim; non-blocking findings are condensed. The supervisor
     authored none of the findings. Untracked; not part of the PR. -->

# Review 7: agent-plugin-lifecycle spec (#1153), re-review of the review-6 fix pass

> Reviewer: independent read-only seat, no shell. Advisor consulted. HEAD `27311798`.
> Pinned input (supervisor-verified with `shasum -a 256`; author idle; no pending messages to it):
> requirements.md 685 `db2d087e…301956` · design.md 492 `d00dffef…70e3ad` · tasks.md 909 `2d91e8cf…50d5d7`
>
> **Verdict: NOT CLEARED. Two blocking findings, both mechanical.** R6-B-1 closed. N-1 renumbering
> verified at every reference. N-4, N-5, N-7, N-9, N-10, N-14 fixed. No regressions. N-11 excluded.

## Blocking

**R7-B-1: 8.11's new obligation has no owning task, and the scope check rejects the edit it requires.**
`requirements.md:367` requires `test/test_agent_plugin_pin_boundedness.py:484-493` to be extended so
disagreement produces `None`. No match for `pin_boundedness` in `tasks.md` or `design.md`. T5's Owns line
(`tasks.md:520`) and the wave table (`:56`) list only `test_packages.py`; the `t4|t5` `WAVE_PATHS` entry
(`:95`, `:401`, `:731`) covers only that file, so a correct edit reports OUT-OF-SCOPE WRITE.
**Fix:** add the file to T5's Owns line, wave table and description (`:551`); add a T5 criterion that the
disagreement fixture writes all three manifests, and add the file to T5's pytest line (`:599`); add
`|test/test_agent_plugin_pin_boundedness\.py$` to the `t4|t5` pattern in all three end-block copies.

**R7-B-2: hazard-4's blocks, 13.8's block and T1's limits check do not close their heredocs as written in
the source (inferred).** Hazard 4's start (`tasks.md:75-86`) and end (`:90-155`) blocks sit in list item 4,
indented three spaces, so the terminator is `   EOF`; `<<'EOF'` closes only on column-0 `EOF`. Same in
13.8's block (`requirements.md:494-507`) and T1's limits check (`tasks.md:221-232`, `  PY`). Run "as it
sits in the source file" (10.9's rewritten test): start block creates the stamp then exits 127; 13.8 exits
127 on a correct tree; interactive paste hangs at the continuation prompt. End blocks survive because
`exit "$FAIL"` runs first. None of the round's measurements exercised these copies (they ran de-indented
extracts). Review 6 missed this; the reviewer owns the miss.
**Fix:** move every fenced block out of list-item indentation to column 0; re-run the proof on the hazard-4
copies exactly as they sit in the source, under both shells, not on de-indented extracts.

## Non-blocking (condensed)

- **R7-N-1** `tasks.md:384` "fails loudly" is false: a failed `$(…)` doesn't change `cd`'s status and `cd ""` succeeds. Fix: `TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"`.
- **R7-N-2** T5's gate-1 lines (`:602`, `:604`) pass with a validator that checks nothing. Add a four-line negative control to T2's must-pass block (`:313-319`): 2000-char description in a `mktemp -d` skill, `--skills-dir`, require exit 1 naming the skill.
- **R7-N-3** 13.8's block (`requirements.md:497-505`) doesn't assert `%an` = plauzy; accepts a duplicated Agent trailer; `%G?`=`G` assumes signature trust that is unproven (round 1 saw `E`). Fix: assert `%an`, assert the second trailer is the author, and either accept `G|U` or record one signed local commit showing `G`.
- **R7-N-4** T1 `:243` writes STATUS.md "when T1 commits", during wave 1, contradicting `:158`. Record it between waves, after wave 1.
- **R7-N-5** 4.3 (`requirements.md:280`) contradicts itself. Fix: "its positional argument SHALL be a package root; a bare skills directory is accepted only through `--skills-dir`."
- **R7-N-6** `design.md:473-482` lists D-b/D-c/D-d as needing maintainer sign-off while `:454-470` marks them decided. Add: "the user decided these; the maintainer may still decline them at review, which is D-a."
- **R7-N-7** `tasks.md:646` rationale duplicates `:698`; add a blind-spot table row (`:178`) for the quoted-path side effect (a pre-existing oddly named untracked file fails every task until removed).

## Item rulings (condensed)

R6-B-1 closed at every site (`tasks.md:301`, `:602`, `:604`, `:215`, `:570`, `:67`; `requirements.md:280`; `design.md:332`). N-1 map verified. Scope blocks: `--no-renames --diff-filter=D`, `core.quotePath=false` via `g()`, the fail-closed `if`, check 4's warning path all correct; no check passes on any input. STATUS's exit-code table is credible for the T3/T6 copies only; it did not cover hazard-4's indented copies, 13.8's positive path, T3's experiment block, or T5's build and gate-1 lines. N-8 partly fixed (R7-N-1). N-12 fixed in shape (R7-N-3, R7-B-2).

## Assessment

Not cleared. Two mechanical fixes away. Everything else landed; no regression.

---

## Disposition

*Appended by the author seat, 2026-11-01. Nothing above the rule was edited. Line numbers are for the files after this round; the hashes are in `STATUS.md` § "Round 3".*

| Finding | Disposition | Where, after the change |
|---|---|---|
| **R7-B-2** (blocking) | **Reproduced first, then fixed.** The four blocks were copied byte-for-byte from the source, keeping their indentation, and run under zsh and bash in a throwaway clone. **Hazard 4's start block:** it printed `stamp taken: /tmp/cao-apl-t1.stamp`, then exited **127** with `bash: line 9: EOF: command not found` in both shells; the stamp *was* created. **13.8's block:** it exited **1** with "no commits" when there were none, and **1** with "signature is not G" after an unsigned commit. The heredoc never closed there either, but the `exit` paths fired first; with the `upstream/main` ref absent it exited **128**. **T1's limits block:** exit **1**, `IndentationError: unexpected indent`, in both shells, because the two-space indentation reached Python. **Hazard 4's end block:** exit **0**, `scope OK`, because `exit "$FAIL"` runs before the stray `   EOF`, as the review predicted. `bash -n` passed all four, which is why no earlier syntax check saw it. **Fix:** every fenced block inside list-item indentation was moved to column 0. A sweep of all three files found exactly these four, and none is left (`indented-fences=0`, `indented-close=0`). The rest of hazard 4's list item was de-indented with it. T1's criterion and 13.8 were reworded so no list text continues after a block. | `tasks.md:76-85`, `:91-155`, `:224-234`, `:221`; `requirements.md:493`, `:498-514` |
| **R7-B-1** (blocking) | **Fixed, all three parts.** `test/test_agent_plugin_pin_boundedness.py` is in T5's wave-table row, Owns line and description. A new criterion requires the disagreement fixture to write all three manifests. The test is on T5's pytest criterion and command. `\|test/test_agent_plugin_pin_boundedness\.py$` is in the `t4\|t5` pattern of all three end-block copies. **Proved:** that edit is now in scope for t5 (exit 0 under both shells) and still out of scope for t1, t3 and t6 (exit 1). | `tasks.md:56`, `:531`, `:562`, `:602`, `:603`, `:613`; patterns `:95`, `:412`, `:744`; `requirements.md:368` |
| **R7-N-1** | **Fixed everywhere, not only in T3.** All 15 `cd "$(git rev-parse --show-toplevel)"` lines (14 in `tasks.md`, 1 in `requirements.md`) became `TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"`. **Measured:** `cd ""` exits 0 in bash 3.2 and in zsh, and under `set -e`, `cd "$(false)"` does not stop the script. Now, T3's block run from `/tmp` exits **2** with "run this from inside the worktree", and with a relative fixture it exits **2** "fixture path must be absolute", in both shells. | `tasks.md:78`, `:100`, `:252`, `:316`, `:378`, `:394`, `:417`, `:517`, `:541`, `:609`, `:676`, `:689`, `:749`, `:853`; `requirements.md:499` |
| **R7-N-2** | **Fixed.** T2's must-pass block now ends with a negative control: a 2000-character description in a `mktemp -d` skill, run under `--skills-dir`, must exit **1** and name the skill. **It cannot be run meaningfully before T2 exists.** Run now with the validator absent, it exits **1** with "negative control: expected exit 1, got 2" in both shells, so it fails rather than passing vacuously. Its fixture generator was measured to produce a description of exactly 2000 characters. | `tasks.md:321-328` |
| **R7-N-3** | **Fixed, with a measurement.** In a throwaway clone (never this worktree), `git commit -S` with the user's normal configuration (SSH signing, an allowed-signers file) exited 0. `%G?` was **`G`**, `%GS` `4451274+plauzy@users.noreply.github.com`, and `git verify-commit` said "Good "git" signature … ED25519 key SHA256:qxp3vwA0…", exit 0. The accepted set is therefore **`G` only** (`P-71`). The block now asserts `%an` = `plauzy`, asserts `%ae`, requires exactly one Kiro Agent trailer, and requires the other trailer to equal the author. **Positive and negative runs, as the block sits in the source:** the correct signed commit gave **0** in zsh and bash. These each gave **1** in both shells: a duplicated Agent trailer, the wrong author, an unsigned commit, only one trailer, an unsigned last commit, and an unsigned *first* commit, which `git log -1` would have missed. | `requirements.md:493`, `:498-514`, `:204` |
| **R7-N-4** | **Fixed.** The sha is recorded between waves, after wave 1 ends, never during a wave. | `tasks.md:245` |
| **R7-N-5** | **Fixed** with the reviewer's wording. | `requirements.md:281` |
| **R7-N-6** | **Fixed.** D-b, D-c and D-d are marked as decided by the user, and declining any of them is D-a. | `design.md:475` |
| **R7-N-7** | **Fixed.** T6's existence-check rationale and its block comment no longer duplicate the exit contract. A blind-spot row covers a pre-existing untracked file whose name git quotes. | `tasks.md:660`, `:694`, `:187` |
| **N-11** (from review 6) | **Still the user's decision; unchanged.** | — |
