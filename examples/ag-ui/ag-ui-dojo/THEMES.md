<!-- ABOUTME: The canonical "why" of the AG-UI Dojo — the frontier-team practices it embodies. -->
<!-- ABOUTME: Every other dojo artifact (capture, recorder, docsite modules, plan) links back here. -->

# Why this dojo exists — the through-line

The CAO AG-UI Dojo is not a demo bolted on after the fact. It is a **working
proof of the two practices that define a frontier engineering team** — and CAO
is the tool that makes both practices routine.

> Frontier engineering teams don't just adopt AI tools, they change how they
> build software. — [kiro.dev/topics/frontier-teams](https://kiro.dev/topics/frontier-teams/)

Two of the five frontier-team practices are the spine of this effort. The dojo
**is** them, demonstrated on CAO's own codebase:

## 1. Feed agents instead of babysitting them  →  **Dog-food**

Frontier teams "maintain a steady backlog of well-scoped tasks, running multiple
agents in parallel and reviewing output asynchronously." CAO is precisely the
substrate for that: a supervisor delegates to worker agents (`assign`,
`handoff`) across providers, and the operator reviews results — not keystrokes.

**The dog-food loop:** the data this dojo renders is produced by a *real CAO
orchestration* — a `kiro_cli` supervisor delegating to `claude_code` and `codex`
workers. CAO builds and observes its own AG-UI showcase. The audit fleet is
itself the workload the feature visualizes (`capture.py` extends the existing
[`ag-ui-meta-dogfood`](../ag-ui-meta-dogfood/) loop). We eat our own cooking:
if the orchestration story is real, the fixtures are real.

## 2. Shift testing left  →  **Verify before the pipeline**

Frontier teams "build tooling so agents can run integration tests locally and
self-correct before code ever reaches the pipeline… automated guardrails,
component tests, performance tests, and formatters that caught issues early. Code
reviews shifted focus to interface definitions and architectural decisions rather
than code style."

**The shift-left loop:** every dojo artifact is *gated by an assertion that runs
before anything ships*. Fixtures must satisfy the AG-UI frame contract and the
metadata-only privacy boundary; the renderer must actually paint all six
generative-UI components and the four L2 panels; the off-list component must be
refused. **No green recording, no merged dojo, unless the assertions pass first.**
A broken dojo cannot produce a passing artifact. This mirrors the shipped
[`ag-ui-construct-demos`](../ag-ui-construct-demos/) gated-recorder pattern.

---

## The three pillars underneath (how Kiro frames it)

Frontier teams "give agents rich context, make intent explicit, and verify
correctness before code ships." This dojo operationalizes all three:

| Pillar | How the dojo embodies it |
|---|---|
| **Rich context** | Steering files + the `agui-author` skill give the worker agents the exact component vocabulary and privacy contract before they emit anything. |
| **Explicit intent** | The `.sop` plan and this THEMES file define what "done" looks like *before* code — acceptance criteria, gates, and the fixture contract are written first. |
| **Verify before ship** | The shift-left gates (frame contract → renderer assertion → gated media → site build) run in CI ahead of the pipeline. |

## The two supporting practices (also present)

- **Invest in agent context** — the dojo ships steering + the `agui-author`
  skill so any provider's agent authors valid UI on the first try.
- **Make intent explicit before code** — the plan/spec precedes the scaffold;
  the fixture schema is the contract the renderer is written against.

## One-line summary (use this in talks / the README lead)

> **The CAO AG-UI Dojo is CAO feeding agents to build its own showcase
> (dog-food), with every artifact gated by an assertion that runs before the
> pipeline (shift-left) — a frontier-team workflow you can watch.**
