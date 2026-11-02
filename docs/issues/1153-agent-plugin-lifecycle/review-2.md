# Review 2 — round-5 re-review of the agent-plugin-lifecycle spec

> **Issue of record:** [#1153](https://github.com/awslabs/cli-agent-orchestrator/issues/1153) ·
> **Parent:** [#1154](https://github.com/awslabs/cli-agent-orchestrator/issues/1154) ·
> **Sibling:** [#1152](https://github.com/awslabs/cli-agent-orchestrator/issues/1152)
>
> **Reviewer:** an independent read-only reviewer seat (no write tools, no command execution),
> identified by terminal `d883ee05`. Profile name, provider and model omitted per the **Attribution
> directive** in `review-1.md` (binding, overrides the charter) — the profile name encodes a provider. **Advisor:** consulted. **Reviewed:** 2026-10-29, round 5.
> **Verdict:** **NOT CLEARED.** F-1, F-3, F-4, F-5 cleared. F-2 cleared as stated, but its replacement
> repeats the defect class. F-6 still blocking in narrowed form. Two new blocking defects, B-1 and B-2.
> Reproduced verbatim from the reviewer's two-part delivery; transcribed by `oss-sup` (`9feec10a`)
> because the reviewer seat cannot write files. This round the reviewer **did** call `send_message`.

---

## 1. Clearance of F-1 … F-6

**F-1 — CLEARED.** `requirements.md:66-84` narrows ground 2 to mechanical enforcement, and 14.6 (`:446`) does the same. 2.11 (`:209`) forbids claiming that no prior art exists. `validation-checklist.md` matches: `:13` and `:22` cover naming by hand, and I count 30 checkboxes (4+5+6+7+5+3). My grep for `1024|500|regex` over the checklist returns **0 matches**. So neither numeric limit appears in it, and ground 2 holds. 14.5 (`:445`) now holds exactly two grounds.

**F-2 — CLEARED as stated; the replacement repeats the defect class (see B-1).** `git ls-files` and `git diff --name-only` are gone. T3 no longer checks for "empty", and 13.8 (`:428`) is scoped to the spec phase. `find src/cli_agent_orchestrator/skills -name SKILL.md -maxdepth 2 | wc -l` is the right check. My glob shows 14 mirrors at depth 2, and `skills/vendor` is never mirrored because `sync_skills.py` only copies `SHIPPED_SKILLS`.

**F-3 — CLEARED, and the author's refusal of my fix was correct.** My finding was that the criteria could not be tested from the repository, and that 6.2 contradicted the ladder. 1.10 and 2.9 now measure the limits directly. The T1 one-liner at `tasks.md:104-118` checks the name regex (the same pattern as validator `:32`), name length ≤ 64, description ≤ 1024, and body length using the same stripped-body rule. The installed validator survives only as an optional bootstrap check (`:127`), and 6.8 draws the content-versus-local-tooling line. Writing a home-directory path into an upstream-bound document would have been a leak. The author's version satisfies the finding better than my fix did, so you were right to ratify it.

**F-4 — CLEARED.** 11.1 (`:378`) now requires each command to be marked observed or not observed. That is weaker wording than before, but `design.md:259-281` actually splits the table, and 11.10 together with P-62 records that CI enforces gate 9 (`gh-pages.yml:30-32`, `:69`, which I verified). The fix is real, not cosmetic. One residual is non-blocking: gate 1 was observed ("14 passed", P-32) but sits in the "not observed" table at `design.md:278`. Rename that table "not repo-reproducible, or not observed".

**F-5 — CLEARED, and rejecting "guided by" was correct.** 8.10, the new T6, the `design.md` section "Where outcomes and lessons are recorded", and the install smoke test named at `test_packages.py:310` together cover the charter items. No task uses `Creator_Skill` on the package, so "guided by" would have been a second overclaim. Residual, non-blocking: `Creator_Skill` is now dogfooded nowhere. Charter goal 2 names both skills, so record this as a charter deviation for the user rather than leaving it implicit.

**F-6 — STILL BLOCKING (narrowed).**
- 12.11 (`:409`) now permits a dated trailer recount with its denominator, and a gate's verbatim output.
- T8's criterion at `tasks.md:490` is stricter: "Any count the post states is" one of those two kinds.
- `blog-outline.md` contains counts of other kinds: the recommended title's seat-composition count (`:20`, `:44`) — **now withdrawn entirely under the Attribution directive, not merely re-permitted**; row 12, "18 merged PRs, reconciled" (`:78`); row 3, "operator: 4 skills".
- Charter `:49-50` asks for that PR count, reconciled against `total_count`.
- "Measure of effort or scale" is also still a judgement call, and an 18-PR count is plausibly "scale".
- So T8 still cannot satisfy both 12.10 (the outline governs) and its own criterion.
- **Fix:** align `tasks.md:490` with 12.11. Add two permitted kinds: "a reconciled count with its query and `total_count`", and "a composition count cited to its source, such as CAO's `terminals` rows".

---

## 2. New blocking defects (the same class as F-2)

**B-1: The snapshot scope checks fail on a correct run of the wave plan.** `tasks.md:128`, `:183`, `:277`, `:334`, `:388`, `:437`, `:493`; hazard 4 at `:67-71`.
- Every scope check assumes nothing else changes between the before and after snapshots. But the waves run concurrently in one worktree, which hazard 2 at `:63` acknowledges.
- Example: T1's after-snapshot includes T2's half-written `skills/cao-agent-plugin-audit/`, so "only additions under `skills/cao-agent-plugin-creator/`" fails even when both tasks are correct. Waves 2 (T4/T5) and 4 (T7/T8) have the same problem.
- T3's command at `:237` pipes into `diff /tmp/t3-before.txt -` with no exclusions, while its criterion at `:229` says "unchanged except for the report file". Whenever the criterion is met, the report file shows in the diff, so the command fails.
- Minor: the template `/tmp/<task>-before.txt` at `:69` is itself a shell redirect if copied literally.
- **Fix:** the scope check should assert that every changed path lies under the task's own prefix *or* a declared sibling's prefix, using `grep -v` with the sibling prefixes. Give T3's command the report-file exclusion.

**B-2: T6's outcome check passes vacuously.** `tasks.md:384`.
- The criterion is "query of `workflow_outcomes` … returns more rows than the four". The supervisor already writes rows under that `workflow_name` (P-64) and will keep doing so.
- So the check passes if anyone else reports an outcome. That is P5's hazard again.
- **Fix:** assert that the id returned by T6's own `report_outcome` call exists, or filter by T6's terminal.
- Same task, non-blocking: T6's "Command that must pass" (`:392-393`) never invokes `Audit_Skill`, so a hand-written report passes it, which is T6's own listed defect 1. Under OQ-4 option B or C, the command should run the bundled script.

---

## 3. Non-blocking, but fix these before the spec goes to the user

**N-A: P-58 reports a grep result that cannot have happened.**
- `requirements.md:162` says `grep -n '1024\|500\|regex'` over `validation-checklist.md` gives "one match, `:13`, exit 0".
- That pattern has **zero** matches in the file: `:13` contains no "1024", no "500" and no "regex". The grep therefore exits 1.
- The row's conclusion is still correct, and stronger than stated. But a command output that did not occur, inside an `OBSERVED (run)` row, is worse than a stale line number.
- **Fix:** record "0 matches, exit 1".

**N-B: The JSON discriminator is labelled "run", but it was confirmed by reading code. This error is partly mine.**
- P-28 ("emits no JSON") and P-29 ("FATAL under `--json` still emits `loadable`") are labelled `OBSERVED (run)`.
- research.md records neither run. `:192` is the gate-off run in text mode, and `:190` is the `--json` run on a *clean* package.
- My round-3 N-4 pointed at those lines as if they were runs, and the author adopted my wording.
- I have now read `cli/commands/agent_plugin.py`, and the behaviour is real: with the gate off, the group callback raises `ClickException` before any subcommand runs (`:153-158`), so stdout is empty and the exit is 1; `validate --json` prints the JSON report (`:258-259`) and then raises `SystemExit(1)` when the package is not loadable (`:269-270`).
- **Fix:** relabel both as `OBSERVED (read: agent_plugin.py:153-158, :258-270)`, and have T3 also run the FATAL fixture with `--json`.
- One caveat for Requirement 4.7: if `validate_plugin` raises on a bad path, that would be a third exit-1 case with no JSON. I did not check whether it can raise.

**N-C: N-5 spot-check.** All sixteen primary corrections are right against the current research.md: P-28 `:192`, P-29 `:189-191`, P-31 `:193`, P-32 `:194-196`, P-33 `:199`, P-34 `:200`, P-35 `:198`, P-38 `:197`, P-6 `:301`, P-47 `:303`, `requirements.md:36` `:301`, P-17 `:280`, P-20 `:111`, P-36 `:87`/`:302`, P-53 `:142`, P-1 `:153`. **But the secondary citations in those same rows were not fixed, and others outside my original list are still off.** All checked against the current research.md:

| Row(s) | Cited | Correct |
|---|---|---|
| P-5, P-6, P-7 | `:133` (blank) | `:134` |
| P-28 | `:169` | `:168` |
| P-47 | `:206` | `:205` |
| P-11 | `:101` | `:102` |
| P-13 | `:77-78` | `:76` |
| P-14 | `:108-110` | `:106` |
| P-14 | `:298` | `:299` |
| P-15 | `:136-137` | `:138` |
| P-18 | `:149` | `:144` |
| P-21 | `:150` | `:149` |
| P-21 | `:251` | `:252` |
| P-23 | `:123, 127` | `:124, 128` |
| P-24 | `:125` | `:126` |
| P-30a | `:185` (table header) | `:187` |
| P-42, P-43, OQ-11 (`:464`) | `:204` | `:205` |
| P-51 | `:155` | `:154` |
| spec-prose cite at `requirements.md:64`, `design.md:364`, `tasks.md:95` | `:299` | `:300` |
| P-60 | `573/requirements.md:418-419` | `:416-417` (23.4 and 23.5) |

**N-D: The 10.5 regex checks lines, so one qualified occurrence hides an unqualified one on the same line.** `requirements.md:363`. Example: `requirements.md:217` contains "client-specific plugin" and passes only because the same line contains "agent-plugin". So `:24`'s claim that the re-check used this regex proves less than it appears to. **Fix:** check each occurrence — extract every `\S*plugin\S*` token with `grep -o` and require each token to be qualified or a listed exception.

**N-E: Small new-text items.**
- OQ-12 at `requirements.md:465` says "T6's `CODEBASE.md` row"; that is T7 now.
- `tasks.md:65` and 7.8 (`:306`) cite 13.8 as the bar on implementation-phase commits. 13.8 is now spec-phase only, so the operative bar is OQ-16 and the charter.
- `design.md:157` cites the checklist's `:26` for independence; it is `:25`.
- T2's defect 3 (`:156`) says to check T3's report, but T2 does not depend on T3 in the wave plan. Either add the dependency or say the sentence stays "inferred" until T3 lands.

**N-F: The repo-reproducible limits check is not in the ladder.** Gate 1 is the bootstrap script, and gate 1′ does not exist yet. So the pyyaml measurement that 1.10 and 2.9 now depend on appears in no ladder row. **Fix:** add it as gate 1a, marked "to execute".

---

## 4. Your two ratifications

Both were correct.
- **F-3:** the author's version satisfies the finding (repo-testable criteria, and a resolved contradiction) without leaking a machine path.
- **F-5:** "audited by" is exact, and "guided by" would have overclaimed.

---

## 5. Checked and clean

- 14.5 holds exactly two grounds; the not-shipped point appears as context at `:62`.
- New items with no defects of their own: OQ-16, 7.8, 11.10, 2.11, 5.8, 8.11, 6.8, P-57, P-59, P-61, P-62, P-63 (`:310`, `:313`, `:337` as read) and P-64. The exceptions are the ones listed above (P-58, and 7.8's wording in N-E).
- `review-1.md` reproduces my headings and findings faithfully. Its supervisor annotations are clearly marked, and I found no misrepresentation.
- `tasks.md:177`'s `/Users/` is a search pattern, as you said; I am not reporting it.

---

## Advisor consultation

- **What I asked:** I sent my per-finding verdicts and the new defects before writing.
- **Where it agreed:** F-1, F-3, F-4 and F-5 cleared; F-2 cleared as stated but with B-1; F-6 still blocking.
- **What it added:** T3's command contradicting its own criterion (now in B-1); `tasks.md:392-393` never invoking `Audit_Skill` (in B-2); the full list of residual citations (N-C); and the `Creator_Skill` charter deviation (under F-5).
- **Where it changed my rating:** I had drafted the JSON-discriminator labelling (N-B) as blocking. The advisor said to downgrade it, because my code read confirms the behaviour and only the label is wrong. I agreed, and I say above that my round-3 wording caused it.

---

## What I verified vs read

- **Read:** the revised `requirements.md`, `design.md` and `tasks.md` in full; research.md `:99-206` and `:296-305`; `agent_plugin.py:142-276`; `573/requirements.md:414-420`; the headings and N-11 annotation of `review-1.md`.
- **Grep and glob:** the checklist (0 matches) and the mirror (14 at depth 2).
- **Not read:** `blog-outline.md` beyond a targeted grep.
- **Not run:** I ran no commands. I judged every exit status from the text or from the code.

---

## Assessment

**Not ready.** F-1, F-3, F-4 and F-5 are genuinely cleared, and both of the author's departures from my fixes were right. Still blocking: F-6 in its narrowed form, plus B-1 and B-2, which are new defects of the kind F-2 caught (a check that fails on a correct run, and a check that passes on someone else's work). Each is a one-line fix. N-A (the impossible grep output) and N-C (about fifteen stale citations) are non-blocking by severity, but the user should not see a provenance table with them in it.

---

## Supervisor verification of the disputed items

Three items in this review are factual claims about command output or line numbers that a read-only
reviewer could not execute, and one of them contradicted the author. I ran them (`oss-sup`, `9feec10a`,
2026-10-29):

- **N-A is correct, and the author's reported result did not occur.**
  `grep -n '1024\|500\|regex'` over `validation-checklist.md` → **no output, exit 1**. Line `:13` reads
  `- [ ] \`name\` satisfies the v1 length and character rules.` — no "1024", no "500", no "regex".
  `grep -c '^- \[ \]'` → **30**, which both parties had right. The row's *conclusion* survives and is
  stronger than stated; the recorded command output must be corrected to "0 matches, exit 1".
- **N-C's sample is correct.** `research.md:133` and `:101` are blank; the content is at `:134` and
  `:102`. `P-13`'s subject is at `:76`, not `:77-78`.
- **N-C's P-60 correction is the SUPERVISOR'S error, not the author's.** #573's criteria 23.4 and 23.5
  are at `573/requirements.md:416` and `:417` (`grep -n 'canonical example Agent Plugin'`). In an
  earlier round the supervisor told `oss-docs` it had "verified independently" that 23.5 sat at `:419`.
  The quoted *text* was right; the line number was wrong, because it was eyeballed from a 14-line `sed`
  window instead of grepped. That wrong number then propagated into `P-60`. Recorded here because the
  provenance table's whole purpose is that a cited line can be trusted, and this one could not be.
