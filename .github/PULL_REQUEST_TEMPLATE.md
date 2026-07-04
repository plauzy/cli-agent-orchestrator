## Why (answer before "what")

> From [docs/TENETS.md §2](docs/TENETS.md): every PR description answers these four questions before the summary of changes.

1. **What outcome are we trying to change?**
   <!-- Be specific. "Improve X" is not an outcome; "reduce manual smoke verification from 20 min → 30 s per release" is. -->

2. **What would have to be true** for that outcome to look different than today?
   <!-- Preconditions: what must hold before the change is useful? -->

3. **What is the smallest change that makes those things true?**
   <!-- Justify scope: why not more, why not less? -->

4. **How will we know it worked?**
   <!-- Quantifiable. A metric, a before/after measurement, a test that was previously failing and now passes. -->

---

## Summary of changes

<!-- Bullet-point summary. What files changed and why. -->

## Test plan

<!-- How was this tested? Link to CI run, test output, or manual steps. -->

- [ ] Unit / integration tests pass (`uv run pytest -m "not e2e"`)
- [ ] e2e smoke passes (`uv run pytest -m e2e test/e2e/test_websocket_auth.py -v --no-cov`)
- [ ] `mypy` strict passes (`uv run mypy src/`)
- [ ] `black` + `isort` clean (`uv run black src/ test/ && uv run isort src/ test/`)

## Provider tier

<!-- Per docs/TENETS.md §1 — pick one and justify. -->

- [ ] Tier 1 — unit/integration, no provider boot needed
- [ ] Tier 2 — mock_cli, runs in CI on every PR (no secrets)
- [ ] Tier 3 — real provider, nightly/workflow_dispatch only
