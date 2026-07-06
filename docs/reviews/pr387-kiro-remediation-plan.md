# PR #387 remediation plan — execution spec for the Kiro agent

- **Date:** 2026-07-06
- **Input:** `pr387-review-audit-synthesis-2026-07-06.md` (verdicts + ground-truth table G1–G14; read it first — every "why" lives there)
- **Audience:** Kiro (executing agent) and the human reviewing its PRs
- **Target:** close out the review cycle on [awslabs/cli-agent-orchestrator#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387) via a two-PR split — **PR-A** (AG-UI core + generative UI + PWA + mock_cli + OTel, lands first) and **PR-B** (A2A + Agent Card, lands after auth is wired)
- **Working branches:** reshape in place on `feat/agentic-protocols-generative-ui` (PR-A keeps PR #387's number and review history); new branch `feat/a2a-agent-card` for PR-B

Rules of engagement (carried over from the fork's working agreements): every claim in every PR description must be true of that PR's diff; default-off means a test asserts no new listener/route without flags; no PR mixes unrelated subsystems; run the full gate (`black`, `isort`, `mypy`, `pytest`, PWA `npm ci && npm test`) before each push.

---

## Phase A — Reshape PR #387 into PR-A (subtract A2A, fix the diff's own defects)

**A1. Extract the A2A surface to `feat/a2a-agent-card` (branch from the current PR head, then subtract from the PR branch).**
Remove from the PR branch:
- `src/cli_agent_orchestrator/a2a/` (5 files), `src/cli_agent_orchestrator/agent_card/` (5 files)
- `test/a2a/` (6), `test/agent_card/` (7), `test/e2e/test_a2a_roundtrip.py`
- `docs/auth.md` — revert only the A2A/Agent-Card sections added by this PR
- `api/main.py`: the lifespan block wiring the `:9890` listener (~lines 395–460: `CAO_AGENT_CARD_ENABLED` gate, `_agent_card_metadata`, `InMemoryTaskStore`/`InMemoryTaskEventBus` construction, `start_agent_card_listener` call, `app.state.agent_card_listener` + shutdown hook) and the now-unused imports (lines 35–41: `a2a`, `agent_card`)
- `pyproject.toml`: drop `authlib`, `python-multipart`; regenerate `uv.lock`
- `CHANGELOG.md`: remove the "A2A v1.0 transport + signed Agent Card" bullet (it moves to PR-B's changelog)
- Sanity: `git grep -riE 'a2a|agent_card' src/ test/` on PR-A must return only benign historical references (e.g. the "A2A delegation" event-kind name in the AG-UI vocabulary — that's CAO's internal event taxonomy, keep it).

**A2. Fix the dead example (the defect no reviewer caught — G4).**
`examples/cross-provider/data_analyst_gemini_cli.md` declares `provider: gemini_cli`, which doesn't exist. Either delete it, or retarget: rename to `data_analyst_antigravity_cli.md`, set `provider: antigravity_cli`, and verify the front-matter validates against `models/provider.py::ProviderType`. Prefer retarget (keeps the cross-provider example matrix complete). Update `examples/cross-provider/README.md` if it indexes the files.

**A3. Rewrite the PR #387 body.**
- Feature list = exactly what remains in the diff: AG-UI typed-event stream (`/agui/v1/stream`), generative UI (`emit_ui` MCP tool + `POST /agui/v1/emit_ui`, frozen allow-list), standalone PWA (`cao_pwa/`), `mock_cli` provider, opt-in OTel GenAI instrumentation, WS auth (`cao.bearer.<jwt>` subprotocol, 4401/4403), workflow-spec touch-ups.
- Delete: every mention of DAG/swarm/Polecat/Cedar/WAL/policy queue/3-layer cache (G9) and of q_cli/gemini_cli deletion (G2/G3).
- Add: a "Follow-up PRs" section linking the PR-B plan and the hygiene PR (Phase E).

**A4. Dependency hygiene.**
Move the three OTel deps (`opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-grpc`) to `[project.optional-dependencies] otel = [...]`. Guard imports in `telemetry/otel.py` (verify it already no-ops when the SDK is absent — it's opt-in by design; add a `pytest.importorskip`-based test if not). Document `pip install cli-agent-orchestrator[otel]` in `docs/otel-deployment.md`.

## Phase B — PR-A hardening (the accepted review items)

**B-1. Token-parse exceptions → clean 401/4401 (verdict I3, G7).**
- `api/main.py` SSE path (~781): wrap `extract_scopes_from_token(access_token)` in `try/except Exception` → `HTTPException(401, "invalid or expired token")`.
- `_extract_ws_scopes` (~1894–1897): broaden `except HTTPException` → `except Exception: return None` (caller already closes 4401).
- New tests: malformed bearer and expired bearer on `GET /agui/v1/stream` → 401 (not 500); same tokens via WS subprotocol → close code 4401. Reuse the JWT fixtures from the WS-auth test suite.

**B-2. Query-JWT log hygiene (verdict I2, G8).**
- Scrub the token from access logs: either `uvicorn.run(..., access_log=False)` on the main app with app-level request logging that redacts query strings, or (preferred, narrower) a logging filter that masks `access_token=` values on `/agui/v1/stream` lines.
- Docs (`docs/pwa.md` + endpoint docstring): recommend short token TTLs; note the query-param pattern exists because `EventSource` cannot set headers.
- File a follow-up issue for the short-lived single-use ticket handshake (`POST /agui/v1/ticket` with header auth → `?ticket=`), referencing the review. Do **not** build it in PR-A.

**B-3. `_agui_enabled()` wording (nit).**
Keep the `CAO_MCP_APPS_ENABLED` fallback (shared event source is intentional — synthesis §1.4), but rewrite the docstring + `docs/pwa.md` to state it explicitly, and drop/adjust any "no new flags" phrasing in the PR body. Add a parametrized test asserting both enablement paths.

**B-4. De-stub the `?since=` endpoint test (nit).**
In `test/api/test_agui_stream_endpoint.py`, make `_FakeLog.history(**kwargs)` honor `since` (filter the canned events) and assert: request with `since=<t0>` excludes `evt-old`, request without it includes it. This exercises the main.py replay wiring end-to-end.

**B-5. Copilot five (all accepted).**
1. Delete stray `tests/__init__.py` (the real suite is `test/`); confirm nothing imports `tests.*` (`git grep -n 'import tests\|from tests'`).
2. `pyproject.toml` `[tool.mypy] python_version = "3.10"` (match `requires-python = ">=3.10"`); run mypy to catch any 3.11-only typing that slips.
3. `plugins/events.py`: replace the RFC 9114 citation (HTTP/3) with W3C Trace Context (`https://www.w3.org/TR/trace-context/`) for `traceparent`.
4. `cao_pwa/src/components/InstancePicker.tsx`: remove the nested interactive `<button>`-inside-`<button>`; restructure as sibling elements with proper roles; keep the existing component tests green and add an a11y assertion if the suite has one.
5. `test/e2e/test_headless_ci.py`: fix the docstring claiming manual server start (conftest auto-starts it).

**B-6. Docs.**
Fold `docs/generative-ui-implementation-2026-07-04.md` into `docs/pwa.md` (drop the date/status-log framing); fix inbound links from CHANGELOG/README. Strip README/CODEBASE prose reformatting that isn't feature-related.

**B-7. Gate + verify (before push).**
- `uv run black --check . && uv run isort --check . && uv run mypy src/`
- `uv run pytest test/` — expect the prior 40 AG-UI tests plus the new B-1/B-4 tests green
- `cd cao_pwa && npm ci && npm test` (18/18) and the Playwright job if runnable locally
- Default-off probe (regression for AC1): with no env flags, `GET /agui/v1/stream` → 404, `POST /agui/v1/emit_ui` → 404, no `:9890` bind, byte-identical route table
- Redaction probe (AC4): the existing canary-secret test must still pass — it is the strongest evidence in the reply.
- Push to `feat/agentic-protocols-generative-ui`; PR #387 becomes PR-A; post the reply draft (see Phase D) after the push so reviewers see code + response together.

## Phase C — PR-B: A2A + Agent Card, hardened (the blocking items)

**C-1. Auth enforcement (B1, G5).**
- JSON-RPC multiplexes methods over one route, so enforce *per-method after parse*, inside the `rpc()` handler in `a2a/rpc.py`: resolve scopes once per request (reuse `security/auth.py::extract_scopes_from_token` / `get_current_scopes`; honor `is_auth_enabled()`), then require `cao:write` for `task.send`/`task.cancel` and `cao:read` for `task.get`. Failures return JSON-RPC error objects **with matching HTTP status**: 401 (missing/invalid token), 403 (insufficient scope) — don't tunnel auth failures through 200s.
- `a2a/stream.py` SSE + REST routes: standard FastAPI `Depends(require_any_scope(SCOPE_READ, ...))`.
- Fail-closed mount guard in `api/main.py`: if `is_auth_enabled()` is false **and** the effective bind host is non-loopback, refuse to mount the A2A routers (log the reason) — encoding the reviewer's alternative remedy. Loopback + no auth stays allowed (dev ergonomics).
- Docstrings: rewrite `rpc.py:24-25` and `stream.py:21-22` to describe the enforcement that actually exists.

**C-2. Bounded store (B2, G6).**
`InMemoryTaskStore(max_tasks: int = 1000, ttl_seconds: float = 3600)` — env-tunable via `CAO_A2A_MAX_TASKS` / `CAO_A2A_TASK_TTL`. TTL sweep on access (lazy, under the existing lock); on overflow evict oldest *terminal* tasks first; if still full of non-terminal tasks, reject `task.send` with an A2A application error (pick/add the appropriate `A2AErrorCode`). Keep the `TaskStore` Protocol seam intact.

**C-3. Tests.**
Per-method auth matrix (send/get/cancel × no-token/bad-token/read-scope/write-scope → 401/403/200); stream + REST route auth; auth-disabled-loopback still works; mount-guard refusal case; eviction (overflow and TTL) incl. the reject-when-full path; the existing 25-file A2A/agent-card suite stays green.

**C-4. Ship.**
Move the A2A CHANGELOG bullet here; add `[a2a]` optional extra for `authlib`/`python-multipart`; open PR-B referencing #386/#387 and review 4632216702, description limited to what this diff does. Open only when C-1–C-3 are green.

## Phase D — Response draft v2 (posted by the maintainer of the fork, not by Kiro)

`docs/reviews/pr387-agui-response-draft-v2.md` (in this folder) supersedes `baf9d45`'s draft. Deltas from v1 — apply, don't regress:
- **Withdraw** the `### Removed` CHANGELOG concession and the dedicated provider-removal-PR offer (false premise — G2/G3).
- **Insert** the R1 pushback (0 deletions; #353 in merge base) and the G4 counter-offer (we found and fixed the dead gemini example ourselves).
- **Keep** from v1: B1/B2 acceptance with the conditional-severity note, the 157-not-400 correction, the I2 `EventSource` pushback, the I3 fails-closed framing, the inclusive-language attribution correction (now backed by G10 as proof, not a hedge), `.coverage-baseline.json` keep+comment, the Copilot five, and the closing "why keep pushing on AG-UI" section.

## Phase E — Goodwill hygiene PR (small, separate, upstream; defuses R1–R3/R5 permanently)

1. `whitelist` → `allowlist` in `services/audit_log.py` (incl. renaming `AUDIT_EVENT_WHITELIST` → `AUDIT_EVENT_ALLOWLIST` with a module-level alias if anything external imports it), `services/memory_scoring.py`, `services/memory_service.py`; "Master switch" → "Primary switch" in `docs/memory.md`, `docs/mcp-apps.md`.
2. `check_and_send_pending_messages()` → `deliver_pending()` ×4 in `docs/inbox-delivery.md`.
3. CHANGELOG `### Removed` backfill entry under the release that contained #353 (q_cli, gemini_cli) — recorded where the removal actually happened.
4. One-line header comment in `.coverage-baseline.json` (or a README note beside it) marking it as ratchet-floor config.
5. Optional: propose an inclusive-language CI lint (the review noted no gate exists) — separate discussion, not this PR.

## Backlog (fork-side, explicitly NOT part of the CR)

From the Gemini plan, items with a verified gap (G13/G14):
- `execution_mode` badges — interactive vs headless — in `cao_mcp_apps` `AgentStatus.tsx` (+ the `interrupt`/`pause`/`resume` payloads exposure in the UI); requires the backend telemetry field to exist first — verify before building.
- HeaderBar token-consumption/cognitive-load warning (>4 concurrent agents) — present only as fleet counts today (unverified beyond that).
- Short-lived-ticket handshake for the AG-UI stream (filed in B-2).
- Auth0/OAuth 2.1 OBO integration — deferred to the sibling RFC; **not** to be conflated with C-1 (which is plain scope wiring of existing infra).
- L2 construct library + L3 recomposition (Phases 2–3 of the original continuation plan) — sequenced after PR-A merges.

## Sequencing & exit criteria

1. Phase A+B → push → PR #387 (now PR-A) re-review requested; post draft-v2 reply.
2. Phase C in parallel on `feat/a2a-agent-card`; open PR-B when green **and** after PR-A merges (or when reviewers ask to see it — whichever first).
3. Phase E anytime; keep it out of the PR-A/PR-B review threads.
4. **Done when:** PR-A merged; PR-B open with auth + bounds + green matrix; hygiene PR open; reply posted; no unaddressed review thread on #387.
