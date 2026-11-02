# Tasks: ship the agent-plugin creator and audit skills, a dogfood package, and the post

**Issue:** [#1153](https://github.com/awslabs/cli-agent-orchestrator/issues/1153) · **Parent:** [#1154](https://github.com/awslabs/cli-agent-orchestrator/issues/1154) · **Sibling:** [#1152](https://github.com/awslabs/cli-agent-orchestrator/issues/1152)
**Requirements:** [requirements.md](requirements.md) · **Design:** [design.md](design.md) · **Evidence:** [research.md](research.md) · **Review:** [review-1.md](review-1.md)
**Status:** Specified, **not** implemented.

---

## Wave 0 — the decisions, and the one thing still open

**The user has decided to proceed without waiting for maintainer answers** (2026-10-30). `requirements.md`'s [`## Decisions, and what remains open`](requirements.md) is the authority; this section records only what an implementer must know before wave 1.

### What is decided

| Decision | Consequence for the tasks |
|---|---|
| **OQ-1a** — proceed as if **D4 is reversed** (the user's half; **OQ-1b**, the maintainer's, stays open and gates the merge) | Run every wave. **Requirement 14 stays**: a maintainer can still decline at review, so the pull-request body leads with the fact that this revisits #573's D4. Proceeding is a decision to *propose*, not a finding that anyone agreed. |
| **OQ-16** — **the implementation commits, and never pushes** | Signed (`-S`), author `plauzy`, **exactly two trailers** (`plauzy`, `Kiro Agent`). Stop at "ready to push". See hazard 3. |
| **OQ-4** — the `Audit_Skill`'s **bundled validator**, pinned to the `PIN.json` hashes, plus `cao plugin validate --json` when the gate is set | T2 builds it. It **is** gate 1; the bootstrap framing is retired. |
| **OQ-7 / OQ-12** — a **third `PackageConfig`** named **`cao-agent-plugin-lifecycle`** | T5 creates `agent-plugin/cao-agent-plugin-lifecycle/`; **T7's `CODEBASE.md` row must name it exactly.** |
| **OQ-6** — **both skills join `SHIPPED_SKILLS`** | T4 runs, and the full obligation ladder applies. |
| **OQ-3** `cao-plugin` · **OQ-5** object evals · **OQ-13** `references/` for the audit skill | T1, T2. |
| **OQ-8**–**OQ-10**, **OQ-14** — **deferred** | **There is no blog task.** Requirement 12 is deferred-with-reason, not deleted; `blog-outline.md` stays untracked on disk. |

### OQ-17: dropped

**OQ-17 is dropped, by the user, 2026-11-02** (`/Volumes/workplace/open-source/.agents/plans/agent-plugin-lifecycle/decisions-oq17-n11.md`, "Update 2026-11-02"; Requirement 15). The creator skill is not dogfooded on an external package, no external work is planned, and #1200 must not promise it. The audit skill is still exercised on CAO's own packages (T6). The charter deviation stands. **No task is written for external work, because there is none.** The earlier sizing (five tasks plus two approval gates, the M2+M4 floor) and the 2026-11-01 deferral are superseded; they remain in `STATUS.md`'s history.

### Rebase facts an implementer will otherwise get wrong

- The worktree and `upstream/main` are both at **`2731179845f9bd332a22e72fa44cc55345561c99`**, fast-forwarded on 2026-11-01 from `00611d11`. The two new commits, #1170 and #1176, change Kiro provider and identity files, their tests and fixtures, `docs/kiro-cli.md`, `CHANGELOG.md` and two `uv.lock` files. **No path these documents cite changed** (`P-66`), so no citation moved.
- **#1121 is merged — it *is* `00611d11`.** Its follow-ups are **#1168**. Every "open #1121" and `a64bbc76` reference is gone from this specification; if you find one, it is stale.
- **#1121 also fixed the stale #448 comments** in `scripts/build_agent_plugin.py`, so that out-of-scope item is moot (`P-52`).
- **#1121 moved line numbers in `scripts/build_agent_plugin.py`.** Every citation in these documents was re-verified against `00611d11` rather than assumed: `PACKAGES` is now `:188`, `source_skill_dir` `:666-674`, `check_package` `:731`, the sibling flags `:988`, `:997`, `:1007`. They are unchanged at `27311798`, because neither later commit touches `scripts/`. Re-verify again after any rebase; two earlier rounds lost time to exactly this.

## Parallelisation plan

**Eight** tasks in five waves. No two tasks in the same wave own a file. **There is no blog task:** the `Blog_Post` is out of this pull request (**OQ-8**–**OQ-10**, **OQ-14** deferred), Requirement 12 is retained as deferred-with-reason, and `blog-outline.md` stays on disk, untracked.

| Wave | Task | Owner seat | Owns (exclusively) | Depends on |
|---|---|---|---|---|
| 1 | **T1** — creator skill | `oss-dev` | `skills/cao-agent-plugin-creator/**` | Wave 0 |
| 1 | **T2** — audit skill + validator | `oss-dev` | `skills/cao-agent-plugin-audit/**` | Wave 0, OQ-4 |
| 1 | **T3** — over-limit experiment | `kiro-researcher` | `docs/issues/1153-agent-plugin-lifecycle/t3-overlimit-experiment.md` (the **report**; the experiment itself runs in a temp dir) | Wave 0 |
| 2 | **T4** — wheel shipping | `oss-dev` | `scripts/sync_skills.py`, `src/cli_agent_orchestrator/skills/**` | T1, T2, OQ-6 |
| 2 | **T5** — dogfood package | `oss-dev` | `scripts/build_agent_plugin.py`, `agent-plugin/cao-agent-plugin-lifecycle/**`, `test/agent_plugins/test_packages.py`, `test/test_agent_plugin_pin_boundedness.py` | T1, T2, OQ-7, OQ-12 |
| 3 | **T6** — audit the package, then record the outcome and lesson | `oss-docs` | `docs/issues/1153-agent-plugin-lifecycle/audit-report.md`, `…/audit-raw.txt` | T2, T5 |
| 4 | **T7** — documentation obligations | `oss-docs` | `CODEBASE.md`, `docs/skills.md`, `docs/agent-plugins.md` | T5 |
| 5 | **T8** — independent review | **two independent read-only reviewer seats** (see below) | **nothing** — read-only seats | T1–T7 |

**Seat capabilities, so no implementer re-derives them.** T8 is **two independent read-only reviewer seats**, each resolving as an installed profile with role `reviewer`, and neither able to write files or run commands. **Axis 1** — correctness, security, evidence honesty and test honesty; `oss-review` covers it. **Axis 2** — logic and spec conformance. The two must be **separate seats** so the second does not inherit the first's context; which profile fills axis 2 is the supervisor's routing decision and is deliberately not recorded here. **No seat in this plan is described by its provider**, per the binding attribution directive. T8 therefore owns nothing, runs nothing, and returns findings inline. `kiro-researcher` produces evidence; T3's experiment runs in a temporary directory and only its **report** lands in the repository.

### Cross-task hazards

1. **A sibling's red gate is not your defect, in wave 2.** T4 and T5 both run the ladder. A new skill present in `skills/` but not yet in any `PackageConfig` is a valid intermediate state — the drift guard compares a package against its own allowlist, not against `skills/`. But a skill named in a `PackageConfig` before it exists in `skills/` raises a build error (`build_agent_plugin.py:666-674`), which is why T1 and T2 are dependencies rather than peers. **One more expected red, from T5 until T7:** `test/test_agent_plugins_docs.py:139-164` reads `PACKAGES` and requires every packaged skill to be named in `docs/agent-plugins.md`, so it fails as soon as T5 adds the third config and passes again only when T7 documents both skills. T5's command does not run it, deliberately; T7's command does (Requirement 8.11; review 6 **N-9**).

2. **Gate 1 fails on a half-written sibling.** During wave 1, T1 and T2 each create a directory the other's gate run would scan. **Each wave-1 task measures only its own directory** and scans all of `skills/` only as its final check. **Gate 1 itself is run, with a required exit of 0, by T5's "Command that must pass"**, in `--skills-dir` mode over `skills/` and in package mode over the new package, once both skills and the validator exist (review 6 **R6-B-1**). Measured directly at `27311798`, every skill already in `skills/` passes the five limits, so the gate can pass.

3. **The implementation commits; it never pushes.** **OQ-16 is decided.** Commits are **signed** (`-S`), authored by `plauzy`, and carry **exactly two trailers** — no others, per the binding attribution directive — written as exactly these two lines: `Co-authored-by: plauzy <4451274+plauzy@users.noreply.github.com>` and `Co-authored-by: Kiro Agent <244629292+kiro-agent@users.noreply.github.com>`. The second matches the value Requirement 13.8's block accepts and the form on every Kiro co-authored commit on `upstream/main` (review 8 **R8-N-2**). **Run Requirement 13.8's block after every task commit**; a non-zero exit stops the wave until the commit is amended. **No task pushes, and no task may add a step that pushes.** Work stops at "ready to push"; the push and the draft pull request are the supervisor's after the user's approval. Requirement 13.8 carries this. **One consequence for the scope checks:** they are unaffected, because each runs **during** its task and any commit follows it — so at the moment a check runs, its files are still uncommitted. **The end block must run before the task commits:** a file that was untracked at the stamp and is committed before the end block runs disappears from both the untracked and the staged lists, and check 3 then reports it as deleted. The reasoning that forced the timestamp recipe therefore survives the decision that removed its original justification. `git add -A` remains forbidden: stage deliberately, or a stray file from another wave lands in your commit. Separately, `scripts/security-scan.sh` rewrites the tracked `uv.lock` unless `--frozen` is passed; no task needs that script.

4. **Scope checks enumerate candidates through git, then filter by timestamp, and they run under an explicit `bash`.** Two blocks, identical for every task except the task id passed to `bash -s`. Run the **start block** before you touch anything, and the **end block** when the work is done. Run both from anywhere inside the worktree; each changes to the top level itself. The end block refuses to run if the start block did not.

**Start block** — creates the stamp and the untracked-file snapshot the end block depends on:

```bash
bash -euo pipefail -s t1 <<'EOF'
case "$1" in t[1-7]) ;; *) echo "unknown task: $1" >&2; exit 2 ;; esac
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
g() { git -c core.quotePath=false "$@"; }   # print non-ASCII paths raw, not C-quoted
STAMP="/tmp/cao-apl-$1.stamp"
touch "$STAMP"
{ g ls-files -o --exclude-standard; g diff --cached --name-only; } \
  | LC_ALL=C sort -u > "$STAMP.untracked"
echo "stamp taken: $STAMP"
EOF
```

**End block** — exits 0 only when nothing outside the task's wave was written or deleted:

```bash
bash -euo pipefail -s t1 <<'EOF'
TASK="$1"
case "$TASK" in
  t1|t2|t3) WAVE_PATHS='^(skills/cao-agent-plugin-creator/|skills/cao-agent-plugin-audit/|docs/issues/1153-agent-plugin-lifecycle/t3-overlimit-experiment\.md$)' ;;
  t4|t5)    WAVE_PATHS='^(scripts/sync_skills\.py$|src/cli_agent_orchestrator/skills/|scripts/build_agent_plugin\.py$|test/agent_plugins/test_packages\.py$|test/test_agent_plugin_pin_boundedness\.py$|agent-plugin/cao-agent-plugin-lifecycle/)' ;;
  t6)       WAVE_PATHS='^docs/issues/1153-agent-plugin-lifecycle/audit-(report\.md|raw\.txt)$' ;;
  t7)       WAVE_PATHS='^(CODEBASE\.md$|docs/skills\.md$|docs/agent-plugins\.md$)' ;;
  *) echo "unknown task: $TASK" >&2; exit 2 ;;
esac
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
g() { git -c core.quotePath=false "$@"; }   # print non-ASCII paths raw, not C-quoted
STAMP="/tmp/cao-apl-$TASK.stamp"
# A missing stamp must fail LOUDLY. It must never let the check pass.
test -f "$STAMP" || { echo "MISSING STAMP $STAMP: run the start block first" >&2; exit 2; }
test -f "$STAMP.untracked" || { echo "MISSING SNAPSHOT $STAMP.untracked: run the start block first" >&2; exit 2; }
# grep -v exits 1 when it selects nothing, which here means success; 2 is a real error.
keep_out() { grep -vE "$WAVE_PATHS" || [ $? -eq 1 ]; }
present() { { g ls-files -o --exclude-standard; g diff --cached --name-only; } | LC_ALL=C sort -u; }

# 1. Writes since the stamp: modified, staged, and untracked-but-not-ignored paths.
#    find -prune -newer checks the path itself (a symlink is not followed) and
#    errors on a missing stamp; the `|| exit 2` carries that error out of the loop.
#    A path git still prints quoted (it contains `"`, `\` or a control character)
#    cannot be tested, so it is reported rather than skipped: fail closed.
WRITES=$(
  { g ls-files -m; g diff --cached --name-only; g ls-files -o --exclude-standard; } \
    | LC_ALL=C sort -u \
    | while IFS= read -r f; do
        if [ "${f#\"}" != "$f" ]; then printf '%s\n' "$f"; continue; fi   # no `case` here: bash 3.2 cannot parse `pat)` inside $( )
        [ -e "$f" ] || [ -L "$f" ] || continue     # gone: covered by checks 2 and 3
        find "$f" -prune -newer "$STAMP" -print || exit 2
      done \
    | keep_out
)
# 2. Deleted tracked files: unstaged (ls-files -d) and staged, which covers `git rm`
#    and the old path of a `git mv` (--no-renames reports a rename as D plus A).
DELETED=$(
  { g ls-files -d; g diff --cached --no-renames --name-only --diff-filter=D; } \
    | LC_ALL=C sort -u | keep_out
)
# 3. Deleted untracked files: present at the stamp, absent now.
GONE=$(present | LC_ALL=C comm -23 "$STAMP.untracked" - | keep_out)
# 4. Gitignored paths written since the stamp: a WARNING, never a failure. A find
#    error here (an unreadable directory, say) is reported and does not change
#    the exit status.
IGNORED=$(
  g ls-files -o -i --exclude-standard --directory \
    | while IFS= read -r f; do
        find "$f" -newer "$STAMP" -print 2>/dev/null \
          || echo "WARNING (not a failure): check 4 could not read all of $f" >&2
      done \
    | keep_out
)
if [ -n "$IGNORED" ]; then
  echo "WARNING (not a failure): gitignored paths written since the stamp:" >&2
  printf '%s\n' "$IGNORED" | sed -n '1,20p' >&2
fi

FAIL=0
if [ -n "$WRITES" ];  then printf '%s\n' "$WRITES"  | sed 's/^/OUT-OF-SCOPE WRITE: /';     FAIL=1; fi
if [ -n "$DELETED" ]; then printf '%s\n' "$DELETED" | sed 's/^/OUT-OF-SCOPE DELETION: /';  FAIL=1; fi
if [ -n "$GONE" ];    then printf '%s\n' "$GONE"    | sed 's/^/UNTRACKED FILE DELETED: /'; FAIL=1; fi
if [ "$FAIL" -eq 0 ]; then echo "scope OK: $TASK"; fi
exit "$FAIL"
EOF
```

**Two rules make a correct run pass (review 6 N-6).** (1) **Nobody edits any file in `docs/issues/1153-agent-plugin-lifecycle/` during a wave** except the files a task owns. That includes the supervisor's `STATUS.md`: the check is per-tree, not per-seat, so a supervisor's edit during a wave is reported as an out-of-scope write and fails a correct task. Record status between waves. (2) **Run the end block before the task commits**, for the reason in hazard 3.

**To use it, change only the `t1` on the first line of each block** to your task id. The per-wave paths live inside the end block as shell assignments, never in a table cell, so no task re-types a regex. T3 and T6 carry their own filled-in copies, which differ from these only in that id.

**Four defects this replaces — measured, not reasoned.** The first three were in the recipe before review 4; the fourth survived into review 5's text as **R5-1**:

1. **`$WAVE_PATHS` was referenced and never assigned.** `grep -vE ""` prints nothing and **exits 1**, so the check passed on **any** tree. Measured: `unset WP; printf 'a\nb\n' | grep -vE "$WP"` → no output, exit 1.
2. **The per-wave patterns were written in markdown table cells with `\|`**, which this platform's grep reads as a **literal pipe**, so the alternation never matched and a *correct* run also failed. Measured on BSD grep 2.6.0-FreeBSD: `echo a | grep -E 'a\|b'` → exit **1**; `printf 'a|b' | grep -E 'a\|b'` → exit **0**; `echo a | grep -E 'a|b'` → exit **0**.
3. **`find` ignores `.gitignore`**, so the gates' own bytecode tripped the check — `.gitignore:2` is `__pycache__/` and `:8` is `.venv/`. `git ls-files -o --exclude-standard` honours it.
4. **R5-1: the verdict depended on the interpreter.** This machine's login shell is `/bin/zsh`. Under zsh, `[ "$f" -nt /missing-stamp ]` is **false**, so with no stamp nothing printed and the check **passed on any tree**; under bash it is true and the check failed loudly. `${PIPESTATUS[0]}` under `set -u` aborts zsh with `parameter not set` (zsh spells it `pipestatus`, 1-indexed). And T3's block tested `-nt /tmp/cao-apl-t3.stamp` without ever creating that file. Separately, bash here is **3.2.57**, and in a 2026-11-01 measurement `[ f -nt s ]` was **false** for a file written immediately after the stamp, while `find f -prune -newer s -print` printed it. **The fix:** every block runs under `bash -euo pipefail <<'EOF' … EOF`, so the outer shell only feeds it text; `-nt` is replaced by `find "$f" -prune -newer "$STAMP" -print`, which exits 1 with `No such file or directory` on a missing stamp in both shells; a `test -f "$STAMP"` runs before any scope check; and the start block, not the reader, creates the stamp.

**The mechanism behind defect 2 is worth naming, because it generalises.** The logic was right and only the transcription was wrong: **executable content placed in a markdown table inherits the table's escaping, and the escaped form is not the runnable form.** The "what input makes it fail / what makes it pass" test does not catch this, because the published command is not the command that was reasoned about. The test that does is coarser — **run the command as it sits in the source file**, not as the rendered page shows it, because the renderer un-escapes `\|` in a table cell and so hides the defect — and it is now the rule here: **no executable command or regex goes in a markdown table cell.** Defect 4 adds a second condition to that test: **run it under the shell a reader will actually paste it into**, which on this machine is zsh. The explicit `bash` wrapper makes the outer shell irrelevant.

**Why the end block captures output instead of piping into `grep -v` directly.** Under `pipefail`, a `grep -v` that selects nothing exits 1 and would fail a *clean* run. `keep_out` treats exit 1 as success and lets exit 2, a real grep error, through. `sed -n '1,20p'` is used in place of `head`, because `head` closing the pipe early can kill the writer with `SIGPIPE`, which `pipefail` reports as a failure.

**What this recipe still cannot detect**, re-checked against the new shape rather than carried over:

| Blind spot | Status under the git-based recipe |
|---|---|
| Deleted tracked files | **CLOSED, staged and unstaged.** `git ls-files -d` reports an unstaged deletion. `git diff --cached --no-renames --diff-filter=D` reports a staged one, which covers `git rm` and the old path of a `git mv`; review 6 (**N-4**) found both passing the earlier version |
| Non-ASCII file names | **CLOSED.** Every git call runs with `-c core.quotePath=false`, so a name like `é.txt` is printed raw rather than C-quoted, which `[ -e ]` would not find and the check would silently skip. A name git still quotes (one containing `"`, `\` or a control character) is **reported as out of scope**, so the check fails closed rather than skipping it |
| Deleted untracked files | **CLOSED for any file untracked when the stamp was taken**, which includes the untracked specification files Requirement 13.7 protects. The start block snapshots the untracked set, and check 3 reports anything that has since disappeared. A file created *and* deleted inside the task is still invisible, and it leaves the tree as it found it. Review 5 raised this: `-d` alone covers tracked files only |
| Staged files | **CLOSED.** `git diff --cached --name-only` is a candidate source, so staging an out-of-scope file does not hide it |
| Symlinks | **CLOSED.** `find -prune -newer` tests the link itself, without following it, so a broken symlink is reported |
| A write inside a declared sibling's prefix | **Still open, by construction.** Wave-level rather than per-task ownership. A separate worktree per wave is the fix |
| Anything outside this worktree | **Still open.** git sees only this repository — not the CAO state directory, the `workflow_outcomes` database, or `CAO_HOME_DIR` temp dirs |
| A write whose mtime is preserved or backdated | **Still open.** `-newer` is still an mtime comparison, though at sub-second resolution where `-nt` was not |
| Work done before the stamp | **Narrowed.** The end block refuses to run without a stamp, so a forgotten stamp fails instead of passing. Work done before the start block ran is still invisible |
| A write to a gitignored path | **Reported as a WARNING, deliberately not a failure.** `--exclude-standard` is what fixes defect 3, and the gates write `__pycache__/` on every run, so failing on ignored paths would fail every task. Review 5 accepted this trade: an ignored file cannot be staged without `git add -f`, so it cannot reach a commit, which is what the check exists to protect. Check 4 lists ignored paths newer than the stamp from `git ls-files -o -i --exclude-standard --directory`, as review 5 suggested. A `find` error inside an ignored path, such as an unreadable directory, prints a warning and never changes the exit status (review 6 **N-5**) |
| A pre-existing untracked file whose name git quotes | **Fails every task until it is renamed or removed.** The fail-closed rule for names containing `"`, `\` or a control character applies to any such file that check 1 sees, including one that existed before the stamp, because a quoted name cannot be tested against the stamp at all. Accepted: failing closed is the point, and the remedy is to rename the file |
| A correct run reported as a failure | **By design, avoided by the two rules above:** an edit to the specification directory during a wave, or a commit before the end block, is reported. The check cannot tell whose edit it was |


## T1 — The creator skill

**Status:** [ ] Not started — **OQ-1a decided** (the user elected to proceed); merge remains gated on **OQ-1b**, the maintainer's answer
**Owner:** `oss-dev`
**Owns:** `skills/cao-agent-plugin-creator/**`

### Description

Create `skills/cao-agent-plugin-creator/` with `SKILL.md` and `evals/evals.json`. The body teaches the manifest contract **from the vendored schema**: `$schema` and `name` are the only required keys (`plugin.schema.json:63`); the schema is closed (`:64`), and CAO treats a key outside it by position: an unknown **top-level** key is a WARNING (`manifest.unknown_field`) and is ignored while the package still loads, and an unknown **nested** key such as `author.twitter` is FATAL (`manifest.invalid`). **Corrected 2026-11-01 (`P-72`):** this description used to say every unknown key is FATAL; `name` is 1–64 characters on the schema's pattern (`:12-18`); `skills/` is optional, one level deep; `README`/`CHANGELOG`/`LICENSE` are **not** schema requirements even though CAO's builder generates them (`build_agent_plugin.py:92, 239, 593, 623`).

**The three Agent Skills limits are measured directly, not via an external script.** Requirement 1.10 was rewritten for this reason: the only script that checks them lives in a non-repo-tracked installed skill of unknown provenance, so a criterion depending on it cannot be tested from a fresh clone. The measurement is three numbers computable with `pyyaml` and the standard library.

### Likely defects to watch for

1. **Copying the source skill's negative boundary.** `cao-skill-creator`'s description ends "Not for provider adapters, **plugins**, or sessions". This feature *reverses* that boundary — our subject **is** a kind of Agent Plugin. Carrying the clause over produces a skill that disclaims its own purpose. Requirement 3.4.
2. **Relying on "agent plugin" as distinguishing vocabulary.** It is **not** safe. `cao-plugin`'s description contains both tokens — "agent" via "CLI Agent Orchestrator" and "plugin" throughout — and the heuristic stems tokens, so only the bigram is absent. Use `plugin.json`, `mcp.json` or `manifest` (Requirement 3.2).
3. **Omitting the migration boundary.** Requirement 3.8 needs a clause excluding migration of an existing client-specific plugin, naming `migrate-agent-plugin`. It is precautionary: CAO's installer **does** project that skill into the store and catalog (`test_installer.py:82-83`), so a user following D4's route has it.
4. **Referencing `skills/cao-skill-creator/scripts/…`.** Both source skills do, and the path does not exist here. An `upstream/main` test already guards against routing to it (`test/test_cao_contributing_skill_accuracy.py:534-559`). Requirement 6.7.
5. **Telling the reader to run `cao plugin validate` without the gate.** With `CAO_AGENT_PLUGINS_ENABLED` unset the command exits 1 and emits **no JSON**, so a reader following it literally concludes their package is broken. Requirement 1.8.
6. **Measuring the body with `wc -l` on the whole file.** The 500-line limit counts the text *after* the closing `---`, stripped. `wc -l SKILL.md` over-counts and sends you trimming prose you did not need to trim.
7. **Using a third-party UI framework's product language** — "self-improving", "AI coworkers", "one checkpoint", "governed" (Requirement 16.4). A live risk, not a theoretical one: that product's automatic-learning feature proposes skills as `SKILL.md` files, which is adjacent to what this skill does, so borrowed phrasing would imply a shared design this feature does not have.
8. **Asserting a spec section number.** The Agent Plugins specification prose was never read (`research.md:300`). Cite the vendored schema path, not "§4.1".

### Requirements addressed

1.1–1.9; **1.10's first clause only** (the three limits, measured directly); 3.1–3.8, 5.1, 5.2, 6.1, 6.7. **1.10's second clause, that the bundled validator reports the skill as passing, is carried by T5's "Command that must pass"**, because the validator does not exist until T2 lands.

### Acceptance criteria

- [ ] `test -f skills/cao-agent-plugin-creator/SKILL.md` and `test -f skills/cao-agent-plugin-creator/evals/evals.json` both exit 0.
- [ ] The three limits, measured directly by the block below (run from anywhere inside the worktree; it changes to the repository root itself), which prints `cao-agent-plugin-creator`, a description length ≤ `1024` and a body line count ≤ `500`, exits 0 when all three hold, and exits non-zero on any breach:

```bash
bash -euo pipefail <<'EOF'
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
uv run --with pyyaml python - <<'PY'
import re,sys,yaml,pathlib
p=pathlib.Path("skills/cao-agent-plugin-creator/SKILL.md")
raw=p.read_text(); _,fm,body=raw.split("---",2)
d=yaml.safe_load(fm); n=d["name"]; desc=d["description"]
lines=len(body.strip().splitlines())
ok = (n=="cao-agent-plugin-creator"
      and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*",n) and len(n)<=64
      and len(desc)<=1024 and lines<=500)
print(n,len(desc),lines); sys.exit(0 if ok else 1)
PY
EOF
```

- [ ] The `description` contains at least one of `plugin.json`, `mcp.json`, `manifest`. A check for the bigram `agent plugin` alone does **not** satisfy this.
- [ ] The `description` contains a negative boundary naming the event-plugin system, and a negative boundary naming `migrate-agent-plugin`.
- [ ] The `description` does **not** contain the clause `plugins, or sessions` inherited from the source skill.
- [ ] `grep -n 'skills/cao-skill-creator' skills/cao-agent-plugin-creator/SKILL.md` returns nothing (exit 1).
- [ ] Every occurrence of `cao plugin validate` in the body is accompanied, in the same fenced block or the preceding sentence, by `CAO_AGENT_PLUGINS_ENABLED`.
- [ ] `python3 -c "import json;d=json.load(open('skills/cao-agent-plugin-creator/evals/evals.json'));assert isinstance(d,dict);t=d['trigger_evals'];print(len([x for x in t if x['should_trigger']]),len([x for x in t if not x['should_trigger']]))"` prints two numbers each ≥ `5`.
- [ ] At least one `should_trigger: false` query uses event-plugin phrasing.
- [ ] **[review-checked]** Requirements 1.4–1.7 and 3.3, 3.5 are confirmed by reading the body; they have no mechanical check and are not pretended to.
- [ ] **T1's commit sha is recorded in `STATUS.md` between waves, after wave 1 ends**, never during a wave (hazard 4's rule 1 forbids spec-directory edits during a wave), (this was Requirement 15.5's reference point; since OQ-17 was dropped on 2026-11-02 it no longer gates anything, and the record is kept as history).
- [ ] **Optional bootstrap check**, not a gate: the installed `cao-skill-creator`'s `validate_skills.py` reports this skill passing. That script is **not in the repository** (`P-11`) and its provenance is unknown (`P-14`), so it cannot be a required criterion.
- [ ] Scope, per hazard 4 (wave 1): hazard 4's **start block**, run with `-s t1` before any work, prints `stamp taken: /tmp/cao-apl-t1.stamp`; hazard 4's **end block**, run with `-s t1` when the work is done, prints `scope OK: t1` and exits 0. A missing stamp makes the end block exit **2**; an out-of-scope write, a deleted tracked file or a deleted untracked file makes it exit **1**; a gitignored write only prints a warning. **Candidates come from git, not from a tree walk, and not from a `git status` line diff:** a tree walk ignores `.gitignore` and trips on the gates' own `__pycache__`, and a status-line diff cannot see an edit to an already-untracked file. `find` is used only to test each git-listed candidate against the stamp.

**Command that must pass:**
```bash
bash -euo pipefail <<'EOF'
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
uv run --with pyyaml python -c "import yaml,pathlib,sys;raw=pathlib.Path('skills/cao-agent-plugin-creator/SKILL.md').read_text();_,fm,body=raw.split('---',2);d=yaml.safe_load(fm);sys.exit(0 if len(d['description'])<=1024 and len(body.strip().splitlines())<=500 else 1)"
python3 -c "import json;d=json.load(open('skills/cao-agent-plugin-creator/evals/evals.json'));assert isinstance(d,dict)"
EOF
```

---

## T2 — The audit skill and its validator

**Status:** [ ] Not started — **OQ-1a** and **OQ-4** decided; merge gated on **OQ-1b**
**Owner:** `oss-dev`
**Owns:** `skills/cao-agent-plugin-audit/**`

### Description

Create `skills/cao-agent-plugin-audit/` with `SKILL.md`, `evals/evals.json`, and — `scripts/validate_agent_plugin.py` with a PEP 723 block (**OQ-4**, decided). **OQ-13** recommends a `references/` directory here, because the rule and severity tables are the content most likely to push the body toward 500 lines, and because the upstream canonical example ships its own skill with exactly such a reference package including a `validation-checklist.md` (`P-61`).

**This task carries the feature's surviving justification, and it is narrower than the first revision claimed.** `review-1.md` **F-1** showed that the skill D4 names already covers naming — its `references/validation-checklist.md` checks the name rules at `:13` and folder-equals-`name` plus Agent Skills naming at `:22`. What it does **not** do is enforce anything mechanically (30 human checkboxes) or mention the 1024-character or 500-line limits **at all**. So the claim this skill must support is: **no artifact CAO ships mechanically enforces the name regex, the 1024-character description limit, or the 500-line body limit.**

If T2 does not check those three mechanically, the feature has no evidenced justification left.

### Likely defects to watch for

1. **Wrapping `cao plugin validate` and calling it an audit.** It does not check the three limits. An audit skill that only shells out to it adds nothing over an existing gate, while every check appears green. The single most likely way to produce a plausible, useless skill.
2. **Claiming no prior art audits an Agent Plugin.** The D4 skill's checklist does, by hand. Requirement 2.11 requires recording that. Overstating here is what made the first revision rebuttable with its own citation.
3. **Stating that CAO rejects an over-limit skill.** **Since wave 1, T3 has observed the opposite for the two length limits** (`P-6`): a 2000-character description and a 600-line body are admitted, exit 0. The name limits stay inferred from `models/skill.py:6-19`. The original text follows. Inferred from `models/skill.py:6-19`, never run (`P-6`). Requirement 2.7 requires it be marked inferred unless **T3** has settled it. T2 does **not** depend on T3 in the wave plan, and deliberately so — adding the dependency would serialise wave 1 for one sentence. So the rule is: write it as **inferred**, and only cite T3 if T3's report has already landed. Do not block on T3 (`review-2.md` **N-E**).
4. **Conflating two different exit-1 conditions.** An unset gate exits 1 with a refusal and **no JSON**; a FATAL finding exits 1 with parseable JSON carrying `loadable`. The discriminator is **whether stdout parses as JSON**, never the exit status. Requirement 4.8. A wrapper that branches on exit status alone will tell a user their package is broken when an environment variable was unset.
5. **Declaring a PEP 723 dependency the script does not import.** `run_trigger_evals.py` declares `httpx>=0.27` at `:3` and imports only `json, re, sys, pathlib` at `:29-30`. Requirement 4.4.
6. **Referencing artifacts that do not exist.** The source audit skill's evals cite an absolute path on another machine, a `baseline-report.json` that is absent, and `npx skills-ref validate`. Requirement 2.8.
7. **Fetching the schema.** CAO is forbidden from fetching while loading an Agent Plugin, and the vendored bytes are the only ones it validates against (`PIN.json:7`). Requirement 4.5.
8. **Depending on the harness-oss validator.** It hard-codes `ROOT` at `:25` and never reads `sys.argv`, so it silently validates *its own* package whatever you pass it. #1121's audit brief already made this mistake and reported a pass that proved nothing. Requirement 4.6.

### Requirements addressed

2.1–2.12, 3.1–3.8, 4.1–4.9, 5.1, 5.2, 6.1, 6.7

### Acceptance criteria

- [ ] `test -f skills/cao-agent-plugin-audit/SKILL.md` exits 0 and the frontmatter `name` equals `cao-agent-plugin-audit`.
- [ ] The same three-limit measurement as T1, run against this skill, prints a description length ≤ `1024` and a body line count ≤ `500` and exits 0.
- [ ] The body states that CAO's package validation does **not** check the name regex, the 1024-character limit, or the 500-line limit.
- [ ] The body specifies mechanical checks for **all five** of: name regex, 64-character name bound, folder-equals-`name`, 1024-character description bound, 500-line body bound.
- [ ] The body records that the D4-named skill's `references/validation-checklist.md` covers naming manually and mentions neither numeric limit. `grep -n 'validation-checklist' skills/cao-agent-plugin-audit/SKILL.md` matches at least once.
- [ ] The body marks CAO's behaviour toward an over-limit skill as **inferred**, or cites T3's result. `grep -n -i 'inferred\|T3' skills/cao-agent-plugin-audit/SKILL.md` matches.
- [ ] The body states the JSON-parse discriminator between an unset gate and a FATAL finding, and does not present the exit status as the discriminator.
- [ ] `grep -rn 'harness-oss\|validate-plugin.py' skills/cao-agent-plugin-audit/` returns nothing (exit 1).
- [ ] `grep -rn '/Users/\|baseline-report.json\|skills-ref' skills/cao-agent-plugin-audit/` returns nothing (exit 1). Here `/Users/` is a **search pattern, not a path this specification depends on**: it detects the absolute-path-on-another-machine defect recorded in `P-56`, where the source audit skill's evals cite a directory that exists on no reachable machine.
- [ ] WHERE a script is bundled: its first line opens a PEP 723 `# /// script` block, and every distribution named there is imported by the script — verified by reading the import list against the block, not by assuming.
- [ ] WHERE a script is bundled: run against `agent-plugin/cao` it exits 0; run against a fixture whose skill has a 2000-character description it exits non-zero **and names that skill**.
- [ ] WHERE a script is bundled: no URL in it is an argument to a network request; any URL present is a `$schema` identifier string.
- [ ] **`--skills-dir <dir>` mode — gate 1's contract** (Requirement 4.3; review 6 **R6-B-1**). The script accepts `--skills-dir <dir>`. **Each immediate child of `<dir>` that contains a `SKILL.md` is one skill**, checked for all five limits. **Everything else is ignored, and the script's help text and the skill body say so explicitly:** a `plugin.json` at the top of `<dir>` (this repository's `skills/plugin.json` is an inert proto-manifest with no `$schema`), and any child without a `SKILL.md`, such as `skills/vendor/`. Tested against a `mktemp -d` directory, never a committed fixture: with one conformant skill, a top-level `plugin.json` and a `vendor/` child holding no `SKILL.md`, it **exits 0**; after adding a second skill whose description is 2000 characters, it **exits non-zero and names that skill**.
- [ ] **Exit contract**, stated in the script and the body: **0** = no finding above advisory, **1** = at least one finding, **any other status** = the audit itself failed (bad arguments, unreadable input, a crash). T6 relies on this to tell a run with findings from a run that never happened (review 6 **N-7**).
- [ ] **The script never reads stdin.** Every runnable block in this document is fed to `bash` on stdin (`bash -s` or a heredoc), so a command inside one that read stdin would consume the rest of the block. Verified by reading the script: no `sys.stdin`, no `input()`, no `-` path argument (review 6).
- [ ] **Requirement 2.12 — the description/skills listing is PRODUCED.** Against a fixture package **generated in a `mktemp -d` directory and never committed under `skills/` or anywhere else in the repository**, whose `description` names skills it does not ship, the audit output contains **both** the manifest's declared `description` **and** the discovered skill names, so a reader can compare them. **This tests that the listing is emitted, NOT that a mismatch is detected** — those are different criteria and only the first is testable, because nobody can say what input would make a semantic-mismatch check fail.
- [ ] **The 2.12 finding is classified `advisory`** in the audit output, and running against that fixture — which is otherwise conformant, so the advisory is its only finding — **exits 0**: the advisory alone never makes the audit non-zero. That is the testable form of "advisory, never fatal".
- [ ] **[review-checked]** The bundled validator's output **does not claim to have detected** a mismatch between the description and the skill set. `grep -in 'mismatch\|does not match\|inconsistent' ` over the audit output returns nothing that asserts a verdict on meaning.
- [ ] `evals/evals.json` parses as a dict with ≥ 5 should-trigger and ≥ 5 should-not-trigger queries, at least one of the latter in event-plugin phrasing.
- [ ] **[review-checked]** Requirements 2.5, 2.6, 4.1, 4.7 are confirmed by reading the body.
- [ ] Scope, per hazard 4 (wave 1): hazard 4's **start block**, run with `-s t2` before any work, prints `stamp taken: /tmp/cao-apl-t2.stamp`; hazard 4's **end block**, run with `-s t2` when the work is done, prints `scope OK: t2` and exits 0. A missing stamp makes the end block exit **2**; an out-of-scope write, a deleted tracked file or a deleted untracked file makes it exit **1**; a gitignored write only prints a warning. **Candidates come from git, not from a tree walk, and not from a `git status` line diff:** a tree walk ignores `.gitignore` and trips on the gates' own `__pycache__`, and a status-line diff cannot see an edit to an already-untracked file. `find` is used only to test each git-listed candidate against the stamp.

**Command that must pass:**
```bash
bash -euo pipefail <<'EOF'
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
uv run --with pyyaml python -c "import yaml,pathlib,sys;raw=pathlib.Path('skills/cao-agent-plugin-audit/SKILL.md').read_text();_,fm,body=raw.split('---',2);d=yaml.safe_load(fm);sys.exit(0 if len(d['description'])<=1024 and len(body.strip().splitlines())<=500 else 1)"
# grep exits 1 for "no match", which is the pass; 0 (a match) or 2 (an error) must fail.
set +e; grep -rqnE 'harness-oss|validate-plugin\.py|/Users/|baseline-report\.json|skills-ref' skills/cao-agent-plugin-audit/; G=$?; set -e
test "$G" -eq 1
# Negative control: gate 1 must be able to FAIL. A skill whose description is 2000
# characters, in a temporary directory, must give exit 1 (findings) and be named.
NEG=$(mktemp -d); mkdir "$NEG/zz-overlimit"
printf -- '---\nname: zz-overlimit\ndescription: %s\n---\nbody\n' "$(printf 'x%.0s' $(seq 1 2000))" > "$NEG/zz-overlimit/SKILL.md"
set +e; OUT=$(uv run --quiet --script skills/cao-agent-plugin-audit/scripts/validate_agent_plugin.py --skills-dir "$NEG" 2>&1); NX=$?; set -e
test "$NX" -eq 1 || { echo "negative control: expected exit 1, got $NX" >&2; exit 1; }
grep -q 'zz-overlimit' <<<"$OUT" || { echo "negative control: over-limit skill not named" >&2; exit 1; }
rm -rf "$NEG"
EOF
```

---

## T3 — Settle whether CAO admits an over-limit skill

**Status:** [ ] Not started — **OQ-1a** decided; merge gated on **OQ-1b**
**Owner:** `kiro-researcher`
**Owns:** `docs/issues/1153-agent-plugin-lifecycle/t3-overlimit-experiment.md` — the **report**. The experiment runs in `mktemp -d`; no other repository file is touched.

### Description

The highest-value experiment in the specification, and it writes no code.

Requirement 2 and correctness property P2 rest on a premise that is **inferred, not run**: that `cao plugin validate` admits a skill breaking the Agent Skills name and length limits (`models/skill.py:6-19`; `research.md:301`). Settle it. **Done in wave 1:** `P-6` is OBSERVED for the two length limits, and the name limits were not tested (`t3-overlimit-experiment.md`).

In a temporary directory, build a minimal conformant Agent Plugin — `plugin.json` with `$schema` and `name` only — containing two skills: one whose `description` exceeds 1024 characters, one whose body exceeds 500 lines, **each with a folder name matching its frontmatter `name`** so the one check CAO does perform passes. Run `CAO_AGENT_PLUGINS_ENABLED=1 uv run cao plugin validate <dir> --json` and record the verdict, the `findings[]` array and the exit status verbatim.

Point `CAO_HOME_DIR` at a fresh `mktemp -d` and **record** what is in it afterwards. **It is not empty:** T3 observed three empty directories, `fifos/`, `logs/` and `logs/terminal/`, and no files; the cause is inferred to be CAO's startup directory creation and has not been traced (`P-73`). Nothing here asserts emptiness.

### Likely defects to watch for

1. **Reporting the expected answer.** The point is the measurement. If CAO **rejects** the over-limit skill, ground 2 is narrower than Requirement 2.3 claims and `requirements.md` must change. That outcome is a **success** for this task and must be reported plainly.
2. **Letting a folder-name mismatch confound it.** A mismatch makes CAO reject the skill for *that* reason and the experiment measures nothing about the limits. Make the one check CAO performs pass, so the limits are the only variable.
3. **Running it with the gate unset.** Exit 1 with a refusal looks like a rejection. It is not. Confirm the gate is on by also validating a known-good package in the same session, and note that the refusal emits **no JSON** while a real finding does.
4. **Writing the fixture into `test/agent_plugins/fixtures/`.** That is implementation, and this is a spec phase. Temp directory only.
5. **Generating the 500-line body by hand.** Generate it, and assert the measured count before validating; a hand-written near-miss wastes the run.
6. **Checking for a clean tree.** `test -z "$(git status --porcelain)"` **fails on this tree today** — the five specification files are untracked. Compare against a snapshot instead.

### Requirements addressed

Settles `P-6`. Evidence for 2.3, 2.4, 2.7, 2.11; correctness property P2; `design.md § Testing strategy` item 1.

### Acceptance criteria

- [ ] A temporary package whose `plugin.json` contains exactly `$schema` and `name` validates clean first: `CAO_AGENT_PLUGINS_ENABLED=1 uv run cao plugin validate <dir>` exits 0 — the positive control.
- [ ] One skill's `description` is **measured** at > 1024 characters and one skill's body at > 500 lines, both numbers reported, with folder name equal to frontmatter `name` in both.
- [ ] `CAO_AGENT_PLUGINS_ENABLED=1 uv run cao plugin validate <dir> --json` is run and its **exit status**, `loadable` value and complete `findings[]` array are reported verbatim.
- [ ] The same command with the gate unset is run, and the report records that it exits 1 **and emits no parseable JSON**, establishing the discriminator Requirement 4.8 depends on.
- [ ] `CAO_HOME_DIR` pointed at a fresh `mktemp -d`, and its contents after the run **recorded** in the report, not asserted. T3 observed `fifos/`, `logs/` and `logs/terminal/`, all empty (`P-73`).
- [ ] Scope, per hazard 4 (wave 1): hazard 4's **start block**, run with `-s t3` before any work, prints `stamp taken: /tmp/cao-apl-t3.stamp`; hazard 4's **end block**, run with `-s t3` when the work is done, prints `scope OK: t3` and exits 0. A missing stamp makes the end block exit **2**; an out-of-scope write, a deleted tracked file or a deleted untracked file makes it exit **1**; a gitignored write only prints a warning. T3 and T6 carry these two blocks filled in; run those copies. **Candidates come from git, not from a tree walk, and not from a `git status` line diff:** a tree walk ignores `.gitignore` and trips on the gates' own `__pycache__`, and a status-line diff cannot see an edit to an already-untracked file. `find` is used only to test each git-listed candidate against the stamp.
- [ ] The report states in one sentence whether `P-6` is now **OBSERVED** or **DISPROVED**, and if disproved, which requirement criteria must change.
- [ ] The report is at `docs/issues/1153-agent-plugin-lifecycle/t3-overlimit-experiment.md`, so its findings have a cited home rather than living only in a message.

**Before you start — creates the stamp and snapshot the scope check needs.** Run this first; nothing else in T3 creates `/tmp/cao-apl-t3.stamp`, and the scope check below refuses to run without it:
```bash
bash -euo pipefail -s t3 <<'EOF'
case "$1" in t[1-7]) ;; *) echo "unknown task: $1" >&2; exit 2 ;; esac
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
g() { git -c core.quotePath=false "$@"; }   # print non-ASCII paths raw, not C-quoted
STAMP="/tmp/cao-apl-$1.stamp"
touch "$STAMP"
{ g ls-files -o --exclude-standard; g diff --cached --name-only; } \
  | LC_ALL=C sort -u > "$STAMP.untracked"
echo "stamp taken: $STAMP"
EOF
```

**Command that must pass** — the experiment. **Run it from inside this worktree**, so `uv run cao` resolves this checkout, and pass the fixture directory as an **absolute** path. The validator's exit status is **recorded, not required to be 0**, because a rejection is a legitimate result (defect 1):
```bash
bash -euo pipefail -s "$FIXTURE" <<'EOF'
FIXTURE="${1:?pass the fixture directory as the argument}"
case "$FIXTURE" in /*) ;; *) echo "fixture path must be absolute: $FIXTURE" >&2; exit 2 ;; esac
test -f "$FIXTURE/plugin.json"
TOP=$(git rev-parse --show-toplevel) || { echo "run this from inside the worktree" >&2; exit 2; }
cd "$TOP"
CAO_HOME="$(mktemp -d)"
set +e
CAO_AGENT_PLUGINS_ENABLED=1 CAO_HOME_DIR="$CAO_HOME" uv run cao plugin validate "$FIXTURE" --json
echo "exit=$?"
set -e
echo "CAO_HOME_DIR contents after the run (recorded, not asserted; T3 saw empty fifos/ logs/ logs/terminal/):"
ls -A "$CAO_HOME"
EOF
```

**Scope check that must pass** — hazard 4's end block with `t3`; exits 0 and prints `scope OK: t3`:
```bash
bash -euo pipefail -s t3 <<'EOF'
TASK="$1"
case "$TASK" in
  t1|t2|t3) WAVE_PATHS='^(skills/cao-agent-plugin-creator/|skills/cao-agent-plugin-audit/|docs/issues/1153-agent-plugin-lifecycle/t3-overlimit-experiment\.md$)' ;;
  t4|t5)    WAVE_PATHS='^(scripts/sync_skills\.py$|src/cli_agent_orchestrator/skills/|scripts/build_agent_plugin\.py$|test/agent_plugins/test_packages\.py$|test/test_agent_plugin_pin_boundedness\.py$|agent-plugin/cao-agent-plugin-lifecycle/)' ;;
  t6)       WAVE_PATHS='^docs/issues/1153-agent-plugin-lifecycle/audit-(report\.md|raw\.txt)$' ;;
  t7)       WAVE_PATHS='^(CODEBASE\.md$|docs/skills\.md$|docs/agent-plugins\.md$)' ;;
  *) echo "unknown task: $TASK" >&2; exit 2 ;;
esac
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
g() { git -c core.quotePath=false "$@"; }   # print non-ASCII paths raw, not C-quoted
STAMP="/tmp/cao-apl-$TASK.stamp"
# A missing stamp must fail LOUDLY. It must never let the check pass.
test -f "$STAMP" || { echo "MISSING STAMP $STAMP: run the start block first" >&2; exit 2; }
test -f "$STAMP.untracked" || { echo "MISSING SNAPSHOT $STAMP.untracked: run the start block first" >&2; exit 2; }
# grep -v exits 1 when it selects nothing, which here means success; 2 is a real error.
keep_out() { grep -vE "$WAVE_PATHS" || [ $? -eq 1 ]; }
present() { { g ls-files -o --exclude-standard; g diff --cached --name-only; } | LC_ALL=C sort -u; }

# 1. Writes since the stamp: modified, staged, and untracked-but-not-ignored paths.
#    find -prune -newer checks the path itself (a symlink is not followed) and
#    errors on a missing stamp; the `|| exit 2` carries that error out of the loop.
#    A path git still prints quoted (it contains `"`, `\` or a control character)
#    cannot be tested, so it is reported rather than skipped: fail closed.
WRITES=$(
  { g ls-files -m; g diff --cached --name-only; g ls-files -o --exclude-standard; } \
    | LC_ALL=C sort -u \
    | while IFS= read -r f; do
        if [ "${f#\"}" != "$f" ]; then printf '%s\n' "$f"; continue; fi   # no `case` here: bash 3.2 cannot parse `pat)` inside $( )
        [ -e "$f" ] || [ -L "$f" ] || continue     # gone: covered by checks 2 and 3
        find "$f" -prune -newer "$STAMP" -print || exit 2
      done \
    | keep_out
)
# 2. Deleted tracked files: unstaged (ls-files -d) and staged, which covers `git rm`
#    and the old path of a `git mv` (--no-renames reports a rename as D plus A).
DELETED=$(
  { g ls-files -d; g diff --cached --no-renames --name-only --diff-filter=D; } \
    | LC_ALL=C sort -u | keep_out
)
# 3. Deleted untracked files: present at the stamp, absent now.
GONE=$(present | LC_ALL=C comm -23 "$STAMP.untracked" - | keep_out)
# 4. Gitignored paths written since the stamp: a WARNING, never a failure. A find
#    error here (an unreadable directory, say) is reported and does not change
#    the exit status.
IGNORED=$(
  g ls-files -o -i --exclude-standard --directory \
    | while IFS= read -r f; do
        find "$f" -newer "$STAMP" -print 2>/dev/null \
          || echo "WARNING (not a failure): check 4 could not read all of $f" >&2
      done \
    | keep_out
)
if [ -n "$IGNORED" ]; then
  echo "WARNING (not a failure): gitignored paths written since the stamp:" >&2
  printf '%s\n' "$IGNORED" | sed -n '1,20p' >&2
fi

FAIL=0
if [ -n "$WRITES" ];  then printf '%s\n' "$WRITES"  | sed 's/^/OUT-OF-SCOPE WRITE: /';     FAIL=1; fi
if [ -n "$DELETED" ]; then printf '%s\n' "$DELETED" | sed 's/^/OUT-OF-SCOPE DELETION: /';  FAIL=1; fi
if [ -n "$GONE" ];    then printf '%s\n' "$GONE"    | sed 's/^/UNTRACKED FILE DELETED: /'; FAIL=1; fi
if [ "$FAIL" -eq 0 ]; then echo "scope OK: $TASK"; fi
exit "$FAIL"
EOF
```

---

## T4 — Wheel shipping and mirror parity

**Status:** [ ] Not started — **OQ-1a** and **OQ-6** decided; merge gated on **OQ-1b**
**Owner:** `oss-dev`
**Owns:** `scripts/sync_skills.py`, `src/cli_agent_orchestrator/skills/**`

### Description

If **OQ-6** resolves to ship the skills in the Python distribution, add both names to `SHIPPED_SKILLS` and regenerate the tracked mirror with `python scripts/sync_skills.py`. If OQ-6 resolves to Agent-Plugin-only, **this task is dropped** and Requirement 7.7 applies.

`pyproject.toml` is **not** touched.

**Expected, not drift: the audit skill's mirror carries schema bytes** (`P-74`). `skills/cao-agent-plugin-audit/` includes `schemas/1.0.0/plugin.schema.json` and `mcp.schema.json`, byte-identical to the vendored schemas, which its validator needs. `sync_skills.py` copies the whole skill directory, so the mirror at `src/cli_agent_orchestrator/skills/cao-agent-plugin-audit/schemas/1.0.0/` holds a further copy. Do not remove or deduplicate it: the validator refuses to run (exit 2) without byte-identical, pin-matching copies, and `diff -r` against `skills/` covers them.

### Likely defects to watch for

1. **Adding a `skills/**` entry to `[tool.hatch.build] artifacts` to "make sure it ships".** This **actively fails CI**: `test_artifacts_entries_are_all_guarded` at `test/test_hatch_artifacts_guard.py:123-128` asserts every `artifacts` entry has a wheel-contents guard — "new globs cannot join silently". The correct action is to touch `pyproject.toml` not at all. The reasoning is at `:33-37`: a tracked directory "ships via normal packaging regardless of what its `artifacts` entry says".
2. **Counting the mirror with `git ls-files`.** It counts **index** entries, so it keeps printing 14 until the new mirror files are staged — and every check runs before its task commits (**OQ-16** decided: commit, never push), so the check would fail on a correct tree. Use `find`. This was `review-1.md` **F-2**'s "can never pass" case.
3. **Editing `SHIPPED_SKILLS` without regenerating the mirror.** `--check` then exits 1 and the parity test fails. Both copies are committed, which is why they drift silently.
4. **Hand-editing the mirror.** It is generated; run the script.
5. **Adding an entry to `SKILL_RENAMES`.** Nothing is renamed. It is the one-shot retirement step for a *renamed* shipped skill and is currently empty pending a maintainer decision. Requirement 6.3.
6. **Accepting exit 0 as proof.** `--check` also exits 0 if your edit did nothing. Assert the new count explicitly.

### Requirements addressed

7.1–7.8, 6.3

### Acceptance criteria

- [ ] `uv run python -c "import importlib.util;s=importlib.util.spec_from_file_location('x','scripts/sync_skills.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);print(len(m.SHIPPED_SKILLS));print('cao-agent-plugin-creator' in m.SHIPPED_SKILLS,'cao-agent-plugin-audit' in m.SHIPPED_SKILLS)"` prints `16` then `True True`. **Under the narrowed-D4 path this is `15` and a single `True`** (Requirement 14.2).
- [ ] `uv run python scripts/sync_skills.py --check` exits 0 and reports **16** shipped skills in sync.
- [ ] `find src/cli_agent_orchestrator/skills -name SKILL.md -maxdepth 2 | wc -l` prints `16`. **Not `git ls-files`** — the mirror is unstaged.
- [ ] `diff -r skills/cao-agent-plugin-creator src/cli_agent_orchestrator/skills/cao-agent-plugin-creator` reports no differences, and likewise for the audit skill.
- [ ] `git diff --quiet HEAD -- pyproject.toml` exits 0.
- [ ] No `skills` entry appears inside the `[tool.hatch.build] artifacts` block.
- [ ] `uv run pytest -q -p no:cacheprovider test/test_skill_packaging_parity.py test/test_hatch_artifacts_guard.py --no-cov` exits 0.
- [ ] `git diff --quiet HEAD -- src/cli_agent_orchestrator/cli/commands/init.py` exits 0 — `SKILL_RENAMES` unchanged.
- [ ] Scope, per hazard 4 (wave 2): hazard 4's **start block**, run with `-s t4` before any work, prints `stamp taken: /tmp/cao-apl-t4.stamp`; hazard 4's **end block**, run with `-s t4` when the work is done, prints `scope OK: t4` and exits 0. A missing stamp makes the end block exit **2**; an out-of-scope write, a deleted tracked file or a deleted untracked file makes it exit **1**; a gitignored write only prints a warning. **Candidates come from git, not from a tree walk, and not from a `git status` line diff:** a tree walk ignores `.gitignore` and trips on the gates' own `__pycache__`, and a status-line diff cannot see an edit to an already-untracked file. `find` is used only to test each git-listed candidate against the stamp.

**Command that must pass:**
```bash
bash -euo pipefail <<'EOF'
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
uv run python scripts/sync_skills.py --check
test "$(find src/cli_agent_orchestrator/skills -maxdepth 2 -name SKILL.md | wc -l | tr -d ' ')" = 16
uv run pytest -q -p no:cacheprovider test/test_skill_packaging_parity.py test/test_hatch_artifacts_guard.py --no-cov
git diff --quiet HEAD -- pyproject.toml
EOF
```

---

## T5 — The dogfood package

**Status:** [ ] Not started — **OQ-1a**, **OQ-7** and **OQ-12** decided; merge gated on **OQ-1b**
**Owner:** `oss-dev`
**Owns:** `scripts/build_agent_plugin.py`, `agent-plugin/cao-agent-plugin-lifecycle/**`, `test/agent_plugins/test_packages.py`, `test/test_agent_plugin_pin_boundedness.py`

### Description

Under **OQ-7 option A** (recommended): add a third `PackageConfig`, append it to `PACKAGES` at `scripts/build_agent_plugin.py:188` with both new skills in its allowlist, and generate the package **in-process at the held pin** (below). The package commits byte-identical copies of the skills it ships, including any `references/` subdirectory, as the two existing packages do (`P-16`).

**Build it at `2.5.3`, in-process, and never with `make agent-plugin`** (Requirement 8.13). `make agent-plugin` rebuilds every package at `pyproject.toml`'s `2.5.4` and moves the pin. Call `build_package(config, committed_package_version(), PACKAGES_DIR)` instead, then `make check-agent-plugin`. **The trap:** `committed_package_version()` reads every entry in `PACKAGES`, so once your new config is appended and before its directory exists it returns **`None`** (`P-68`, measured), and `--check` then falls back to `2.5.4` and reports **every** package `CONTENT DIFFERS`. Capture the version before appending the config, or read it from the two existing manifests, and assert it equals `2.5.3` before you build. The runnable form, after the config is appended and both skills exist (review 6 **N-14**):

```bash
bash -euo pipefail <<'EOF'
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
uv run python - <<'PY'
import json, sys
sys.path.insert(0, "scripts")
import build_agent_plugin as b
# The held pin, read from the two EXISTING packages. committed_package_version()
# cannot be used yet: with the third config appended and its directory absent it
# returns None (P-68).
held = {json.load(open(b.PACKAGES_DIR / n / "plugin.json"))["version"]
        for n in ("cao", "cao-contributor")}
assert held == {"2.5.3"}, f"held pin is not 2.5.3: {held}"
cfg = next(c for c in b.PACKAGES if c.name == "cao-agent-plugin-lifecycle")
b.build_package(cfg, "2.5.3", b.PACKAGES_DIR)
v = b.committed_package_version()
assert v == "2.5.3", f"committed_package_version() is {v!r}, not 2.5.3"
print("built cao-agent-plugin-lifecycle at", v)
PY
make check-agent-plugin
EOF
```

**Also extend `test/test_agent_plugin_pin_boundedness.py:484-493`** (Requirement 8.11; review 7 **R7-B-1**). `test_packages_disagreeing_is_unknowable` writes only the `cao` and `cao-contributor` manifests, so once a third config exists it still passes, but only because the third manifest is missing, not because two disagree. Make the fixture write **one manifest per entry in `bap.PACKAGES`**, built from the config names rather than a hard-coded list (review 8 **R8-N-4**), with at least two versions differing, so disagreement is what produces `None` and a fourth package later is covered without another edit.

**Also extend every two-package site in `test/agent_plugins/test_packages.py`, not only the install test** (Requirement 8.11, `P-69`, `review-1.md` **N-13**). Each passes with a third package present while covering only the first two, so no test fails to tell you: the `[OPERATOR_DIR, CONTRIBUTOR_DIR]` parametrisations at `:42`, `:50`, `:54`, `:67`, `:83` and `:312` (the last is `TestPackagesInstallThroughTheRealPipeline`, `:309` at `27311798` and `:345` after this task, `P-77`); the `(config, package_dir)` parametrisation at `:216-219`; the pairwise disjointness assertion at `:223-225`; the both-packages `--check` assertion at `:227-234`; and `test_both_packages_install_side_by_side` at `:326-340`, with its two-directory loop at `:328` and its `{"cao", "cao-contributor"}` equality at `:336`.

**Expected, not drift: the package carries schema bytes too** (`P-74`). `build_package` copies `skills/cao-agent-plugin-audit/` whole, so `agent-plugin/cao-agent-plugin-lifecycle/skills/cao-agent-plugin-audit/schemas/1.0.0/` holds another byte-identical copy of the vendored schemas, and the drift guard checks it like every other skill file. The package-mode gate-1 line runs the validator against this package; that validator finds CAO's `PIN.json` from the repository root and must agree with it. A **WARNING**-level CAO finding makes that validator exit **1** where `cao plugin validate` exits 0 (`P-76`). The command below still requires **0**: a generated manifest has no unknown keys, so a 1 here is a real finding to fix, and the difference from CAO's exit is the exit contract, not a broken gate.

**Option B is not taken** (**OQ-7** decided). Its in-flight-conflict cost is gone anyway — **#1121 is merged as `00611d11`**, an ancestor of this worktree's `HEAD` — but the decision rests on the narrative ground that the package is the deliverable. **Option C — `harness-oss` — is rejected** (Requirement 8.7).

### Likely defects to watch for

1. **Adding a skill to a `PackageConfig` before it exists in `skills/`.** `source_skill_dir` raises a build error (`build_agent_plugin.py:666-674`) telling you to fix the allowlist or add the skill. Why T1 and T2 are dependencies.
2. **Hand-writing the package files.** Every file in both existing packages is generated — manifests by `render_manifest()`, README by `render_readme()`, CHANGELOG by `render_changelog()`, skills copied by `build_package()`. A hand-written `plugin.json` will differ from a fresh build and the drift guard will report it.
3. **Letting the version pin drift.** Both committed packages pin `2.5.3` while `pyproject.toml` is at `2.5.4`, and the lag is **deliberate**. #1121 had to rebuild in-process at `committed_package_version()` because the script has no keep-pin flag — which is what sibling issue **#1152** (`--keep-committed-pin`) exists to add. Bumping the two existing packages as a side effect is a change nobody asked for. Requirement 9.6.
4. **Leaving `cao-agent-plugin-lifecycle` unresolved.** It appears in T5, T6 and T7, and T7's `CODEBASE.md` row must match the manifest `name` exactly. **OQ-12** must be answered first.
5. **Forgetting `CODEBASE.md` under option A.** That row enumerates the packages by name, so a third leaves it factually wrong. It is **T7's** file — coordinate; do not edit it here.
6. **Reporting exit 0 from the builder as proof.** The builder *writes*; `--check` *verifies*. Run `--check` separately and read the version it names.
7. **Choosing a `name` the schema rejects.** The pattern forbids `--` and `..` and requires start and end in `[a-z0-9]`. The schema is closed, but **CAO does not fail on a typo'd top-level key**: it reports a WARNING, `manifest.unknown_field`, ignores the key and loads the package, so a typo silently drops the field you meant (`P-72`). A typo'd key nested in an object such as `author` is FATAL. The manifest is generated by `render_manifest()`, so this bites only if someone edits it by hand.
8. ~~**"Fixing" the stale #448 comments while in the file.**~~ **Moot:** #1121 already fixed them (`P-52`); `build_agent_plugin.py:38-40` and `:179` now describe #448 as merged. Retained so a reader of an earlier revision does not hunt for a defect that no longer exists.
9. **Claiming the package is "dogfooded in CI".** It is not: the `agent-plugins-dogfood` job reaches only `agent-plugin/cao` through `run.sh` (`P-67`). Say it is **gated in CI by `make check-agent-plugin`** (Requirement 8.12). Extending `run.sh` is an open user question, not part of this task.
10. **Using `make agent-plugin`.** See the description: it moves the pin for every package. Build in-process at `2.5.3`.

### Requirements addressed

8.1–8.13, 9.1–9.8, 10.7, 13.6, 13.9; **1.10's and 2.9's bundled-validator clauses**, through gate 1 in the command below (review 6 **R6-B-1**)

### Acceptance criteria

- [ ] Under option A, the module's `PACKAGES` list prints three names, the third being the new package.
- [ ] `python3 -c "import json;d=json.load(open('agent-plugin/cao-agent-plugin-lifecycle/plugin.json'));print(sorted(d))"` shows `$schema` and `name` present and every key within the vendored schema's property set.
- [ ] The manifest `name` matches `^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$` and is 1–64 characters, asserted by a regex check rather than by eye.
- [ ] `find agent-plugin/cao-agent-plugin-lifecycle -type f | sort` lists `plugin.json`, `.claude-plugin/plugin.json`, `README.md`, `CHANGELOG.md`, `LICENSE`, and both skills' `SKILL.md` under `skills/`.
- [ ] `diff -r skills/cao-agent-plugin-audit agent-plugin/cao-agent-plugin-lifecycle/skills/cao-agent-plugin-audit` reports no differences, and likewise for the creator skill — the byte-identity the drift guard enforces.
- [ ] `uv run python scripts/build_agent_plugin.py --check` exits **0**, and its output names the version it built at, equal to the version the two pre-existing packages carry.
- [ ] `git diff --quiet HEAD -- agent-plugin/cao agent-plugin/cao-contributor` exits 0 under option A — the existing packages untouched, pin included.
- [ ] `CAO_AGENT_PLUGINS_ENABLED=1 uv run cao plugin validate ./agent-plugin/cao-agent-plugin-lifecycle` exits **0** and names both new skills.
- [ ] The same with `--json` reports `"loadable": true` and `"findings": []`.
- [ ] `env -u CAO_AGENT_PLUGINS_ENABLED uv run cao plugin validate ./agent-plugin/cao-agent-plugin-lifecycle` exits **1** and emits no parseable JSON — recorded as the gate-off demonstration, not a package defect.
- [ ] `CAO_AGENT_PLUGINS_ENABLED=1 uv run cao plugin validate ./test/agent_plugins/fixtures/corpus/manifest-missing-name` exits **1** — the negative control.
- [ ] **Every two-package site in `test_packages.py` covers the new package** (Requirement 8.11): the parametrisations at `:42`, `:50`, `:54`, `:67`, `:83`, `:312` include its directory; `:216-219` includes its `(config, package_dir)` pair; the disjointness check at `:223-225` covers all three allowlists pairwise; the `--check` assertion at `:227-234` names all three packages; and `test_both_packages_install_side_by_side` (`:326-340`) installs all three and asserts a three-name set. Line numbers are as of `27311798` and move as you edit; check the sites by name. Verified by reading the diff, because each site passes without the edit.
- [ ] **The package was built in-process at `2.5.3`, not with `make agent-plugin`.** `python3 -c "import json;print({json.load(open(f'agent-plugin/{n}/plugin.json'))['version'] for n in ('cao','cao-contributor','cao-agent-plugin-lifecycle')})"` prints `{'2.5.3'}`, and `uv run python -c "import sys;sys.path.insert(0,'scripts');import build_agent_plugin as b;print(b.committed_package_version())"` prints `2.5.3`, not `None`.
- [ ] Neither the pull-request text nor any document this task touches claims the package is "dogfooded in CI" (Requirement 8.12).
- [ ] `uv run python scripts/vendor_agent_plugins_schemas.py --check` exits 0, and `git diff --quiet HEAD -- src/cli_agent_orchestrator/schemas/` exits 0.
- [ ] **The boundedness disagreement fixture writes all three manifests.** In `test/test_agent_plugin_pin_boundedness.py`, `test_packages_disagreeing_is_unknowable` writes a `plugin.json` for **every** `PackageConfig` in `bap.PACKAGES` — today `cao`, `cao-contributor` and `cao-agent-plugin-lifecycle` — taking the names from `bap.PACKAGES` rather than a literal list, with at least two versions differing, and still asserts `committed_package_version() is None`. Verified by reading the diff: the test passes without this edit.
- [ ] `uv run pytest -q -p no:cacheprovider test/agent_plugins/ test/test_agent_plugin_pin_boundedness.py --no-cov` exits 0.
- [ ] Scope, per hazard 4 (wave 2): hazard 4's **start block**, run with `-s t5` before any work, prints `stamp taken: /tmp/cao-apl-t5.stamp`; hazard 4's **end block**, run with `-s t5` when the work is done, prints `scope OK: t5` and exits 0. A missing stamp makes the end block exit **2**; an out-of-scope write, a deleted tracked file or a deleted untracked file makes it exit **1**; a gitignored write only prints a warning. **Candidates come from git, not from a tree walk, and not from a `git status` line diff:** a tree walk ignores `.gitignore` and trips on the gates' own `__pycache__`, and a status-line diff cannot see an edit to an already-untracked file. `find` is used only to test each git-listed candidate against the stamp.

**Command that must pass:**
```bash
bash -euo pipefail <<'EOF'
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
uv run python scripts/build_agent_plugin.py --check
CAO_AGENT_PLUGINS_ENABLED=1 uv run cao plugin validate ./agent-plugin/cao-agent-plugin-lifecycle
uv run python scripts/vendor_agent_plugins_schemas.py --check
uv run pytest -q -p no:cacheprovider test/agent_plugins/ test/test_agent_plugin_pin_boundedness.py --no-cov
# Gate 1, verbatim from design.md's runnable-forms block: every skill in skills/
# passes the bundled validator, including both new ones. Exit 0 required.
uv run --script skills/cao-agent-plugin-audit/scripts/validate_agent_plugin.py --skills-dir skills/
# The same validator in package mode, against the new package. Exit 0 required.
uv run --script skills/cao-agent-plugin-audit/scripts/validate_agent_plugin.py ./agent-plugin/cao-agent-plugin-lifecycle
EOF
```

---

## T6 — Audit the package with its own skill, then record the outcome and the lesson

**Status:** [ ] Not started — **OQ-1a** decided; merge gated on **OQ-1b**
**Owner:** `oss-docs`
**Owns:** `docs/issues/1153-agent-plugin-lifecycle/audit-report.md` **and** `docs/issues/1153-agent-plugin-lifecycle/audit-raw.txt` (the captured audit output, which the report must quote)

### Description

**This task exists because the first revision had no task behind the dogfood claim, and no task covering a charter deliverable.** A grep for `learning|fleet|smoke` across all three specification documents returned nothing (`review-1.md` **F-5**).

Two steps.

**Step 1 — audit the package with a skill it ships.** Run `Audit_Skill` against `agent-plugin/cao-agent-plugin-lifecycle` and record its findings in `audit-report.md`: each finding with its severity, the five mechanical checks and their results, and the manifest verdict from `cao plugin validate --json`. This is what makes the dogfood claim demonstrated rather than described. Note the claim's **exact** shape: the package is **audited by** a skill it carries, not "produced by" it — it is produced by `build_agent_plugin.py` (Requirement 8.1, 8.10).

**Step 2 — record the outcome and the lesson**, per `cao-learning`. This fleet records outcomes in the **`workflow_outcomes`** table, not `outcomes`; it held zero rows table-wide when this work began and now holds four for workflow `agent-plugin-lifecycle-spec` (`P-64`, the supervisor's rows). Call `report_outcome` for this task, and store a lesson whose final clause is `Applies when: <trigger>` — that clause **is** the index by which a later session finds it. Store conclusions only, never transcripts or file contents.

**How to read `audit-raw.txt`.** The command block's audit step runs with `CAO_AGENT_PLUGINS_ENABLED` **unset**, so the skill's own optional wrapper around `cao plugin validate` prints `cao plugin validate: not run`. **That line does not mean a check is missing.** CAO's verdict is taken separately, by the block's step 2, which sets the gate and writes `/tmp/manifest-verdict.json`. The two are reported separately on purpose (OQ-4, option C), and the report must say so wherever it quotes the raw output.

The **install smoke test** is `TestPackagesInstallThroughTheRealPipeline` at `test/agent_plugins/test_packages.py:345` since T5 (`:309` at `27311798`, `P-77`), already in gate 7; cite it rather than writing a new one. The **fleet story** belongs to `blog-outline.md`; point at it.

### Likely defects to watch for

1. **Writing the report before running the skill.** The report's value is that a skill produced it. A hand-written conformance summary that looks like audit output is the exact failure this task exists to prevent, and nothing downstream can tell the difference.
2. **Recording a lesson without `Applies when:`.** Without that clause the lesson is unfindable, and an unfindable lesson is not a lesson.
3. **Storing a transcript as the lesson.** Conclusions only. Transcripts are long, go stale, and leak whatever was on screen.
4. **Writing to `outcomes`.** The table is `workflow_outcomes`. A query against the wrong name returns nothing and looks like "learning is disabled".
5. **Claiming the four existing outcome rows.** They are the **supervisor's** `report_outcome` calls from terminal `9feec10a` (`P-64`). This task adds its own; it does not inherit theirs.
6. **Reporting a clean audit as proof the skill works.** A skill that finds nothing on a package built from its own canonical sources has demonstrated very little. The meaningful check is that it **flags a deliberately broken fixture** — which is T3's over-limit package, so cite T3's result alongside the clean run.
7. **Softening the result.** If `Audit_Skill` finds a real defect in the `Dogfood_Package`, the finding goes in the report and T5 gets a follow-up. An audit that cannot fail is not an audit.

### Requirements addressed

8.10, 2.4, 2.11, 11.7; charter requirements for `cao-learning`, the install smoke test, and the fleet story.

### Acceptance criteria

- [ ] `audit-report.md` exists at `docs/issues/1153-agent-plugin-lifecycle/audit-report.md` and records, for `agent-plugin/cao-agent-plugin-lifecycle`: the result of each of the five mechanical checks, every finding with its severity, and the `--json` manifest verdict with its exit status.
- [ ] The report states the command that produced it, verbatim, with its exit status.
- [ ] `skills/cao-agent-plugin-audit/scripts/validate_agent_plugin.py` **exists** before the audit is invoked. **The reason, corrected after review 5:** a quoted real path is never read as a redirect. Only a literal angle-bracket placeholder left in a copied command is, because the shell parses `<name>` as an input redirect (`review-1.md:211`, `review-2.md:46`). A missing script is now also caught by step 1's exit-contract check (`test "$AUDIT_EXIT" -le 1`), because `uv run --script` on a missing path exits above 1. The existence check is kept because it fails first, with a message that names the cause.
- [ ] `docs/issues/1153-agent-plugin-lifecycle/audit-raw.txt` exists and is non-empty — the audit skill's output **as captured**, not retyped.
- [ ] The report **quotes `audit-raw.txt` verbatim**: with blank lines stripped, **each** of its first five output lines appears in `audit-report.md`, checked **one line at a time in a loop**. `grep -qF -f` is **not** sufficient — it succeeds when a *single* pattern matches, so it cannot enforce "all five". Blank lines must be stripped first, because `grep -F` reads an empty pattern as matching anything. Both holes would let a hand-written report pass, which is T6's own defect 1.
- [ ] The report records the audit's **exit status**, so a clean run and a run with findings are distinguishable from the artifact alone. An audit exit of **1** (findings) is **not** a failure of this task; discarding it is. Any status **above 1** means the audit did not run to completion (T2's exit contract) and **is** a failure.
- [ ] The report cites **T3's** over-limit result as the evidence that the skill can fail, alongside the clean run on the `Dogfood_Package`.
- [ ] The report says the package is **audited by** a skill it carries and does **not** say "produced by".
- [ ] `report_outcome` is called for this task, and the row it creates is identified **by its own returned id** — `SELECT id, task_label, agent_profile FROM workflow_outcomes WHERE id = '<the id report_outcome returned>'` returns exactly one row whose `task_label` names this task. **A count-based check is forbidden here:** "more rows than the four" passes whenever *anyone* reports an outcome under that `workflow_name`, including the supervisor on a later turn, which makes the evidence that motivated the criterion into a gate that cannot fail (`review-2.md` **B-2**). Filtering by this task's terminal id is an acceptable alternative; a bare count is not.
- [ ] A lesson is stored whose text ends with `Applies when: <trigger>`, containing conclusions only — no transcript, no file contents, no secrets.
- [ ] The report cites `TestPackagesInstallThroughTheRealPipeline` as the install smoke test, at `test/agent_plugins/test_packages.py:345` since T5 (`:309` at `27311798`, `P-77`), and does not introduce a second one.
- [ ] The report points at `blog-outline.md` for the fleet story rather than restating it.
- [ ] Scope, per hazard 4 (wave 3): hazard 4's **start block**, run with `-s t6` before any work, prints `stamp taken: /tmp/cao-apl-t6.stamp`; hazard 4's **end block**, run with `-s t6` when the work is done, prints `scope OK: t6` and exits 0. A missing stamp makes the end block exit **2**; an out-of-scope write, a deleted tracked file or a deleted untracked file makes it exit **1**; a gitignored write only prints a warning. T3 and T6 carry these two blocks filled in; run those copies. **Candidates come from git, not from a tree walk, and not from a `git status` line diff:** a tree walk ignores `.gitignore` and trips on the gates' own `__pycache__`, and a status-line diff cannot see an edit to an already-untracked file. `find` is used only to test each git-listed candidate against the stamp.

**Before you start — creates the stamp and snapshot the scope check needs.** Run this before step 1; the scope check below refuses to run without it:
```bash
bash -euo pipefail -s t6 <<'EOF'
case "$1" in t[1-7]) ;; *) echo "unknown task: $1" >&2; exit 2 ;; esac
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
g() { git -c core.quotePath=false "$@"; }   # print non-ASCII paths raw, not C-quoted
STAMP="/tmp/cao-apl-$1.stamp"
touch "$STAMP"
{ g ls-files -o --exclude-standard; g diff --cached --name-only; } \
  | LC_ALL=C sort -u > "$STAMP.untracked"
echo "stamp taken: $STAMP"
EOF
```

**Command that must pass:**
```bash
bash -euo pipefail <<'EOF'
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
RAW=docs/issues/1153-agent-plugin-lifecycle/audit-raw.txt
REPORT=docs/issues/1153-agent-plugin-lifecycle/audit-report.md
SCRIPT=skills/cao-agent-plugin-audit/scripts/validate_agent_plugin.py

# 0. The script must EXIST. Step 1's exit-contract check would also catch a missing
#    script; this check fails first and names the cause.
test -f "$SCRIPT" || { echo "MISSING $SCRIPT: T2 has not landed" >&2; exit 1; }

# 1. Run the audit skill's own check and CAPTURE it. A real finding is allowed, so the
#    exit status is RECORDED, not required to be 0, and it is not discarded either.
#    Under pipefail the pipeline reports the audit's own status whenever tee succeeds,
#    so no PIPESTATUS (bash) / pipestatus (zsh) lookup is needed.
set +e
uv run --quiet --script "$SCRIPT" ./agent-plugin/cao-agent-plugin-lifecycle 2>&1 | tee "$RAW"
AUDIT_EXIT=$?
set -e
echo "audit exit=$AUDIT_EXIT"
test -s "$RAW"
# T2's exit contract: 0 clean, 1 findings, anything else = the audit never completed.
# --quiet keeps uv's own progress lines out of audit-raw.txt, so the report quotes the
# audit and not the installer.
test "$AUDIT_EXIT" -le 1 || { echo "audit did not complete: exit $AUDIT_EXIT" >&2; exit 1; }

# 2. The manifest verdict is a DIFFERENT check, not a substitute for step 1.
set +e
CAO_AGENT_PLUGINS_ENABLED=1 uv run cao plugin validate ./agent-plugin/cao-agent-plugin-lifecycle --json \
  > /tmp/manifest-verdict.json
VALIDATE_EXIT=$?
set -e
echo "validate exit=$VALIDATE_EXIT"

# 3. The report must quote the captured output verbatim: EVERY line, not any one of
#    them. `grep -qF -f` succeeds when a SINGLE pattern matches, so it cannot enforce
#    "all five". Blank and whitespace-only lines are skipped because `grep -F` reads an
#    empty pattern as "match anything". awk, not `grep | head`: under pipefail, head
#    closing the pipe early can SIGPIPE the writer and fail a correct run.
awk 'NF { print; if (++n == 5) exit }' "$RAW" > /tmp/cao-apl-t6-pattern.txt
test -s /tmp/cao-apl-t6-pattern.txt
while IFS= read -r l; do
  grep -qF -- "$l" "$REPORT" || { echo "missing from report: $l"; exit 1; }
done < /tmp/cao-apl-t6-pattern.txt

# 4. And the report must record the audit's exit status, so a clean run and a run with
#    findings are distinguishable from the artifact alone.
grep -qF "audit exit=$AUDIT_EXIT" "$REPORT"
EOF
```

**Scope check that must pass** — hazard 4's end block with `t6`; exits 0 and prints `scope OK: t6`:
```bash
bash -euo pipefail -s t6 <<'EOF'
TASK="$1"
case "$TASK" in
  t1|t2|t3) WAVE_PATHS='^(skills/cao-agent-plugin-creator/|skills/cao-agent-plugin-audit/|docs/issues/1153-agent-plugin-lifecycle/t3-overlimit-experiment\.md$)' ;;
  t4|t5)    WAVE_PATHS='^(scripts/sync_skills\.py$|src/cli_agent_orchestrator/skills/|scripts/build_agent_plugin\.py$|test/agent_plugins/test_packages\.py$|test/test_agent_plugin_pin_boundedness\.py$|agent-plugin/cao-agent-plugin-lifecycle/)' ;;
  t6)       WAVE_PATHS='^docs/issues/1153-agent-plugin-lifecycle/audit-(report\.md|raw\.txt)$' ;;
  t7)       WAVE_PATHS='^(CODEBASE\.md$|docs/skills\.md$|docs/agent-plugins\.md$)' ;;
  *) echo "unknown task: $TASK" >&2; exit 2 ;;
esac
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
g() { git -c core.quotePath=false "$@"; }   # print non-ASCII paths raw, not C-quoted
STAMP="/tmp/cao-apl-$TASK.stamp"
# A missing stamp must fail LOUDLY. It must never let the check pass.
test -f "$STAMP" || { echo "MISSING STAMP $STAMP: run the start block first" >&2; exit 2; }
test -f "$STAMP.untracked" || { echo "MISSING SNAPSHOT $STAMP.untracked: run the start block first" >&2; exit 2; }
# grep -v exits 1 when it selects nothing, which here means success; 2 is a real error.
keep_out() { grep -vE "$WAVE_PATHS" || [ $? -eq 1 ]; }
present() { { g ls-files -o --exclude-standard; g diff --cached --name-only; } | LC_ALL=C sort -u; }

# 1. Writes since the stamp: modified, staged, and untracked-but-not-ignored paths.
#    find -prune -newer checks the path itself (a symlink is not followed) and
#    errors on a missing stamp; the `|| exit 2` carries that error out of the loop.
#    A path git still prints quoted (it contains `"`, `\` or a control character)
#    cannot be tested, so it is reported rather than skipped: fail closed.
WRITES=$(
  { g ls-files -m; g diff --cached --name-only; g ls-files -o --exclude-standard; } \
    | LC_ALL=C sort -u \
    | while IFS= read -r f; do
        if [ "${f#\"}" != "$f" ]; then printf '%s\n' "$f"; continue; fi   # no `case` here: bash 3.2 cannot parse `pat)` inside $( )
        [ -e "$f" ] || [ -L "$f" ] || continue     # gone: covered by checks 2 and 3
        find "$f" -prune -newer "$STAMP" -print || exit 2
      done \
    | keep_out
)
# 2. Deleted tracked files: unstaged (ls-files -d) and staged, which covers `git rm`
#    and the old path of a `git mv` (--no-renames reports a rename as D plus A).
DELETED=$(
  { g ls-files -d; g diff --cached --no-renames --name-only --diff-filter=D; } \
    | LC_ALL=C sort -u | keep_out
)
# 3. Deleted untracked files: present at the stamp, absent now.
GONE=$(present | LC_ALL=C comm -23 "$STAMP.untracked" - | keep_out)
# 4. Gitignored paths written since the stamp: a WARNING, never a failure. A find
#    error here (an unreadable directory, say) is reported and does not change
#    the exit status.
IGNORED=$(
  g ls-files -o -i --exclude-standard --directory \
    | while IFS= read -r f; do
        find "$f" -newer "$STAMP" -print 2>/dev/null \
          || echo "WARNING (not a failure): check 4 could not read all of $f" >&2
      done \
    | keep_out
)
if [ -n "$IGNORED" ]; then
  echo "WARNING (not a failure): gitignored paths written since the stamp:" >&2
  printf '%s\n' "$IGNORED" | sed -n '1,20p' >&2
fi

FAIL=0
if [ -n "$WRITES" ];  then printf '%s\n' "$WRITES"  | sed 's/^/OUT-OF-SCOPE WRITE: /';     FAIL=1; fi
if [ -n "$DELETED" ]; then printf '%s\n' "$DELETED" | sed 's/^/OUT-OF-SCOPE DELETION: /';  FAIL=1; fi
if [ -n "$GONE" ];    then printf '%s\n' "$GONE"    | sed 's/^/UNTRACKED FILE DELETED: /'; FAIL=1; fi
if [ "$FAIL" -eq 0 ]; then echo "scope OK: $TASK"; fi
exit "$FAIL"
EOF
```

---

## T7 — Documentation obligations

**Status:** [ ] Not started — **OQ-1a decided**; merge gated on **OQ-1b**. Needs T5's package name
**Owner:** `oss-docs`
**Owns:** `CODEBASE.md`, `docs/skills.md`, `docs/agent-plugins.md`

### Description

Update the three canonical documents the repository's maintenance rule points at. That rule, `CODEBASE.md:141-160`, requires that "any change to public commands, providers, profile fields, API route families, or Markdown headings must update the relevant canonical document and every affected link in the same change", and that local paths and fragments be validated before merging.

- **`CODEBASE.md`** — the `agent-plugin/` row enumerates the packages by name; under option A it must name the third. Requirement 8.5, 10.1.
- **`docs/skills.md`** — describe both new skills. Its builtin-seeding table is introduced by "CAO ships with built-in skills **including**:", so it is explicitly non-exhaustive and already omits most shipped skills; adding rows is still right, because the document is canonical for the subject.
- **`docs/agent-plugins.md`** — "CAO's own packages" at `:485`, and "Verified by dog-fooding" at `:669`, where T6's evidence belongs.

### Likely defects to watch for

1. **Writing an unqualified "plugin".** These two documents are where a reader is most likely to conflate CAO's two plugin systems. Requirement 10.5 now specifies a **regex** check rather than "verified by reading each occurrence", which was a judgement call masquerading as a criterion (`review-1.md` **N-3**).
2. **Stating that M1 is settled.** `573/design.md:4` says decided; `docs/agent-plugins.md:82-88` says not. The repository disagrees with itself and this change does not resolve it. Requirements 10.6, 13.5.
3. **Fixing the split severity table while in `docs/agent-plugins.md`.** Its `warning` and `info` rows sit orphaned at `:304-305`, separated from `fatal` and `skipped` at `:246-247` by an inserted paragraph. Real, **pre-existing**, and out of scope by Requirement 13.9.
4. **Making shipped documentation cite `research.md`.** Requirement 10.8 was scoped after review: the obligation to cite `research.md` applies to **this specification directory only**. A shipped page citing a spec-phase research note would be wrong and untestable.
5. **Counting things.** No line counts, file counts or test counts. Name what exists; do not tally it.
6. **Adding a `docusaurus/sidebars.ts` entry.** Not needed — the blog is routed automatically and `docusaurus/docs/` is a separate curated tree, not a mirror of `docs/`.
7. **Breaking a fragment link.** `docs/issues/` is **not** excluded from the link validator, so the specification documents are checked too, fragments included.

### Requirements addressed

10.1–10.8, 8.5, 13.5, 13.9

### Acceptance criteria

- [ ] Under option A: the `agent-plugin/` row in `CODEBASE.md` names all three packages, and the new name matches T5's manifest `name` exactly — compared by extracting both strings, not by eye.
- [ ] `grep -c 'cao-agent-plugin-creator\|cao-agent-plugin-audit' docs/skills.md` prints ≥ `2`.
- [ ] `docs/agent-plugins.md` mentions both new skills in "CAO's own packages", and its "Verified by dog-fooding" section cites a command with its exit status rather than a prose assurance.
- [ ] `uv run python scripts/validate_markdown_links.py` exits **0**.
- [ ] **No unqualified "plugin" is added** (Requirement 10.5). The check block below exits 0 for T7's commit. It applies the repository's own phrase-level rule, `_UNQUALIFIED_PLUGIN` (`test/agent_plugins/test_naming_migration.py:74`), read from that file so it cannot drift. It uses the stripping `_prose_of` performs (`:60-70`), counts **occurrences** in every Markdown file the commit changes, and fails on any occurrence the parent commit did not have. **This replaces a per-token whitespace check** that could never accept "agent plugin" with a space (`P-78`). The check fails closed: an edited line that already held an unqualified occurrence is reported as new, and a reviewer judges it.
- [ ] No new claim that M1 is settled appears in any of the three files.
- [ ] `git diff --quiet HEAD -- docusaurus/sidebars.ts` exits 0.
- [ ] The orphaned severity rows at `docs/agent-plugins.md:304-305` are unchanged — that hunk does not appear in `git diff`.
- [ ] No file changed by this task introduces a count of lines, files, tests or commits.
- [ ] Scope, per hazard 4 (wave 4): hazard 4's **start block**, run with `-s t7` before any work, prints `stamp taken: /tmp/cao-apl-t7.stamp`; hazard 4's **end block**, run with `-s t7` when the work is done, prints `scope OK: t7` and exits 0. A missing stamp makes the end block exit **2**; an out-of-scope write, a deleted tracked file or a deleted untracked file makes it exit **1**; a gitignored write only prints a warning. **Candidates come from git, not from a tree walk, and not from a `git status` line diff:** a tree walk ignores `.gitignore` and trips on the gates' own `__pycache__`, and a status-line diff cannot see an edit to an already-untracked file. `find` is used only to test each git-listed candidate against the stamp.

**Unqualified-"plugin" check that must pass** — pass the commit to check, T7's own commit once it exists:

```bash
bash -euo pipefail -s a2953880 <<'EOF'
C="${1:?pass the commit whose Markdown changes to check}"
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
git cat-file -e "$C^{commit}" || { echo "not a commit: $C" >&2; exit 2; }
uv run --quiet python - "$C" <<'PY'
import ast, re, subprocess, sys
from collections import Counter
c = sys.argv[1]
# The rule is read from the repository's own guard, so this check cannot drift from it.
guard = "test/agent_plugins/test_naming_migration.py"
pattern = None
for node in ast.walk(ast.parse(open(guard, encoding="utf-8").read())):
    if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "_UNQUALIFIED_PLUGIN" for t in node.targets):
        call = node.value
        if not (len(call.args) == 2 and getattr(call.args[1], "attr", "") in ("I", "IGNORECASE")):
            sys.exit(f"{guard}: _UNQUALIFIED_PLUGIN is no longer re.compile(pattern, re.I); re-read it")
        pattern = call.args[0].value
if pattern is None:
    sys.exit(f"{guard}: _UNQUALIFIED_PLUGIN not found")
rule = re.compile(pattern, re.I)
def show(rev, path):
    r = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""
def offences(text):
    # _prose_of's stripping, applied to the WHOLE text in its order (fenced code, then
    # inline code, then links), because an inline code span or a link can wrap across
    # a line break. Each removed span keeps its newlines, so hits stay on their own
    # line and can be reported. Occurrences are counted, not lines.
    keep = lambda m: "\n" * m.group(0).count("\n")
    text = re.sub(r"```.*?```", keep, text, flags=re.S)
    text = re.sub(r"`[^`]*`", keep, text)
    text = re.sub(r"\[[^\]]*\]\([^)]*\)", keep, text)
    found = Counter()
    for line in text.splitlines():
        n = len(rule.findall(line))
        if n:
            found[line.strip()] += n
    return found
files = subprocess.run(["git", "diff", "--name-only", f"{c}^", c, "--", "*.md"],
                       capture_output=True, text=True, check=True).stdout.split()
bad = 0
for f in files:
    for line, n in (offences(show(c, f)) - offences(show(f"{c}^", f))).items():
        bad += n
        print(f"UNQUALIFIED plugin x{n} in {f}: {line}")
print(f"Markdown files changed by {c}: {' '.join(files) or '(none)'}; new unqualified occurrences: {bad}")
sys.exit(1 if bad else 0)
PY
EOF
```

**Command that must pass:**
```bash
bash -euo pipefail <<'EOF'
TOP=$(git rev-parse --show-toplevel) || exit 2; cd "$TOP"
uv run python scripts/validate_markdown_links.py
git diff --quiet HEAD -- docusaurus/sidebars.ts
# Red from T5 until this task documents both skills (hazard 1); must pass now.
uv run pytest -q -p no:cacheprovider test/test_agent_plugins_docs.py --no-cov
EOF
```

---

## T8 — Independent review

**Status:** [ ] Not started
**Owner:** two independent **read-only reviewer seats** — `oss-review` on axis 1, a second seat on axis 2 (profile chosen by the supervisor)
**Owns:** **nothing.** Cannot write files or run commands; returns findings inline.

### Description

Two independent reviews of T1–T7, neither sharing an implementer's context.

**Axis 1**, `oss-review`: correctness, security, **evidence honesty** and **test honesty** — does any document assert more than its cited evidence supports? **Axis 2**, a second independent seat: **logic and spec conformance** — does each artifact satisfy the criteria it claims, and does each criterion test what it says? The axes are split across **two seats rather than two passes by one seat**, because a second pass shares the first's context and the independence is the point.

The highest-value question is narrow: **does `Audit_Skill` mechanically check the name regex, the 1024-character description bound and the 500-line body bound — or does it wrap `cao plugin validate` and inherit its blind spot?** If the latter, the feature has no evidenced justification and T2 must be redone. Everything else is secondary.

### Likely defects to watch for

1. **Accepting a green gate as proof of the above.** Every gate can pass while `Audit_Skill` checks nothing new. No gate tests the superset relation; only reading the skill does.
2. **Treating an exit-1 from an unset gate as a finding.** Check that the artifacts discriminate by **JSON parseability**, not exit status — and do not make the same conflation while reviewing.
3. **Reviewing `blog-outline.md`, `research.md` or `review-1.md` as in scope.** All belong to other seats; findings go back as routing notes.
4. **Asking a read-only seat to fix what it finds.** It cannot write. A finding returns as a new task against the owning seat.
5. **Running a command.** These seats have no execution tools. A criterion requiring one is misassigned — the first revision gave T8 a `git log` check, which `review-1.md` **N-14** flagged; verification of tree state now belongs to the supervisor.

### Requirements addressed

Verifies all; specifically 2.3, 2.4, 2.11 (the superset relation), 11.7, 11.8, and properties P2, P5, P6.

### Acceptance criteria

- [ ] A written finding on whether `Audit_Skill` mechanically checks the name regex, the 1024-character bound and the 500-line bound — each confirmed by **quoting the skill**, not by citing a passing gate.
- [ ] A written finding on whether any artifact claims CAO rejects an over-limit skill as observed fact, given `P-6` is OBSERVED for the two length limits (T3) and inferred for the name regex and the 64-character bound.
- [ ] A written finding on whether any artifact claims no prior art audits an Agent Plugin, which Requirement 2.11 forbids.
- [ ] A written finding on whether any artifact describes a trigger-eval score as activation, or states one without naming its directory.
- [ ] A written finding on whether any document uses an unqualified "plugin".
- [ ] A written finding on whether `requirements.md`'s D4 section rests on **exactly two** grounds, with the not-shipped point as context under ground 1 rather than as a third ground.
- [ ] A verdict of `APPROVE` or `CHANGES NEEDED`, pinned to the exact tree reviewed.
- [ ] **Tree-state verification is the supervisor's, not T8's**: that `git log --oneline -1` still reports the expected HEAD and `git status --porcelain --untracked-files=all` lists only intended paths. **Requirement 13.8's block is the supervisor's pre-push gate:** it must exit 0 over `upstream/main..HEAD` before anything is pushed. T8 cannot run any of these.

**Command that must pass:** none — these seats run no commands. The verdict is the deliverable.

---

## Out of scope

| Item | Owned by |
|---|---|
| Fixing `run_trigger_evals.py`'s crash on list-shaped eval files | Requirement 13.1, **OQ-5**. Pre-existing; gating per-skill avoids it |
| Removing the unused `httpx` PEP 723 dependency | Requirement 13.2 |
| Generalising `harness-oss/tools/validate-plugin.py` | Requirement 13.3. A different repository, no `upstream` remote, and it cannot be aimed at a CAO package |
| #573 **M4** — renaming `cao-plugin` to `cao-event-plugin` | Requirement 13.4, **OQ-3** |
| #573 **M1** — the self-disagreement between `573/design.md:4` and `docs/agent-plugins.md:82-88` | Requirement 13.5 |
| ~~The stale #448 comments~~ — **already fixed by #1121** (`P-52`): `build_agent_plugin.py:39` and `:179` now describe #448 as merged | Moot. Retained so a reader of an earlier revision does not hunt a defect that no longer exists |
| The split severity table at `docs/agent-plugins.md:246-247` / `:304-305` | Requirement 13.9. Pre-existing; raise separately |
| Retiring or editing the installed `cao-skill-creator` / `cao-skill-audit` | Requirement 6.4. Not this repository's artifacts; provenance unknown |
| `SKILL_RENAMES` in `cli/commands/init.py` | Requirement 6.3. Nothing is renamed |
| Any `pyproject.toml` change | Requirement 7.5. Adding a `skills/**` artifacts entry would fail CI |
| A **lasting** test for the superset relation | Accepted gap, `design.md § Testing strategy` item 1. T3 runs in a temp directory; Requirement 8.11's install-test extension is the only permanent coverage this feature adds |
| `--keep-committed-pin` for the builder | Sibling issue **#1152** |
| The `agent-plugins-dogfood` CI job, its `run.sh` and its demo GIF | **Answered: `run.sh` covers only `agent-plugin/cao`** (`P-67`). Extending it to the third package is an **open user question**, recorded, not added. Until it is decided, Requirement 8.12 limits the claim to "gated in CI by `make check-agent-plugin`" |
| `blog-outline.md`, `research.md`, `review-1.md` | Other seats. Requirement 13.7 |
| **Any push** | **OQ-16** is decided: the implementation phase **commits** (signed, exactly two trailers) and **never pushes**. The push and the draft pull request are the supervisor's, after the user's approval (Requirement 13.8) |
