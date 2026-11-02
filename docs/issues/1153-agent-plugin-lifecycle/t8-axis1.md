<!-- Recorded by the supervisor from the axis-1 reviewer's callback (terminal 54b9cef2, 2026-11-01 ~16:02 -06:00).
     Condensed; the supervisor authored none of the findings. Untracked; not part of the PR. -->

# T8 axis 1 (correctness, security, evidence and test honesty): pinned to a2953880

**Verdict: CHANGES NEEDED — T8A-B-1 only.**

**Priority question: the skill checks the limits itself.** `validate_agent_plugin.py:68-71`, `:272`, `:278-285`, both modes (`:289`, `:376`); `run_cao_validate` (`:318`) is additive. SKILL.md `:66-70`, `:72-80`, `:84-97`. Manifest name regex and bound come from running the vendored schema (`:157`, `:181ff`).

**Per-criterion:** C1 met · C2 no rejection claim; name-pattern upgraded to observed → B-1 (CAO checks only non-blank name/description `models/skill.py:12-19` and folder=name `utils/skills.py:66-69`; `validate_skill_name` is not on the package path) · C3 no "no prior art" claim (related N-3) · C4 none · C5 T7 prose clean; flagged-but-unambiguous: creator `:13`, audit `:3`, inherited README line · C6 met (`:62`, `:64`, `:82`, context `:76`) · C7 pinned · C8 supervisor's.

## Blocking

**T8A-B-1 [T2 → T4, T5].** Audit SKILL.md `:28-33` treats "those limits", including the name pattern, as observed; the evidence (`:33-45`) covers only the two length limits (`t3-overlimit-experiment.md:11`; `design.md:247`). Violates 2.7's SHALL. Fix: a sentence after `:37` saying T3 did not test the name pattern or the 64 bound and that admission is read from `models/skill.py` and `utils/skills.py`, not observed.

## Non-blocking

- **N-1 [T2]** package-mode discovery does not mirror CAO: no SKILL.md containment check (`:306`, `:253`; CAO `validation.py:655-669`), no nested-link walk (CAO `:707-711`); with the gate set CAO findings only count on an info line (`:347-349`), so a CAO-SKIPPED skill gives audit exit 0, contradicting `rules.md:54`. Also reads files through out-of-root symlinks. Fix: containment check, or a WARNING when CAO's findings are non-empty.
- **N-2 [T2, T5 manifest]** "needs … no network" overclaims (SKILL.md `:3`, `build_agent_plugin.py:194`, generated manifests/README); `uv run --script` resolves deps on a cold cache (inferred). Fix: "opens no network connection itself; first run needs its two dependencies available".
- **N-3 [T2, spec 2.3]** SKILL.md `:10-11` "no artifact CAO ships" is false once shipped; match `:29`. Also "three" limits vs four "no" rows (`:72-80`).
- **N-4 [T2, security]** remote retrieval not explicitly refused (`:157` comment); mirror CAO's `_refuse_retrieval` (`validation.py:155-166`, `:187`). Schemas use only local refs, so no practical fetch.
- **N-5 [T2, security]** subprocess (`:332-338`): add `timeout=`, pass `str(root.resolve())`; parse the same bytes that were hashed; no test or CI step runs the script — add a pytest comparing `PINNED_SHA256` (via ast) to PIN.json.
- **N-6 [T7]** `docs/agent-plugins.md:719-721` "must report" reads as an enforced gate and omits "skipped"; say it was reported at the commit that added the package and is not run in CI.
- **N-7 [T5]** `ALL_PACKAGE_DIRS` (`test_packages.py:35`) and `configs` (`:257`) are literal lists not tied to `builder.PACKAGES`; add one assertion. Stale "Both packages" (`build_agent_plugin.py:352`), `test_packages.py:5`, class `TestBothPackagesAreConformant`.
- **N-8 [T5, optional]** add a positive control to the boundedness fixture (all equal → "2.5.0").
- **N-9 [T1]** creator SKILL.md `:187` snippet uses `split("---", 2)`, no strip, and a KeyError exits 1 like a breach.
- **N-10 [supervisor / PR text]** STATUS `:146-153` calls the tmux-dependent seven "pre-existing upstream" on evidence at 5b1dbc81, which is inside the PR; needs a run at 27311798 or a narrower wording.

Not checkable read-only: any run, byte identity of the three copies, wheel contents, jsonschema registry behaviour.
