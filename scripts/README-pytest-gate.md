# Pre-push pytest gate

## The problem

The pre-push hook required a fully green Python suite:

```sh
uv run --project .. pytest ../test -m "not e2e" -q --disable-warnings || exit 1
```

As of 2026-08-19, `main` itself fails **71 tests** from a clean checkout — 57 of them in
AG-UI (`test/services/agui/*`, `test/api/test_agui_*`), plus 5 in
`test/services/test_kiro_engine_phase0.py` and 3 in `test/telemetry/test_otel_init.py`.

Verified by checking out `upstream/main` (`0b02db7a`) into a detached worktree and running the
same files: the failures reproduce with no local changes at all.

So the gate was **unpassable from a clean checkout**. Every push required `--no-verify`.

That is worse than having no gate. A gate nobody can pass does not measure quality — it trains
contributors to bypass it reflexively, which disables it for the regressions it *would* have
caught. The hook was silently doing nothing except costing 5m42s per push.

## The change

Gate on **regressions**, not on absolute green. `scripts/pytest-regression-gate.sh` compares
the current failure set against `test/known-failures.txt` and fails only on test IDs that are
newly broken.

- **New failure** → push blocked, offending IDs listed.
- **Known failure** → push proceeds, count reported.
- **Baseline failure now passing** → reported as a hint to refresh; never blocks.

This preserves the hook's actual purpose (catch what *this branch* broke) while remaining
passable on a red trunk.

## Refreshing the baseline

Run on a clean checkout of the target branch:

```sh
./scripts/pytest-regression-gate.sh --update-baseline
```

Commit the resulting `test/known-failures.txt`. Shrinking that file is the measure of progress
on the pre-existing failures; it should never grow without a deliberate, reviewed reason.

## Scope

This PR does **not** fix the 71 failures. It makes the gate honest about them so they are
visible and countable rather than hidden behind a reflex `--no-verify`. Fixing the AG-UI suite
is separate work.
