# Fixture provenance

The committed `fixtures/` bundle is the evidence the static docsite dojo renders.
Because GitHub Pages serves the docsite with **no backend**, this bundle must be
committed so the public dojo renders in replay mode.

## Current state

- `capture_mode: synthetic-deterministic` — the committed bundle was **seeded**
  by hand to the exact schema emitted by
  [`ag-ui-meta-dogfood/capture.py`](../ag-ui-meta-dogfood/capture.py) and the
  L2 projections, so the dojo renders immediately.
- Running [`capture.py`](capture.py) in a CAO dev environment
  (`CAO_AGUI_ENABLED=1 uv run …`) **regenerates and overwrites** the bundle from
  the real production AG-UI path and flips `capture_mode` to `production-path`.

## Regeneration is the intended workflow (dog-food)

The honest, frontier-team workflow is to regenerate the bundle from a real
orchestration rather than hand-maintain it:

```sh
CAO_AGUI_ENABLED=1 uv run python examples/ag-ui/ag-ui-dojo/capture.py
uv run pytest test/services/agui/test_dojo_fixtures.py -q   # gate must stay green
```

For the maintainers-meeting demo, run `capture.py` against a **live** multi-provider
fleet (real `kiro_cli` supervisor + `claude_code`/`codex` workers) and commit the
resulting bundle with `capture_mode: production-path` and this file updated to
name the run.
