# PR #387 Reconciliation & Orchestration Plan

## 1. Executive Summary

**Goal:** Produce professional-ready, upstream-submittable pull requests that address every review comment on [awslabs/cli-agent-orchestrator#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387).

**Decomposition:**

| Shape | Scope | Lands |
|-------|-------|-------|
| **PR-A** (AG-UI core) | AG-UI protocol adapter, SSE streaming, PWA integration, plugin events | First |
| **PR-B** (A2A hardened) | A2A JSON-RPC endpoint, auth enforcement, task store hardening, agent-card listener | Second |

This sequencing follows the upstream reviewer recommendation (@fanhongy): PR-A provides the streaming surface that PR-B's agent-to-agent layer consumes, so PR-A must land first.

**Approach:** Use CAO's parallel multi-provider orchestration (`/cao`) to generate competing reconciled variants from existing Kiro and Claude branches, then run `/cao-eval` to select the best result per PR shape before submitting upstream.

**Visual evidence mandate:** Every major feature update produced by this plan MUST ship visual evidence — a full-quality `.mp4` screen recording of the live feature path (the canonical artifact), a derived looping `.gif`, and comprehensive annotated screenshots — embedded in both the project documentation and the PR description. This is an enforceable gate, not an aspiration: see [Section 8 (Media & Visual Evidence Requirements)](#8-media--visual-evidence-requirements). It applies to GUI surfaces (Track A / PR-A) and non-GUI surfaces (Track B / PR-B) alike.

---

## 2. Branch Inventory

All PRs are open against `plauzy/cli-agent-orchestrator` and target `feat/agentic-protocols-generative-ui` as the base branch.

| PR# | Branch | Shape | Provider | Description | Status |
|-----|--------|-------|----------|-------------|--------|
| 9 | `feat/agentic-protocols-generative-ui` | Original | plauzy | Original monolithic PR (feat: agentic protocol surface + generative UI) | Open - base for decomposition |
| 11 | `claude/pr387-agui-core` | PR-A | Claude | AG-UI core implementation | Open - evaluation candidate |
| 12 | `claude/pr387-a2a-hardened` | PR-B | Claude | A2A hardened implementation | Open - evaluation candidate |
| 13 | `kiro/pr387-a2a-hardened` | PR-B | Kiro | A2A hardened implementation | Open - evaluation candidate |
| 14 | `kiro/pr387-agui-core` | PR-A | Kiro | AG-UI core + live demo | Open - evaluation candidate |
| 15 | `docs/pr387-reconciliation` | Eval | docs | Kiro x Claude evaluation and reconciliation plan | Open - reference |
| 16 | `docs/pr387-reconciliation-2` | Eval | docs | Independent Linux/Py3.12 evaluation run | Open - reference |
| 17 | `claude/pr387-remediation-reconcile-jlcpmy` | Eval | Claude | Remediation scorecard + reconciliation plan | Open - reference |

---

## 3. Upstream Review Comment Registry

Every comment from [awslabs/cli-agent-orchestrator#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387) mapped to resolution ownership.

### Blocking (must-fix before merge)

| ID | File:Line | Author | Summary | Agreed Fix | Owner |
|----|-----------|--------|---------|------------|-------|
| RC-01 | `rpc.py:24` | @fanhongy | A2A auth bypass - no auth enforcement despite docstring claims | Per-method scope enforcement using `require_any_scope`/`is_auth_enabled` (`task.send`/`cancel` -> `cao:write`; `task.get`/`stream` -> `cao:read`) | PR-B |
| RC-02 | `store.py:47` | @fanhongy | Unbounded in-memory store - OOM vector | Size cap + TTL eviction (env-tunable), `task.send` rejected when full | PR-B |
| RC-03 | `rpc.py:150` | @fanhongy | Task id injection - peer-controlled key overwrites other tasks | Server-side UUID generation OR reject if id already exists | PR-B |
| RC-04 | `listener.py:56` | @fanhongy | A2A endpoint on agent-card listener has no auth | `FastAPI Depends()` on `/a2a/v1/rpc` that validates Bearer token via JWKS when auth enabled | PR-B |

### Important / Nit

| ID | File:Line | Author | Summary | Agreed Fix | Owner |
|----|-----------|--------|---------|------------|-------|
| RC-05 | `types.py:112` | reviewer | `Task.from_dict` KeyError when id missing | Use `data.get("id", "")` instead of `data["id"]` | PR-B |
| RC-06 | `pyproject.toml:50` | reviewer | `authlib` as production dep but only used in tests | Move to `[dev]` dependency group | PR-B |

### Copilot Nits

| ID | File:Line | Author | Summary | Agreed Fix | Owner |
|----|-----------|--------|---------|------------|-------|
| RC-07 | `tests/__init__.py` | copilot | Stray `tests/__init__.py` confusing test discovery | Remove file | PR-A |
| RC-08 | `mypy.ini` | copilot | `python_version = 3.11` vs `requires-python >= 3.10` | Set `python_version = 3.10` | PR-A |
| RC-09 | `events.py` | copilot | Wrong RFC citation (9114 vs W3C Trace Context) | Correct to W3C Trace Context reference | PR-A |
| RC-10 | `InstancePicker.tsx` | copilot | Nested interactive elements (a11y violation) | Refactor to avoid nesting `<button>` inside clickable container | PR-A |
| RC-11 | `test_headless_ci.py` | copilot | Stale docstring | Update docstring to match current test behavior | PR-A |

---

## 4. Head-to-Head Branch Audit Matrix

### PR-A Resolution Status

| ID | Issue | `kiro/pr387-agui-core` | `claude/pr387-agui-core` | Notes |
|----|-------|:---:|:---:|-------|
| RC-07 | Stray `tests/__init__.py` | Partial | Partial | Neither explicitly removes; needs verification |
| RC-08 | mypy `python_version` mismatch | Yes | No | Kiro sets 3.10; Claude leaves 3.11 |
| RC-09 | Wrong RFC citation | Yes | Yes | Both fix the reference |
| RC-10 | Nested interactive elements | No | Partial | Claude restructures but introduces different a11y pattern |
| RC-11 | Stale docstring | Yes | Yes | Both update |

**PR-A Provider Wins:**

| Aspect | Winner | Rationale |
|--------|--------|-----------|
| Py3.10 compatibility | Kiro | Green on Py3.10, mypy version set correctly |
| Skill governance (`SHIPPED_SKILLS`) | Kiro | Ships guard preventing unregistered skills |
| Demo prop fidelity | Kiro | Props match actual AG-UI event schema |
| Committed demo media | Claude | Claude commits a `.webm` demo file; under the [Section 8](#8-media--visual-evidence-requirements) media mandate, committing demo media under `docs/media/` is now **required** (following established repo convention), so this is a Claude advantage to carry forward — the reconciled PR-A must ship mp4 + gif + screenshots regardless |
| PWA `?since=` cursor-loss fix | Claude | Kiro ships the reconnect cursor bug |
| Stronger default-off guard (module-absent) | Claude | Better isolation when AG-UI module not present |
| Live reconnect proof | Claude | Real e2e assertion for SSE reconnection |

### PR-B Resolution Status

| ID | Issue | `kiro/pr387-a2a-hardened` | `claude/pr387-a2a-hardened` | Notes |
|----|-------|:---:|:---:|-------|
| RC-01 | Auth bypass | Partial | Yes | Claude enforces auth-before-parse; Kiro wires scopes but parse order differs |
| RC-02 | Unbounded store | Yes | Yes | Both implement cap + eviction; Kiro adds RESOURCE_EXHAUSTED + HTTP 429 |
| RC-03 | Task id injection | No | No | **Both missed** - post-remediation finding |
| RC-04 | Listener no auth | Yes | Yes | Both add `Depends()` guard |
| RC-05 | `Task.from_dict` KeyError | No | No | **Both missed** |
| RC-06 | `authlib` dep placement | Partial | Yes | Claude moves cleanly; Kiro has dep sequencing issue |

**PR-B Provider Wins:**

| Aspect | Winner | Rationale |
|--------|--------|-----------|
| Auth-before-parse enforcement | Claude | Validates token before JSON-RPC parse (prevents oracle attacks) |
| Real JWT/JWKS tests | Claude | Full integration tests with actual token validation |
| `reset_jwks_cache` fix | Claude | Correctly invalidates cache on key rotation |
| `WWW-Authenticate` header | Claude | Standards-compliant 401 response |
| `RESOURCE_EXHAUSTED` + HTTP 429 semantics | Kiro | Correct gRPC status code + HTTP mapping |
| Extracted `_should_mount_a2a()` guard | Kiro | Clean separation of mount decision |
| 28-case test matrix | Kiro | Comprehensive parametrized coverage |
| Correct dep sequencing in pyproject.toml | Kiro | Proper optional dependency ordering |

### Both Missed (Gaps Found Across All Evaluations)

| Gap | Severity | Source | Notes |
|-----|----------|--------|-------|
| Task id upsert injection (RC-03) | Blocking | Post-remediation review | Neither branch prevents id collision |
| `Task.from_dict` KeyError (RC-05) | Important | Review comment | Neither branch uses `.get()` |
| WS 4401 never asserted e2e on malformed token | Medium | Evaluation PR #16 | No branch tests WebSocket auth rejection path |
| Equal-timestamp `?since=` boundary | Medium | Evaluation PR #15 | Race condition at exact boundary not handled |
| `STATE_DELTA` debounce / `emit_ui` rate limiting | Follow-up | All evaluations agree | Out of scope for this PR stack |

---

## 5. /cao Parallel Orchestration Strategy

This section defines how to use CAO's multi-agent orchestration primitives to generate reconciled variants.

### Agent Topology

```
+---------------------------+
|   Supervisor Agent        |
|   (plauzy/orchestrator)   |
|   Profile: multi-provider |
+---------------------------+
       |           |
   handoff      handoff
       |           |
  +--------+  +--------+
  | Worker |  | Worker |
  | Kiro   |  | Claude |
  +--------+  +--------+
```

### Orchestration Primitives Used

| Primitive | Usage |
|-----------|-------|
| `handoff` | Supervisor hands off PR-A reconciliation to each worker (sync, wait for completion) |
| `assign` | Supervisor assigns PR-B reconciliation (async, fire-and-forget) once PR-A winner is selected |
| `send_message` | Inbox delivery of audit matrix, review comment registry, and evaluation criteria to workers |

### Branch Naming Convention

| Purpose | Pattern | Example |
|---------|---------|---------|
| PR-A reconciliation variant | `reconcile/pr-a-v{N}` | `reconcile/pr-a-v1`, `reconcile/pr-a-v2` |
| PR-B reconciliation variant | `reconcile/pr-b-v{N}` | `reconcile/pr-b-v1`, `reconcile/pr-b-v2` |
| Final winner (selected) | `reconcile/pr-a-final`, `reconcile/pr-b-final` | - |

### Parallel Execution Plan

```
Phase 1: PR-A Reconciliation (parallel)
  cao launch --headless --async \
    --supervisor orchestrator \
    --workers kiro,claude \
    --task "reconcile PR-A from audit matrix"

  Worker-Kiro:  reconcile/pr-a-v1 (starts from kiro/pr387-agui-core)
  Worker-Claude: reconcile/pr-a-v2 (starts from claude/pr387-agui-core)

Phase 2: /cao-eval PR-A
  cao-eval --branches reconcile/pr-a-v1,reconcile/pr-a-v2 \
    --rubric pr387-reconciliation-rubric.yaml

Phase 3: PR-B Reconciliation (parallel, after PR-A selected)
  cao launch --headless --async \
    --supervisor orchestrator \
    --workers kiro,claude \
    --task "reconcile PR-B from audit matrix"

  Worker-Kiro:  reconcile/pr-b-v1 (starts from kiro/pr387-a2a-hardened)
  Worker-Claude: reconcile/pr-b-v2 (starts from claude/pr387-a2a-hardened)

Phase 4: /cao-eval PR-B
  cao-eval --branches reconcile/pr-b-v1,reconcile/pr-b-v2 \
    --rubric pr387-reconciliation-rubric.yaml
```

---

## 6. Variant Generation Approach

### PR-A Reconciliation

**Base:** `kiro/pr387-agui-core` (rationale: green on Py3.10, skill governance, minimal/clean diff). Note: the reconciled PR-A must still add the required demo media under `docs/media/` per [Section 8](#8-media--visual-evidence-requirements) — the media mandate reframes "no committed artifacts" as "only the *required* feature-prefixed media, nothing stray."

**Cherry-pick from `claude/pr387-agui-core`:**

| Aspect | What to Port | Files Affected |
|--------|--------------|----------------|
| PWA `?since=` cursor-loss fix | SSE reconnect cursor persistence logic | `cao_pwa/src/hooks/useAgUIStream.ts` |
| Stronger default-off guard | Module-absent check before AG-UI route registration | `src/cli_agent_orchestrator/services/agui_stream.py` |
| Live reconnect proof | E2e assertion for SSE reconnection | `test/e2e/test_agui_reconnect.py` |

**Additionally address (both missed):**

| RC | Fix | Implementation |
|----|-----|----------------|
| RC-07 | Remove stray `tests/__init__.py` | `git rm tests/__init__.py` if present |
| RC-08 | Set `python_version = 3.10` in mypy config | Edit `mypy.ini` |
| RC-09 | Correct RFC citation | Fix `src/cli_agent_orchestrator/plugins/events.py` reference |
| RC-10 | Fix nested interactive elements | Refactor `cao_pwa/src/components/InstancePicker.tsx` |
| RC-11 | Update stale docstring | Edit `test/test_headless_ci.py` |

### PR-B Reconciliation

**Base:** `claude/pr387-a2a-hardened` (rationale: auth-before-parse enforcement, real JWT/JWKS tests, standards-compliant responses)

**Cherry-pick from `kiro/pr387-a2a-hardened`:**

| Aspect | What to Port | Files Affected |
|--------|--------------|----------------|
| `RESOURCE_EXHAUSTED` + HTTP 429 | Correct gRPC status + HTTP status mapping for capacity errors | `src/cli_agent_orchestrator/a2a/rpc.py` |
| `_should_mount_a2a()` guard | Extracted predicate for A2A endpoint mounting decision | `src/cli_agent_orchestrator/a2a/__init__.py` |
| 28-case parametrized test matrix | Comprehensive auth/store/rpc test coverage | `test/a2a/test_rpc.py` |
| Correct dep sequencing | Optional dependency ordering in pyproject.toml | `pyproject.toml` |

**Additionally address (both missed):**

| RC | Fix | Implementation |
|----|-----|----------------|
| RC-03 | Task id injection | Server-side UUID generation; reject `task.send` if caller-supplied id already exists in store |
| RC-05 | `Task.from_dict` KeyError | Replace `data["id"]` with `data.get("id", "")` in `src/cli_agent_orchestrator/a2a/types.py:112` |
| RC-06 | `authlib` dep placement | Move `authlib` from `[project.dependencies]` to `[project.optional-dependencies.dev]` |

---

## 7. /cao-eval Criteria and Success Gates

### Evaluation Rubric

Each variant is scored against the following criteria (weighted):

| Category | Weight | Criteria |
|----------|--------|----------|
| **Blocking comments resolved** | 35% | All RC-01 through RC-04 (for PR-B), or relevant nits (PR-A) fully addressed |
| **Important comments resolved** | 15% | RC-05 and RC-06 (PR-B) correctly fixed |
| **Nits addressed** | 10% | RC-07 through RC-11 (PR-A) all fixed |
| **Gate commands pass** | 20% | Full gate suite green (see below) |
| **Visual evidence / media deliverables** | 15% | mp4 + derived gif + comprehensive screenshots exist under `docs/media/` and are correctly embedded per [Section 8](#8-media--visual-evidence-requirements) (mp4 as plain link; gif/png inline with alt text + caption) in BOTH the feature docs and the PR description |
| **Clean diff** | 5% | No unrelated changes, minimal diff vs base (note: demo media under `docs/media/` is expected and required, not counted as unrelated) |

> **Hard gate:** The media deliverables are also a pass/fail prerequisite — a variant that scores well on code but is missing any required artifact (mp4, gif, or screenshots) or embeds them incorrectly is marked **not done** and cannot win, regardless of weighted score. See Pass/Fail Determination below.

### Gate Command Suite

```bash
# Python gates
uv run pytest test/ --ignore=test/e2e -m 'not integration' -v
uv run mypy src/
black --check .
isort --check-only .

# PWA gates
cd cao_pwa && npx tsc --noEmit && npm test && npm run build

# Web UI gates (if touched)
cd web && npx tsc --noEmit && npm test && npm run build

# Media gates (record live feature path, derive gif, capture screenshots)
#   Track A (GUI): Playwright live spec + CI recording job
npx playwright test cao_pwa/e2e/live-dashboard.spec.ts   # produces the live recording
bash showcase.sh                                          # headless proof fallback
#   Derive the looping gif from the canonical mp4
ffmpeg -i docs/media/<feature>-demo.mp4 -vf "fps=12,scale=960:-1:flags=lanczos" docs/media/<feature>-demo.gif
#   Verify artifacts exist and mp4 is NOT embedded with image syntax
test -f docs/media/<feature>-demo.mp4 && test -f docs/media/<feature>-demo.gif
! grep -Rus '!\[[^]]*\](.*\.mp4)' docs/   # mp4 must be a plain link, never ![]()
```

### When to Run /cao-eval

- After 2+ variants exist for a given PR shape (PR-A or PR-B)
- After each variant passes the gate command suite independently
- Before selecting a winner or performing a merge-best operation

### Pass/Fail Determination

A variant **passes** if:
1. All blocking review comments for its shape are resolved (verified by code inspection)
2. All gate commands exit 0
3. No regressions introduced vs. `main` (diff-test against main's test suite)
4. Diff is scoped to the PR shape's files (no cross-contamination between PR-A and PR-B concerns)
5. **Media deliverables present and correct (hard gate):** a full-quality `.mp4` of the live feature path, a derived looping `.gif`, and comprehensive annotated screenshots all exist under `docs/media/` and are embedded per [Section 8](#8-media--visual-evidence-requirements) — mp4 as a plain link, gif/png inline with alt text + caption — in both the feature docs and the PR description. A variant missing any artifact, or embedding the mp4 with `![]()` image syntax, **fails** regardless of code quality.

A variant **wins** if it scores highest on the weighted rubric across all passing variants.

---

## 8. Media & Visual Evidence Requirements

**Policy (mandatory, enforceable):** Every major feature update produced by this plan MUST ship visual evidence. A variant, reconciled PR, or feature update is **not "done"** until the media deliverables below exist, are stored per repo convention, and are correctly embedded in **both** the project documentation **and** the PR description. This section is referenced as a hard gate by the [/cao-eval rubric](#7-cao-eval-criteria-and-success-gates) and by the [Track A and Track B success gates](#84-per-track-success-gates).

### 8.1 Required Artifacts (per major feature update)

| # | Artifact | Format | Role | Embedding |
|---|----------|--------|------|-----------|
| 1 | Full-quality screen recording of the **live** feature path | `.mp4` | **Canonical artifact** — authoritative proof the feature works end to end | Plain markdown **link** (never `![]()`) |
| 2 | Short looping clip **derived from the mp4** | `.gif` | Inline preview for docs and PR body | Inline image `![alt](path)` |
| 3 | Comprehensive **annotated screenshots** of each key state / component / step | `.png` | Static reference for every UI state (GUI) or CLI step (non-GUI) | Inline image `![alt](path)` |

Every embed MUST carry descriptive alt text **and** a one-line caption.

### 8.2 Production & Storage

- **Recorded by** the Playwright live spec (`cao_pwa/e2e/live-dashboard.spec.ts`) and the CI recording job; the `showcase.sh` headless proof is the scriptable fallback.
- **mp4 is captured first** from the live run and is the canonical artifact. The **gif is derived from that mp4** (downscaled, looping — same source execution). **Screenshots are captured in the same live run**, so all three artifacts describe one consistent execution rather than three unrelated captures.
- **Stored under `docs/media/`**, following the established repo convention — the base branch already commits `.mp4`/`.webm`/`.gif`/`.png` demo binaries there, so committing media is the norm, not an exception.
- **Naming:** `{feature}-demo.mp4`, `{feature}-demo.gif`, `{feature}-{state}.png` (e.g., `agui-generative-ui-demo.mp4`, `a2a-auth-flow-401.png`).

### 8.3 Embedding Rules (GitHub-safe)

| Rule | Reason |
|------|--------|
| Reference the mp4 as a **plain markdown link** — `[Watch the live demo](docs/media/x-demo.mp4)` — **never** with image syntax `![]()` | A committed video embedded with `![]()` image syntax will **not play on GitHub**; it renders as a broken image |
| Embed the gif and every png **inline** with `![descriptive alt](path)` immediately followed by a caption line | gif/png render inline in both docs and PR bodies |
| Every embed carries **descriptive alt text + a one-line caption** | Accessibility and reviewer context |
| Apply the media to **BOTH** the project documentation (`docs/pwa.md` and the relevant feature docs) **AND** the PR description | Evidence must live where both readers and reviewers are |

**Non-viable technique (do not attempt):** offline/online reconnect emulation in headless Chromium — it is not reliable in that environment. To demonstrate reconnection, use server `SIGKILL` + restart + page reload and record that instead.

### 8.4 Per-Track Success Gates

Media is a first-class success gate for **both** reconciliation tracks. A track's `reconcile/*-final` branch cannot be selected until its media gate is green.

**Track A — `reconcile/pr387-agui-core` (PR-A, AG-UI / GUI):**
- Live mp4 of the AG-UI generative-UI path (agent stream -> PWA render -> reconnect via SIGKILL+reload).
- Derived looping gif + annotated screenshots of each key PWA state (instance picker, live event stream, generative-UI component render, post-reconnect resume).
- Embedded in `docs/pwa.md` and the PR-A description per 8.3.

**Track B — `reconcile/pr387-a2a-hardened` (PR-B, A2A transport / non-GUI):**
Track B has no PWA, but the "every major feature" guarantee still holds. Track B MUST ship **screen-recorded CLI walkthroughs** as mp4 + derived gif + screenshots for:

| Scenario | What the recording must show |
|----------|------------------------------|
| Auth enforcement flow | `401` (missing/invalid token) → `403` (valid token, insufficient scope) → `200` (valid token, correct scope) against `/a2a/v1/rpc` |
| Store-full capacity path | `task.send` rejected with `RESOURCE_EXHAUSTED` / HTTP `429` once the task-store cap is reached |

Record these via a scripted terminal session (e.g., `asciinema` or an `ffmpeg` screen capture of the CLI), store under `docs/media/`, and embed per 8.3 in the A2A feature doc and the PR-B description.

### 8.5 Media Deliverables Checklist (required in every reconciled PR description)

Both reconciled PRs (PR-A and PR-B) MUST include this checklist with every box checked before the PR is considered submittable:

- [ ] Full-quality `.mp4` of the **live** feature path committed under `docs/media/`
- [ ] `.mp4` embedded in the feature doc **and** PR body as a **plain link** (not `![]()`)
- [ ] Looping `.gif` **derived from the mp4**, embedded inline with alt text + caption
- [ ] Comprehensive annotated screenshots of **every** key state/step, embedded inline with alt text + captions
- [ ] Feature doc updated with the same media (`docs/pwa.md` for PR-A; A2A feature doc for PR-B)
- [ ] **(Track B only)** CLI walkthrough recordings for the `401 → 403 → 200` auth flow **and** the store-full `429` path
- [ ] Verified `mp4` is NOT embedded with image syntax anywhere (`grep` guard from the Media gate passes)

---

## 9. Reconciliation Workflow

### Step-by-Step Operational Procedure

```
Step 1: Sync main
  For each implementation branch:
    git fetch origin main
    git rebase origin/main
  Resolve any conflicts. Ensure gate commands still pass.

Step 2: Create reconcile/* branches
  git checkout feat/agentic-protocols-generative-ui
  git checkout -b reconcile/pr-a-v1
  git checkout -b reconcile/pr-a-v2
  (repeat for pr-b-v1, pr-b-v2)

Step 3: Supervisor dispatches PR-A reconciliation
  Supervisor agent uses `handoff` to assign:
    - Worker-Kiro: "Reconcile PR-A starting from kiro/pr387-agui-core,
       incorporating claude wins per Section 6, fixing all RC-07..RC-11"
    - Worker-Claude: "Reconcile PR-A starting from claude/pr387-agui-core,
       incorporating kiro wins per Section 6, fixing all RC-07..RC-11"
  Workers receive the audit matrix via `send_message`.

Step 4: Workers implement PR-A variants
  Each worker:
    a. Checks out their reconcile/pr-a-v{N} branch
    b. Applies base branch changes
    c. Cherry-picks winning patterns from the other provider
    d. Addresses all "both missed" gaps for PR-A
    e. Runs full gate command suite
    f. Produces media deliverables (Section 8): records the live AG-UI path
       via the Playwright live spec / CI recording job to an .mp4 under
       docs/media/, derives the looping .gif from that mp4, captures annotated
       screenshots of each key PWA state, and embeds them (mp4 as plain link;
       gif/png inline with alt text + captions) in docs/pwa.md
    g. Commits with message: "feat(agui): reconciled PR-A variant v{N}"

Step 5: /cao-eval for PR-A
  Run evaluation comparing reconcile/pr-a-v1 vs reconcile/pr-a-v2:
    - Automated gate pass/fail
    - Code review against RC-07..RC-11 checklist
    - Diff size comparison
    - Py3.10 compatibility verification
  Select winner -> tag as reconcile/pr-a-final

Step 6: Supervisor dispatches PR-B reconciliation
  Uses `assign` (async) since PR-B is independent post-selection:
    - Worker-Kiro: "Reconcile PR-B starting from kiro/pr387-a2a-hardened,
       incorporating claude wins per Section 6, fixing RC-03 and RC-05"
    - Worker-Claude: "Reconcile PR-B starting from claude/pr387-a2a-hardened,
       incorporating kiro wins per Section 6, fixing RC-03 and RC-05"

Step 7: Workers implement PR-B variants
  Each worker:
    a. Checks out their reconcile/pr-b-v{N} branch
    b. Applies base branch changes (including PR-A final, since PR-B stacks on PR-A)
    c. Cherry-picks winning patterns from the other provider
    d. Addresses all "both missed" gaps for PR-B (RC-03, RC-05)
    e. Runs full gate command suite
    f. Produces media deliverables for the non-GUI surface (Section 8.4):
       screen-records CLI walkthroughs to .mp4 under docs/media/ for the auth
       401 -> 403 -> 200 flow and the store-full RESOURCE_EXHAUSTED / HTTP 429
       path, derives the looping .gif from each mp4, captures step screenshots,
       and embeds them (mp4 as plain link; gif/png inline with alt text +
       captions) in the A2A feature doc
    g. Commits with message: "feat(a2a): reconciled PR-B variant v{N}"

Step 8: /cao-eval for PR-B
  Run evaluation comparing reconcile/pr-b-v1 vs reconcile/pr-b-v2:
    - Automated gate pass/fail
    - Security-focused review (auth bypass, injection, OOM)
    - Code review against RC-01..RC-06 checklist
    - Integration test coverage comparison
  Select winner -> tag as reconcile/pr-b-final

Step 9: Final gate verification
  On reconcile/pr-a-final:
    - Full gate suite (pytest, mypy, black, isort, tsc, npm test, npm build)
    - Media gate (Section 8): mp4 + derived gif + screenshots present under
      docs/media/, correctly embedded in docs/pwa.md (mp4 as plain link),
      grep guard confirms no ![]() image-syntax mp4 embeds
    - Manual review of diff vs feat/agentic-protocols-generative-ui
  On reconcile/pr-b-final (stacked on pr-a-final):
    - Full gate suite
    - Security audit of auth enforcement paths
    - Media gate (Section 8.4): CLI-walkthrough mp4s (401->403->200 auth flow
      and store-full 429 path) + derived gifs + step screenshots present and
      correctly embedded in the A2A feature doc
    - Verify no cross-contamination with PR-A files

Step 10: Submit upstream
  Create PRs against awslabs/cli-agent-orchestrator:
    - PR-A first (stacks on the existing #387 discussion)
    - PR-B second (stacks on PR-A once merged)
  Each PR references this reconciliation plan and the /cao-eval results.
  Each PR description embeds the media deliverables (Section 8): the mp4 as a
    plain link, the derived gif and screenshots inline with alt text + captions,
    and includes the completed media checklist (Section 8.5).
  In the upstream reply, note that demo media is committed under docs/media/ per
    fork convention, and offer to drop the committed binaries in favor of
    artifact-only delivery (CI-produced downloads) if maintainers prefer — the
    fork-side deliverable remains the embedded media.
```

---

## 10. Constraints and Non-Goals

### Hard Constraints

- **Do NOT commit to `feat/agentic-protocols-generative-ui` directly.** All reconciliation work happens on `reconcile/*` branches.
- **PR-A lands before PR-B.** This is the agreed sequencing per upstream reviewer recommendation.
- **All gate commands must pass** before any PR is submitted upstream.
- **Pull latest `main`** into all branches before beginning reconciliation.
- **Every major feature update ships visual evidence.** A full-quality `.mp4` of the live feature path (canonical), a derived looping `.gif`, and comprehensive annotated screenshots MUST exist under `docs/media/` and be correctly embedded (mp4 as a plain link; gif/png inline with alt text + captions) in both the feature docs and the PR description — for GUI (Track A) and non-GUI (Track B) surfaces alike. See [Section 8](#8-media--visual-evidence-requirements). This is a pass/fail gate, not a follow-up.

### Non-Goals (Explicit Follow-ups)

These items were identified during evaluation but are out of scope for this PR stack:

| Item | Rationale |
|------|-----------|
| `STATE_DELTA` debounce | Performance optimization, not a correctness fix |
| `emit_ui` rate limiting | Performance optimization, not a correctness fix |
| Equal-timestamp `?since=` boundary handling | Edge case requiring separate design discussion |
| WS 4401 e2e assertion on malformed token | Nice-to-have test, not blocking |

### Scope Boundaries

- PR-A touches: `src/cli_agent_orchestrator/services/agui_stream.py`, `src/cli_agent_orchestrator/plugins/events.py`, `cao_pwa/`, `test/test_headless_ci.py`, `mypy.ini`, `tests/__init__.py`, plus `docs/pwa.md` and PR-A media under `docs/media/` (Section 8)
- PR-B touches: `src/cli_agent_orchestrator/a2a/`, `src/cli_agent_orchestrator/agent_card/listener.py`, `src/cli_agent_orchestrator/security/`, `pyproject.toml`, `test/a2a/`, `test/security/`, plus the A2A feature doc and PR-B CLI-walkthrough media under `docs/media/` (Section 8.4)
- No overlap between PR-A and PR-B file scopes (by design). `docs/media/` is a shared, additive location — each PR only adds its own feature-prefixed artifacts, so there is no scope collision.
- **Committed demo media under `docs/media/` is expected and required** (Section 8), following established repo convention; it is not treated as an "unrelated change" or a stray artifact.

---

## 11. Appendix

### Links

| Resource | URL |
|----------|-----|
| Upstream PR #387 | [awslabs/cli-agent-orchestrator#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387) |
| Fork: all open PRs | [plauzy/cli-agent-orchestrator/pulls](https://github.com/plauzy/cli-agent-orchestrator/pulls?q=is%3Apr+is%3Aopen+sort%3Aupdated-desc) |
| PR #9 (original) | [feat/agentic-protocols-generative-ui](https://github.com/plauzy/cli-agent-orchestrator/pull/9) |
| PR #11 (Claude PR-A) | [claude/pr387-agui-core](https://github.com/plauzy/cli-agent-orchestrator/pull/11) |
| PR #12 (Claude PR-B) | [claude/pr387-a2a-hardened](https://github.com/plauzy/cli-agent-orchestrator/pull/12) |
| PR #13 (Kiro PR-B) | [kiro/pr387-a2a-hardened](https://github.com/plauzy/cli-agent-orchestrator/pull/13) |
| PR #14 (Kiro PR-A) | [kiro/pr387-agui-core](https://github.com/plauzy/cli-agent-orchestrator/pull/14) |
| PR #15 (Eval 1) | [docs/pr387-reconciliation](https://github.com/plauzy/cli-agent-orchestrator/pull/15) |
| PR #16 (Eval 2) | [docs/pr387-reconciliation-2](https://github.com/plauzy/cli-agent-orchestrator/pull/16) |
| PR #17 (Eval 3) | [claude/pr387-remediation-reconcile-jlcpmy](https://github.com/plauzy/cli-agent-orchestrator/pull/17) |

### CAO Primitives Reference

| Primitive | Type | Description |
|-----------|------|-------------|
| `handoff` | Sync | Wait for worker completion before proceeding |
| `assign` | Async | Fire-and-forget task dispatch |
| `send_message` | Delivery | Inbox message between agents |
| `cao launch --headless --async` | CLI | Unattended execution mode |
| Profiles | Config | Pin agents to providers via frontmatter |
| Supervisor-worker hierarchy | Architecture | Orchestration over MCP |

### Review Comment Quick Reference

| ID | Severity | Shape | One-liner |
|----|----------|-------|-----------|
| RC-01 | Blocking | PR-B | A2A auth bypass |
| RC-02 | Blocking | PR-B | Unbounded in-memory store |
| RC-03 | Blocking | PR-B | Task id injection |
| RC-04 | Blocking | PR-B | Agent-card listener no auth |
| RC-05 | Important | PR-B | `Task.from_dict` KeyError |
| RC-06 | Important | PR-B | `authlib` wrong dep group |
| RC-07 | Nit | PR-A | Stray `tests/__init__.py` |
| RC-08 | Nit | PR-A | mypy `python_version` mismatch |
| RC-09 | Nit | PR-A | Wrong RFC citation |
| RC-10 | Nit | PR-A | Nested interactive elements |
| RC-11 | Nit | PR-A | Stale docstring |
