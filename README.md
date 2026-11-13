# Evidence for awslabs/cli-agent-orchestrator#1314

Pinned to commit 667ccfc5a13d3cb8770155a2802a454a7bfa35e9 (draft PR, stacked on #1312).

- Head 667ccfc5a13d3cb8770155a2802a454a7bfa35e9 replaces 136533a6227e5bf64c462d44dc7105f32fed66c6: the only change is how `L16_KEYS` and `L16_NUMERIC_KEYS` are written in `examples/ag-ui/cao-dojo/tools/trace_leaks.py` (one key per line), because gitleaks 8.30.1 flagged the one-line form as a false positive (`generic-api-key`). `pA2-gitleaks-red.txt` is the finding on the old head and `pA2-gitleaks-green.txt` is no leaks on the new one, same flags as the CI step. Targeted trace_leaks tests, black, isort and ruff were re-run on that file.
- The gates, red/green and e2e files below were run on 136533a6227e5bf64c462d44dc7105f32fed66c6. Only that one file changed since, and no UI file.
- The clip and stills (`pA2/host-strip-real.*`, `pA2/fleet-panel-real.png`) were recorded from a9159c79's tree. That commit was later rebased onto #1312's amended head and given review fixes, and no UI file changed in between. The e2e was re-run on 136533a6227e5bf64c462d44dc7105f32fed66c6 (`pA2/pA2-e2e-run-clean.txt`).
- They come from a private mock_cli cao-server (throwaway HOME, own tmux socket), not a live fleet.
- `pA2-commands.txt`, `pA2-red-base.txt`, `pA2-green-head.txt`: same pytest command on #1312's head and the pre-fix commit.
- `pA2-red-vitest.txt`, `pA2-green-vitest.txt`, `pA2-coverage-*.txt`: dashboard tests and the 100% coverage floor.
- `pA2-gates-clean.txt`: gates in a clean detached worktree at 136533a6227e5bf64c462d44dc7105f32fed66c6.
- `pA2-macos-local-evidence.txt`: loose local macOS comparison with sysctl and top.
- The three Linux-only tests (loadavg, meminfo, busy-children) did not run locally; CI runs them.
