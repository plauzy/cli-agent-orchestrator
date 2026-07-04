# CAO Tenets

Principles that guide how we evolve this codebase. New tenets are added by direct user direction in a session and committed alongside the work they shaped.

---

## 1. Provider-onboarding is a first-class concern (2026-05-12)

> *"This repo is only as easy to set up as its most difficult provider."*

CAO supports 8 provider CLIs (Kiro, Claude Code, Codex, Q, Gemini, Kimi, Copilot, OpenCode). Each one raises the bar for new contributors and CI: one stale auth path or drifted regex pattern blocks shift-left testing for everyone touching that provider.

### What this means in practice

**Three-tier provider model.** Every e2e surface picks a tier explicitly:

| Tier | Audience | Mechanism | Secret needs |
|---|---|---|---|
| **1 — Default-off** | unit + most integration | W1 fixtures with `cao_server` (no auth). `cao_terminal` skips when no provider boots. | None — already shipped. See `test/fixtures/cao_server.py`. |
| **2 — Mock provider** | e2e in CI on PRs from forks | `mock_cli` provider: minimal Python emitting the IDLE/PROCESSING/COMPLETED regex patterns from a deterministic echo loop. `cao launch --provider mock_cli` runs with no external CLI installed. | None. |
| **3 — Real-provider matrix** | nightly + manual `workflow_dispatch` only (never on fork PRs) | One workflow per provider (`e2e-anthropic.yml`, `e2e-openai.yml`, …) consuming `secrets.<PROVIDER>_API_KEY`. Gated by `if: github.event.pull_request.head.repo.full_name == github.repository` to deny forks. | Per-provider CI service-account keys, scoped to "test" usage tier where supported. |

**Secret hygiene in CI.**

- Never commit provider config files. Auth lives entirely in env vars consumed at workflow run-time.
- Each provider key has its own GH secret name; key rotation is a single PR touching only workflow files.
- Tier-3 jobs always set `continue-on-error: true` for individual providers so one stale key doesn't red-X the run; the aggregate job that requires "at least one provider succeeded" is what's merge-blocking.
- Workflows use `permissions: contents: read` and explicit `secrets:` passthrough — no `secrets.*` is available in reusable workflows by default.

**Failure visibility.** When a provider can't boot (timeout, missing CLI, drifted regex), tests must skip with a clear message naming the provider and the failure mode (see `test/fixtures/cao_server.py:_create_terminal_authed` and `test/e2e/test_websocket_auth.py:_create_terminal_authed` for the canonical pattern). Tests must never fail-silent or fail-cryptic on a provider-side issue — that's how the bar rises uncontrollably for the next contributor.

**Cycle time.** When a provider regex drifts, regenerating its fixture (`test/providers/fixtures/generate_fixtures.py` per the existing pattern) and re-shipping the provider module is a P0 unblocker, not a maintenance task. The repo's onboarding bar = the slowest provider's recovery time.

### Why this exists

PR #25 (W2 WebSocket auth integration smoke) skipped 3 of 4 scenarios because `kiro_cli` initialization timed out on the dev host. The skip path was graceful, but the underlying experience — "you can't run the e2e suite without authenticating an external CLI" — is the kind of friction that compounds across 8 providers and silently kills adoption.

The proposed `mock_cli` provider (Tier 2) is the missing piece that lets the e2e suite run green in CI on every PR — including from forks — without provisioning real provider credentials.

---

## 2. "Why" before "what" (2026-05-12)

> *Every meaningful improvement must answer "why does this need to exist" before "what are we changing". The why-discovery is part of the change, not a preamble to it. When we can't articulate why, we don't ship.*

Background: this repo has accumulated an overwhelming surface area (8 providers, 4 entry points, ~20 services, multiple control planes) without a single guiding principle visible from the outside. The author has admitted to building and abandoning ~10 UX iterations because no clear "why" anchored them. That symptom is the disease — when "why" is implicit, every contributor invents their own, and the codebase fragments into 10 disconnected dialects of "what".

### What this means in practice

**Every PR description answers four questions, in order, before "summary of changes":**

1. **What outcome are we trying to change?** (Be specific. "Improve X" is not an outcome; "reduce manual smoke verification from 20 min → 30 s per release" is.)
2. **What would have to be true** for that outcome to look different than today?
3. **What is the smallest change that makes those things true?**
4. **How will we know it worked?** (Quantifiable. See §3.)

**Every workstream plan** (`docs/w3-w8-batch.md`, future batch docs) has a "Why this batch exists" section as its first content section, **before** the unit decomposition. If you can't write that section, you don't have a plan yet — you have a list.

**"Why" survives the change.** When the change ships, the "why" gets committed to the doc that survives: a tenet, an RFC, or a top-level doc with the original prompt and the resulting outcome. PRs are ephemeral; tenets and RFCs are durable.

**The why-process is the core layer.** This tenet itself is durable; the methodology lives in the repo, not in any single contributor's head. New work that doesn't pass the four-question filter gets blocked here, regardless of who's asking.

### What good "why" answers look like

| Anti-pattern | Better |
|---|---|
| "We need a refresh-token rotation in the PWA." | "Users on the PWA get logged out every 60 minutes because Auth0 access tokens are 1 h; the current flow makes them re-enter credentials mid-task. Outcome: ≥90% of sessions ≥4 h continue seamlessly. Smallest change: silent refresh on `aud` mismatch." |
| "Add a Playwright test." | "Manual WS-auth smoke (PR #23, 4 unchecked boxes) costs ~20 min of human verification per release and gets skipped under pressure. Outcome: 100% of WS-auth regressions caught pre-merge. Smallest change: 4 Playwright specs that consume the W1 subprocess fixture." |

The "better" column is testable, falsifiable, and survives without context. The "anti-pattern" column requires the author in the room to make sense.

---

## 3. Before/after metrics on every meaningful change (2026-05-12)

> *Every improvement carries a quantitative measure of "before → after". If we can't measure it, we can't tell whether we made the system better or just busier.*

This is the natural consequence of Tenet #2. "How will we know it worked?" must produce a number.

### What this means in practice

**Pick at least one of these axes** per workstream:

| Axis | Unit | Example |
|---|---|---|
| **Manual-step count** | discrete steps | "Manual smoke: 4 checkboxes × 5 min = 20 min" → "30 s automated" → **40× faster** |
| **Onboarding bar** | what a new contributor must auth | "8 providers" → "0 providers (Tier 2 mock_cli)" |
| **Feedback latency** | time from regression introduced → caught | "next release" → "next CI run (~5 min)" |
| **Setup time** | first-time-to-running | minutes saved on local boot |
| **Failure attribution** | "test failed, why?" → answer time | "log archeology, ~10 min" → "skip message names the cause, 0 min" |
| **Cycle time** | round-trip on a single fix | hours/days |

**Record the measurement in the workstream's PR description.** The measure becomes part of the durable record; "we made it better" without a number is not a closeable claim.

**The four-question filter from Tenet #2 ends with this.** Question 4 ("how will we know it worked?") = pick an axis + a target.

### Reusable evaluation template

Every batch / RFC / large change uses this section structure (in order). If a section is empty, that's a signal to stop and answer the question, not to skip it.

```
1. Why this exists
   - What outcome are we changing?
   - What would have to be true?
   - Smallest change?
   - How will we know? (axis + target)

2. Before-state measurement
   - Concrete numbers as of the change opening.

3. The change
   - Decomposition / units / files.

4. After-state target
   - The target for the same axis.

5. Self-referential proof (where applicable)
   - Was the change built using its own approach? If not, why not?

6. Pickup / onboarding pointer
   - Reading order for new contributors.
```

This template applies to **every** durable plan doc going forward. `docs/w3-w8-batch.md` is the first reference instance.
