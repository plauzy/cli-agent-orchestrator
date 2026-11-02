<!-- Recorded by the supervisor from the axis-2 reviewer's callback (terminal a453276e, 2026-11-01 ~16:00 -06:00).
     Condensed; the supervisor authored none of the findings. Untracked; not part of the PR. -->

# T8 axis 2 (logic and spec conformance): pinned to a2953880

**Verdict: CHANGES NEEDED — T8B-B-1 only.** The reviewer notes its advisor rated B-1 non-blocking; if weighed so, the verdict is APPROVE with N-1..N-9.

**Priority question: MECHANICAL, not a wrapper.** `validate_agent_plugin.py:68-71` (constants), `:272` (body lines), `:275-284` (folder, regex, 64, 1024, 500), reached in both modes (`:309`, `:387`); CAO's validator is optional and additive (`:318-349`). Audit SKILL.md `:3`, `:28-29`, `:63-79`; rules.md `:74-77`.

**Per-criterion:** C1 yes · C2 no artifact claims CAO rejects; reverse overreach → B-1 · C3 no "no prior art" claim · C4 no trigger-eval score · C5 no new unqualified prose in T7 (README.md:12 inherited template text → N-6) · C6 exactly two D4 grounds (`requirements.md:62-98`, context at `:76`) · C7 pinned · C8 supervisor's.

**Per-task:** T1 conforms · T2 conforms except B-1 · T4 conforms by reading · T5 conforms (all 8.11 sites, boundedness from `bap.PACKAGES`) · T7 conforms.

## Blocking

**T8B-B-1 [T2 → T4, T5].** Requirement 2.7's second clause is unmet. Audit SKILL.md `:31-36` cites T3 for the two length limits, but `:47-49` ("It loads it") and `:192` ("LIMIT … CAO loads it anyway") state admission as fact for all four LIMIT codes, including the name pattern and the 64 bound, which T3 did not test and 2.7 requires marked inferred. The criterion at `tasks.md:299` passes vacuously on the word "inferred" at `:31`. Fix: a sentence after `:36` marking the name-pattern and 64-character behaviour inferred from `models/skill.py`; qualify `:192`; re-sync the mirror and rebuild the package in-process at 2.5.3.

## Non-blocking

- **N-1 [T2]** SKILL.md `:10-11` "no artifact CAO ships enforces them" becomes false once this skill ships; say "no other artifact".
- **N-2 [T1]** creator `evals.json:74-79` asserts the unset gate is the cause of exit 1 with no JSON; contradicts audit SKILL.md `:122-124` and 4.8.
- **N-3 [T1]** creator `evals.json:68` contains the literal `skills/cao-skill-creator/`; no guard scans evals; conflicts with 6.7's wording.
- **N-4 [T2]** the 2.12 listing prints loaded skills only (`:309-311`, `:369`); body `:203-205` says "discovered". Body `:203` says "always" emitted; code and rules.md emit only when a manifest was read; fix the body.
- **N-5 [T2]** missing/wrong `$schema` yields two FATALs (`:193-196` plus `:215-216`); description measured after `.strip()` (`:270`) vs T1's raw value.
- **N-6 [builder template]** 10.5 "any document it touches": T5's generated README.md is never checked; README `:12` "every plugin you install" and `:36-37` MCP posture text are inherited template (`build_agent_plugin.py:663`), not T5 regressions.
- **N-7 [T5]** stale "two packages" wording: `build_agent_plugin.py:353`, `test_packages.py:5`, class `TestBothPackagesAreConformant` `:42`.
- **N-8 [T4 criterion]** `tasks.md:512` bare `diff -r` would report a gitignored `__pycache__/*.pyc` in the mirror; add `-x __pycache__`.
- **N-9 [T2, inferred]** comment `:154-156` on jsonschema remote retrieval should be checked against the pinned version; bundled schemas use only local refs.

Advisor: agreed on the priority answer and that nothing else blocks; asked for the evals-guard and symbol checks (N-3; all four symbols exist); raised N-6, the plugin.json ruling and the 2.7 gap (which it rated non-blocking).
