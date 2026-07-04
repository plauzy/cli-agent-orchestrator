# Refinery YAML → Cedar Policy Migration

The Refinery write gate (`src/cli_agent_orchestrator/refinery/policy.py`)
currently evaluates rules in a small operator-managed YAML file. The
v2.5 close-out introduces a Cedar adapter
(`src/cli_agent_orchestrator/refinery/cedar_policy.py`) and a parallel-
evaluation harness so operators can:

1. Run YAML and Cedar engines side-by-side in shadow mode.
2. Audit divergences via OTel `cao.refinery.policy.divergence` spans.
3. Flip the runtime authoritative engine via env var, no code change.

The runtime engine swap **defaults to off**. Operators opt in per
deployment via `CAO_REFINERY_ENGINE`.

---

## Engine selection (`CAO_REFINERY_ENGINE`)

| Value      | Behavior                                                                 |
|------------|--------------------------------------------------------------------------|
| `yaml`     | Default. `YamlRulePolicy` evaluates directly. v2.5 baseline.             |
| `parallel` | Both engines run on every request; YAML is authoritative; Cedar is shadow. |
| `cedar`    | Both engines still run; Cedar is authoritative; YAML is shadow.            |

Unknown values fall back to `yaml` with a warning. Switching engines
takes effect at process start; mid-process switches are not supported.

---

## YAML grammar

The grammar lives at
[`src/cli_agent_orchestrator/refinery/policy.py:43–142`](../src/cli_agent_orchestrator/refinery/policy.py).
A rule is a mapping with three optional keys:

```yaml
rules:
  - action: "delete_terminal"
    payload_match:
      tmux_session: "^prod-"
    outcome: "escalate"
    reason: "production session — operator confirms"

  - action: "delete_flow"
    outcome: "deny"
```

Rules are evaluated in order; the first match wins. Anything not
matched falls back to `ALLOW`.

`payload_match` values are regular expressions evaluated against the
payload field as a string. A rule without an `action` key matches every
action; a rule without `payload_match` matches every payload for the
named action.

---

## Equivalent Cedar policies

Cedar's grammar is more expressive but requires a deliberate mapping.
The Refinery's `(action, payload)` shape translates to Cedar's
`(principal, action, resource, context)` as:

| Refinery field            | Cedar field                                    |
|---------------------------|------------------------------------------------|
| (none — process-wide)     | `principal = User::"refinery"`                 |
| `action`                  | `action == Action::"<action>"`                 |
| (derived)                 | `resource == Resource::"refinery/<action>"`    |
| `payload`                 | `context.<key>`                                |

### Rule 1 — escalate prod terminal deletes (YAML → Cedar)

YAML:

```yaml
- action: "delete_terminal"
  payload_match: { tmux_session: "^prod-" }
  outcome: "escalate"
  reason: "production session — operator confirms"
```

Cedar (deny — Cedar has no native ESCALATE; encode "needs operator
approval" as a separate Cedar policy that denies, and let the YAML
shadow rule produce the ESCALATE outcome):

```cedar
forbid (
  principal == User::"refinery",
  action == Action::"delete_terminal",
  resource
)
when {
  context.tmux_session like "prod-*"
};
```

### Rule 2 — deny all flow deletes

YAML:

```yaml
- action: "delete_flow"
  outcome: "deny"
```

Cedar:

```cedar
forbid (
  principal == User::"refinery",
  action == Action::"delete_flow",
  resource
);
```

### Rule 3 — allow everything else (default-ALLOW)

The YAML grammar's "anything not matched falls back to ALLOW" needs an
explicit Cedar `permit`:

```cedar
permit (
  principal,
  action,
  resource
)
when {
  // Everything not denied above is permitted.
  true
};
```

In Cedar's evaluation order, `forbid` always wins over `permit`, so
the deny-rules above take precedence regardless of where the
`permit` sits in the policy text.

---

## Parallel-evaluation harness

When `CAO_REFINERY_ENGINE=parallel` (or `cedar`),
:class:`cli_agent_orchestrator.refinery.cedar_policy.ParallelEvaluatingPolicy`
runs both engines on every Refinery write. The non-authoritative
engine's outcome is observable via:

  * **OTel span** `cao.refinery.policy.divergence` with attributes
    `cao.refinery.policy.action`, `cao.refinery.policy.yaml_outcome`,
    `cao.refinery.policy.cedar_outcome`,
    `cao.refinery.policy.diverged` (bool),
    `cao.refinery.policy.authoritative`.

Operators query their tracing backend for `diverged=true` to find
mismatches:

```
{ "service.name": "cao", "name": "cao.refinery.policy.divergence",
  "attributes": { "cao.refinery.policy.diverged": true } }
```

---

## Rollout sequence

The migration is gated by the env var. The recommended sequence:

1. **Day 0** — operator drafts Cedar policies equivalent to the YAML
   rules. Pass them at construction time:

   ```python
   from cli_agent_orchestrator.refinery import CedarPolicy, select_policy, YamlRulePolicy
   yaml_policy = YamlRulePolicy.from_file(Path(...))
   cedar_policy = CedarPolicy(policies=open("/etc/cao/refinery.cedar").read())
   policy = select_policy(yaml_policy=yaml_policy, cedar_policy=cedar_policy)
   ```

2. **Day 1–7** — set `CAO_REFINERY_ENGINE=parallel`, restart CAO.
   YAML stays authoritative; Cedar shadows. Watch OTel for
   `diverged=true` spans; fix Cedar policies until divergences are
   either zero or fully understood.

3. **Day 8** — flip to `CAO_REFINERY_ENGINE=cedar`. Cedar authoritative;
   YAML shadows. Run for one more horizon to catch any production
   surprises (the YAML divergence path now flags when the Cedar
   engine *over*-permits relative to YAML).

4. **Day 14+** — once stable, an operator may delete the YAML rules
   file. The runtime engine selection still falls back through
   :class:`PermissivePolicy` so a missing YAML doesn't break the
   `parallel` mode.

5. **v2.6** — drop the YAML engine entirely. The two-week shadow
   horizon above is what makes this safe.

---

## What this migration does **not** do

- Does not switch the runtime authoritative engine. That's an operator
  decision via env var.
- Does not auto-translate YAML rules into Cedar. The YAML grammar's
  regex `payload_match` doesn't have a perfect Cedar analog; operators
  hand-craft Cedar policies and use the parallel harness to verify
  equivalence.
- Does not remove the YAML engine. v2.5 ships the Cedar adapter; v2.6
  is the cleanup.

---

## See also

- [`src/cli_agent_orchestrator/refinery/policy.py`](../src/cli_agent_orchestrator/refinery/policy.py) — current YAML engine.
- [`src/cli_agent_orchestrator/refinery/cedar_policy.py`](../src/cli_agent_orchestrator/refinery/cedar_policy.py) — Cedar adapter + parallel harness.
- [Cedar language reference](https://www.cedarpolicy.com/) — upstream syntax.
- [`docs/runbooks.md`](runbooks.md) — operator runbooks (Cedar cut-over runbook below).
