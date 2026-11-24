# Evidence for awslabs/cli-agent-orchestrator#1459

Real runs of the decision-home guard probes (`test/decisions/test_decision_home_probe.py`, `CAO_TEST_DECISION_HOME_PROBE=1`, environment as in `test_decision_home_guard_xdist.py`), rendered as a styled terminal page in Playwright Chromium. Temp HOME per run.

Trees (`git archive`): before = `053ea862` (earlier PR revision; `06ee7ac3` for the lost-worker scene), after = PR head `adb58dfa`, which is on `main` `6234f1f5`. The probe file from the head was copied into the before trees.

| File | Shows |
|---|---|
| `pr1459/pr1459-guard.webm`, `pr1459-guard.gif` | all three scenes |
| `pr1459-01.png` | probe A: serial rc=1 before; `-n 2` rc=0 and no message before (silent pass); `-n 2` rc=1 after, "Decision state changed under startup CAO home: decisions.halt (pytest-xdist worker gw1)" |
| `pr1459-02.png` | `-p no:xdist` on test/test_must_run_gate.py: before rc=3 PluginValidationError, after 27 passed |
| `pr1459-03.png` | a plugin that `os._exit(1)`s each worker in sessionfinish, `-n 2 --max-worker-restart=0`: before rc=0 silent, after rc=1 "only 0 of 2 pytest-xdist worker(s) reported" |
| `raw/*.txt` | exit code and matched lines of each run |
