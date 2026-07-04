# CAO v2.5 Runbooks

Operator runbooks for the v2.5 capabilities. One section per piece of long-running infrastructure that an operator (not a developer) needs to drive.

> **Audience:** humans operating a deployed CAO instance — clearing kill switches, rotating keys, recalibrating thresholds, pruning stranded resources.

---

## Phase 1 — Agent Card signing key rotation

**Background.** Phase 1 publishes a JWS-signed Agent Card on `:9890`. The signing key lives at `~/.aws/cli-agent-orchestrator/agent_card/key.ed25519` and is auto-generated on first boot. The public half is published at `:9890/.well-known/jwks.json` so A2A peers can verify card signatures.

**When to rotate.**

- Suspected key compromise.
- Periodic rotation per your security policy (recommended: annually).
- After running CAO in a CI/staging environment with a key that should not be reused in production.

**Procedure.**

1. Stop the CAO server: `cao shutdown` (or your process supervisor's `stop`).
2. Move the existing key file to a backup location:
   ```
   mv ~/.aws/cli-agent-orchestrator/agent_card/key.ed25519 \
      ~/.aws/cli-agent-orchestrator/agent_card/key.ed25519.rotated-$(date +%Y%m%d)
   ```
3. Restart CAO. The lifespan auto-generates a fresh key on first call.
4. Verify the new public key is published:
   ```
   curl -sS http://localhost:9890/.well-known/jwks.json | jq .keys[0].kid
   ```
5. Notify any A2A peers that have pinned the old `kid` so they refresh.

**Notes.**

- Rotation is not zero-downtime. A2A peers verifying against the old `kid` will reject signatures until they re-fetch JWKS.
- The rotated key file is kept on disk for forensic auditing — delete only after retention requirements are met.

---

## Phase 1 — Polecat git-worktree GC

**Background.** Phase 3 Polecats run inside isolated git worktrees rooted at `~/.aws/cli-agent-orchestrator/worktrees/polecat-{id}`. The lifespan removes them on graceful shutdown, but a CAO crash, OOM kill, or `kill -9` leaves the worktree behind. Stranded worktrees consume disk and clutter `git worktree list` output.

**Procedure.**

1. Run from inside the parent repo:
   ```
   git worktree prune
   ```
   This removes worktrees whose backing directory is gone.
2. List remaining worktrees and identify CAO-owned ones (path contains `polecat-`):
   ```
   git worktree list
   ```
3. For each stranded CAO worktree:
   ```
   git worktree remove --force <path>
   ```
4. Verify the parent repo is clean:
   ```
   git status
   ```

**Automation.** A periodic cron / systemd-timer running `git worktree prune` against each repo CAO operates against will keep the list bounded automatically. The CAO lifespan also calls `git worktree prune` on startup, so a graceful restart cleans up after a prior crash.

---

## Phase 4 — Deacon kill-switch operations

**Background.** When the Deacon detects sustained ASI degradation (Rath 2026 framework — see [`docs/v2-5-architecture.md`](v2-5-architecture.md) §"Phase 4"), `KillSwitchHandler` flips a per-task-class flag that `dispatch_task` consults. New work for that class is refused until the operator clears the switch.

**Inspect the current state.**

```
curl -sS http://localhost:9889/asi/kill-switch | jq
```

Returns `{"killed": [...], "available": true}` — the list of currently kill-switched task classes. If `available: false`, the Deacon is disabled (`CAO_ASI_DISABLED=true`).

**Clear a specific class.**

```
curl -sS -X POST 'http://localhost:9889/asi/kill-switch/clear?task_class=research_breadth' | jq
```

**Clear all classes.**

```
curl -sS -X POST http://localhost:9889/asi/kill-switch/clear | jq
```

**Procedure on a kill-switch event.**

1. Identify the class that fired. The Deacon emits a `severity=kill` log line at `CRITICAL` level via `LoggingHandler` and an `asi.mitigation` SSE event on `:9889/events`.
2. Investigate the upstream cause:
   - Recent provider/agent changes (config, model swap, tool change)?
   - Sustained API errors against the dependency?
   - Operator-induced misconfiguration?
3. Once the underlying issue is fixed, clear the switch with the API above.
4. Watch the Deacon for a `severity=recover` event indicating the rolling ASI is back above the `mitigate` threshold. The kill switch auto-clears on `severity=recover` so manual clearing is only needed when the operator wants to resume dispatch before the Deacon agrees.

---

## Phase 4 — ASI threshold recalibration

**Background.** Default thresholds (`warn=0.85`, `mitigate=0.75`, `kill=0.60`, `consecutive=3`) follow the Rath (2026) paper. Real CAO deployments have different task mixes, provider performance characteristics, and tolerance for false positives. The v2.5 plan calls these out as "calibration parameters — tune over the first month of operation."

**Calibration procedure.**

1. Run CAO for at least 2 weeks with the defaults under representative load.
2. Pull the WAL audit trail:
   ```
   ls -lh ~/.aws/cli-agent-orchestrator/wal/
   ```
   Each `asi.mitigation` record shows the score, dimensions, and severity.
3. Compute the false-positive rate: how many `mitigate` / `kill` events fired during periods that, in retrospect, were normal operation?
4. Adjust thresholds:
   - **Too many false positives** → lower the threshold values (more lenient: `mitigate=0.65`, `kill=0.50`)
   - **Genuine drift slipped through** → raise the threshold values (more sensitive)
   - **Rapid flapping warn → recover → warn** → increase `consecutive_windows_required`
5. Restart CAO with the new thresholds applied (currently a code change in `observability/asi_evaluator.py`; a config-file path is a v2.6 candidate).

**Recommended reporting cadence.** Log the false-positive rate + missed-drift rate weekly during the first month of operation. By month two, the rates should stabilize and thresholds shouldn't need further tuning.

---

## Phase 5 — Cache health monitoring

**Background.** The three-layer cache (PR #5 + PR #6 lifespan integration) is opt-out via `CAO_CACHE_DISABLED=true`. Operators should monitor hit rate and L2 keep-alive registry size to validate the cache is paying for itself.

**Inspect.**

```
curl -sS http://localhost:9889/cache/stats | jq
```

Returns:
- `cache.l1_hits` / `cache.l3_hits` / `cache.misses` / `cache.hit_rate_percent` — overall hit-rate health
- `cache.total_lookups` — request volume
- `l2.tracked` — number of prefixes the keep-alive scheduler is refreshing
- `l2.total_pings` / `l2.total_errors` — L2 health (errors > 0 may indicate the registered `KeepAlivePinger` is failing)

**Acceptance benchmarks.**

- **Hit rate > 30%** after warm-up (1 hour of typical load) → cache is paying for itself.
- **L2 errors / total_pings < 1%** → keep-alive is hitting the Anthropic API cleanly.
- **L1 evictions << total_lookups** → cache size is adequately bounded.

If hit rate stays low, profile the caller pattern: are envelopes deterministic? Different supervisor IDs, timestamps, or other ephemeral fields will cause cache-key fragmentation. Use `cache_key()` directly to verify two ostensibly identical requests hash the same.

**Reset.** The cache is best-effort and stateless from CAO's perspective — restart CAO to clear L1; remove `~/.aws/cli-agent-orchestrator/db/cao-cache.db` to clear L3.

---

## Phase 5 — A2A / ACP transport health

**Background.** External A2A peers + ACP hosts (Cursor 3 / Zed Parallel Agents / Claude Code) talk to CAO over the v2.5 transport surfaces. When something goes wrong, the failure surfaces are different per protocol.

**A2A — task lifecycle.**

```
# Single task lookup (REST polling fallback)
curl -sS http://localhost:9890/a2a/v1/tasks/{taskId} | jq

# SSE stream of state transitions
curl -sS http://localhost:9890/a2a/v1/stream/{taskId}
```

If a task is stuck in `submitted` (peer expects `working` then terminal), check whether a `TaskExecutor` is wired on the router. Without one, tasks stay in `submitted` indefinitely (PR #5 + PR #6 contract).

**ACP — server log.**

The `cao-acp` console script logs to stderr by default. Hosts should capture stderr for diagnostics. Common failures:

- `ALREADY_INITIALIZED` on the second `initialize` — host bug (must reuse the existing connection rather than re-handshaking).
- `NOT_INITIALIZED` on every method except `initialize` — host hasn't completed handshake.
- `SESSION_NOT_FOUND` on `session/prompt` — host is using a session id from a different connection (sessions are per-connection in CAO's stdio impl).

---

## v2.5 — A/B testing patterns

**Background.** Three v2.5 close-out items change behavior visible to dispatch outcomes: real swarm collector aggregation, behavioral anchoring, and the cache-aware budget oracle. CAO's A/B testing follows four patterns documented here. The same patterns apply to any future behavior change; do **not** add a second feature-flag system.

**Pattern A — held-out improvement benchmark.**
Build a fixed task suite (≥ 50 deterministic shapes), run control vs. treatment, assert improvement above a stated floor. The canonical statistical test is a **paired bootstrap CI on the per-task delta** (1000 resamples; reject if 95% CI excludes zero). A naïve t-test is acceptable for ≥ 50 tasks but bootstrap is preferred. Mark such tests `slow` so they don't gate every CI run.

Examples in-tree:
- `test/benchmarks/test_swarm_correctness.py` — exact equality on a deterministic test set (no statistics; correctness equivalence).
- `test/benchmarks/test_anchoring_recovery.py` — paired bootstrap CI on ASI-score recovery delta.
- `test/benchmarks/test_cache_aware_router.py` — paired bootstrap CI on per-task cost reduction.
- `test/benchmarks/test_topology_improvement.py` — the original Phase 3 template.

**Pattern B — shadow-mode evaluation.**
Wrap the new code path behind a `CAO_<feature>_SHADOW=true` env var. The system runs both old and new paths, returns the old result, and emits OTel spans tagged `cao.shadow.{feature}.match` / `.diverged`. Operators run shadow mode for **at least one week** in production before flipping the default.

In-tree shadow flags:
- `CAO_ANCHORING_SHADOW=true` — behavioral anchoring (Block B.4).
- `CAO_CACHE_BUDGET_SHADOW=true` — cache-aware budget oracle (Block C.8).

**Pattern C — bucketed online experiment.**
For features that aren't deterministically scoreable (e.g. anchoring), assign a stable variant per task via the bucket primitive at `src/cli_agent_orchestrator/observability/experiments.py:bucket(task_id, salt)`. Document a 50/50 split keyed by `task_id`. Variant assignment is recorded on the existing `cao.dispatch` span via attribute `cao.experiment.variant`; per-variant aggregation comes via the WAL `asi.mitigation` records (no new schema).

**Statistical-significance guidance for online experiments:** prefer **sequential testing** (mSPRT or fixed-horizon Bonferroni) over p-value peeking. Operators wait for the configured horizon (default: one week) before declaring a winner. **Do not peek and stop early.**

**Pattern D — kill-switch as auto-rollback.**
The Phase 4 kill switch already auto-rolls back drifted variants. When the treatment variant's ASI crosses the kill threshold for its task class, `KillSwitchHandler` flips the per-class flag and `dispatch_task` refuses new dispatches with `KillSwitchEngaged`. This is **already wired** — A/B experiments ride on the existing infrastructure, no new flag system needed. Pinned by `test/observability/test_mitigations.py::TestAutoRollback`.

**What NOT to do.**
- Don't ship a behavior change without at least Pattern A behind it.
- Don't gate merge on online experiments. Online experiments run after merge under shadow mode and graduate to default-on after the runbook horizon.
- Don't introduce a second feature-flag system. Reuse env vars + `app.state` (the same mechanism Phase 1 / 4 / 5 use).
- Don't peek at online-experiment results before the horizon expires.

---

## v2.5 — Cedar policy cut-over

**Background.** v2.5 ships a Cedar adapter + parallel-evaluation harness for the Refinery write gate (see `docs/cedar-migration.md`). YAML remains authoritative until an operator opts in via `CAO_REFINERY_ENGINE`.

**Default state.** `CAO_REFINERY_ENGINE` is unset → YAML authoritative. No code change required.

**Shadow phase (one-week horizon).**

```bash
export CAO_REFINERY_ENGINE=parallel
# restart cao-server
```

Both engines run on every Refinery write. YAML decides; Cedar shadows. Watch OTel for divergence:

```
{ "name": "cao.refinery.policy.divergence",
  "attributes": { "cao.refinery.policy.diverged": true } }
```

Audit each divergence: is the YAML rule the source of truth, or did the Cedar policy fix a gap? Update the Cedar policy file accordingly. Repeat until divergences are zero or fully understood.

**Cut-over.**

```bash
export CAO_REFINERY_ENGINE=cedar
# restart cao-server
```

Cedar authoritative; YAML shadows. Run for one more horizon to catch surprises. After this, an operator may safely delete the YAML rules file (the engine falls back through `PermissivePolicy` so a missing YAML file doesn't crash `parallel` mode).

**Rollback.** Setting `CAO_REFINERY_ENGINE=yaml` (or unsetting) reverts to the v2.5 baseline immediately on the next process restart. No data migration required.

---

## Forward look

These runbooks track the v2.5 surface area through the v2.5 close-out PR. v2.6 work adds new operational surfaces; runbooks land alongside the implementation per phase.
