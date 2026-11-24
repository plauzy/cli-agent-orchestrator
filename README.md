# Evidence for awslabs/cli-agent-orchestrator#1463

Real runs of the deterministic race tests, rendered as a styled terminal page in Playwright Chromium. Each test ran in 20 fresh Python processes per tree (`python -m pytest <node id> -q --no-cov -p no:cacheprovider`, temp HOME, isolated CAO_HOME_DIR). The video plays the captured output line by line; the runs themselves took several minutes on a loaded machine.

Trees: `main` = `git archive` of upstream/main `6234f1f5` plus the PR's new test file; `commit 1 only` = `3314952f` plus the new test file; `both` = PR head `962714f2`.

| File | Shows |
|---|---|
| `pr1463/pr1463-race.webm`, `pr1463-race.gif` | all four scenes |
| `pr1463-01.png` | create-side test on main: 20 / 20 failed, "a same-name teardown ran between the create's lock release and its registration" |
| `pr1463-02.png` | create-side test on 962714f2: 0 / 20 failed |
| `pr1463-03.png` | delete-side test on commit 1 only (3314952f): 20 / 20 failed, "a single-terminal delete ran between the create's row write and its registration" |
| `pr1463-04.png` | delete-side test on 962714f2: 0 / 20 failed |
| `raw/*.txt` | the unedited per-run logs |

Not recorded here: the "main + commit 2 only" row of the PR's four-way table.
