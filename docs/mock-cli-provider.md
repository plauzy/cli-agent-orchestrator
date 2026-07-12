---
created_by: Claude Opus 4.7
model: claude-opus-4-7
---

# mock_cli provider — credential-free orchestration testing

## Why this exists

The other CAO providers (`claude_code`, `kiro_cli`, `codex`, `kimi_cli`, `copilot_cli`, `opencode_cli`) all wrap real coding-CLI binaries that need real authentication — Anthropic API keys, Google OAuth, AWS SSO, etc. That auth model is right for production but blocks two classes of work in CI:

1. **Fork CI cannot access secrets.** GitHub Actions running in a fork can't read `secrets.ANTHROPIC_API_KEY` or equivalent. Any test that hits a real CLI is gated to the upstream `main` branch (see `.github/workflows/test-claude-code-provider.yml`'s `if: github.ref == 'refs/heads/main' || github.event_name == 'workflow_dispatch'`). Contributors opening a PR from a fork get no end-to-end signal on their orchestration-layer changes.
2. **Real CLIs are slow, non-deterministic, and expensive.** Even with credentials, running a real model in CI burns real dollars, varies between runs, and adds 10–60s per terminal lifecycle. Orchestration logic — handoffs, the inbox watchdog, multi-provider sessions — doesn't need a real model; it just needs *something* that behaves like a CLI agent on the terminal-state contract.

`mock_cli` fills that gap. It's a tiny bash binary plus a thin provider that together let CAO drive a deterministic "agent" through the full lifecycle (initialize → IDLE → receive input → PROCESSING → COMPLETED → respond, plus ERROR injection). No auth, no network, no flakes, no cost.

## Design

Two components:

**1. `test/providers/fixtures/bin/mock_cli`** — a ~60-line bash REPL.

- Prints a banner (`MockCli ready.`), prints the prompt char `❯ `, reads stdin.
- On each input line: sleeps `--delay-ms` (default 50ms), echoes `> MOCK: <input>`, reprints the prompt.
- Magic strings for failure-mode injection:
  - `/exit` or `/quit` → clean exit with `goodbye`
  - `__mock_error__` → emit `ERROR: mock failure injected` (drives state to ERROR)
  - `__mock_sleep_<N>` → sleep N seconds (lets tests exercise long-PROCESSING paths)
- Not on PATH outside pytest. `test/conftest.py` prepends the fixture bin dir to `PATH` at module-load time so `shlex.join(["mock_cli", ...])` resolves.

**2. `src/cli_agent_orchestrator/providers/mock_cli.py`** — a ~95-line provider.

- Subclasses `BaseProvider`.
- `initialize()` waits for shell → spawns `mock_cli --delay-ms N` via `tmux_client.send_keys` → waits for IDLE/COMPLETED.
- `get_status()` strips ANSI then pattern-matches:
  - `ERROR: mock failure injected` present → ERROR
  - no `❯ ` visible → PROCESSING
  - `> MOCK:` + `❯ ` present → COMPLETED
  - just `❯ ` → IDLE
- `extract_last_message_from_script()` returns the payload of the last `> MOCK: <text>` line.
- Registered in `ProviderType.MOCK_CLI = "mock_cli"` and `ProviderManager.create_provider()` like any other provider.

That's it. No model API, no settings.json mangling, no auth flow, no PATH lookup in production.

## What this unlocks

Orchestration-layer tests that previously needed a real provider can now run in fork CI without secrets:

- **Handoff lifecycle** — spawn → send → wait for COMPLETED → extract → exit, all the way through `terminal_service`.
- **Assign + callback** — spawn → send with callback instructions → return immediately → exercise `send_message` flush via inbox.
- **Inbox watchdog** — send to busy receiver → assert PENDING → mock IDLE transition → assert flush.
- **Multi-provider sessions** — spawn two `mock_cli` workers + one `mock_cli` supervisor → assert message routing across the session.
- **Flow scheduling** — APScheduler-driven cron flows can hit mock terminals without burning real model calls.

## Boundaries

- **Production code never sees `mock_cli`.** The binary isn't installed to PATH outside pytest. The provider is registered but inert unless someone explicitly passes `--provider mock_cli`.
- **It doesn't validate provider correctness.** Real CLIs change between versions; the captured-fixture replay tests in `test/providers/fixtures/*_output.txt` are what catches regex drift for the real providers. `mock_cli` validates the *orchestrator's* behavior, not the providers'.
- **It still uses real tmux and a real subprocess.** This is intentional — the unit tests that just mock `tmux_client.get_history` already exist; `mock_cli` enables the next layer up (tests that exercise real tmux + real subprocess + the inbox/watchdog wiring) at zero auth cost.

## CI strategy summary

| Tier | Auth needed | Runs in fork PRs | Tooling |
|---|---|---|---|
| Unit | None | ✅ | `unittest.mock` of `tmux_client` + captured fixture `.txt` files |
| **Orchestration (this PR enables)** | **None** | **✅** | **`--provider mock_cli` + real tmux + real subprocess** |
| Integration | Real CLI | ❌ (main only) | Gated workflow job + `pytest.mark.integration` |
| E2E | Full stack | ❌ (manual) | Default `addopts = -m 'not e2e'` skip; `pytest -m e2e` to opt in |

## Insights from the session that produced this

This work followed PR #29 (the named-failure detection fix for the `claude_code` provider under `CLAUDE_CODE_REMOTE=true`). Building on top of that required a credential-free way to spawn terminals for the W3-W8 orchestration batch. `mock_cli` is that primitive.

Constraints that shaped the design:

- **awslabs CONTRIBUTING.md asks for an issue first** on significant work. Open an issue before the upstream PR for this provider; reference it in the PR body. The recent contributor pattern (`anilkmr-a2z`, `patricka3125`) suggests reasonably quick maintainer response.
- **Never add `ANTHROPIC_API_KEY` (or any provider secret) to a workflow file**, even gated, even on `main`, even as a doc example. The only credential the existing workflows touch is `CODECOV_TOKEN` (a public-coverage upload). Match that posture.
- **The `pytest.mark.integration` + workflow `if:` clause pattern is canonical** for gating "needs real auth" tests. `mock_cli` makes that gate apply to *fewer* tests by absorbing the orchestration-layer surface into tier-1 (unit-equivalent) CI.
- **The OAuth-FD problem in `claude_code` is provider-specific.** Kiro (AWS SSO/Builder ID, cached on disk) and Gemini (OAuth or `GEMINI_API_KEY`, cached in `~/.gemini/`) don't share Claude Code's managed-host file-descriptor passing — they survive tmux spawn natively. For real-CLI dev iteration *with* auth, prefer those providers, or pre-warm `~/.claude/.credentials.json` with one interactive `claude` run.
- **For your own dev loop (where you do want real auth):** prefer `direnv` + a gitignored `.envrc`, or `op run --env-file=... -- uv run cao-server`, over `~/.zshrc` exports. Both keep secrets off disk and out of shell history.

## Resume prompt for the next session

When you start a new session after merging the PR that introduces this provider, paste this in as your first message:

```
Context: the PR that added the mock_cli provider just merged
(in this repo: src/cli_agent_orchestrator/providers/mock_cli.py +
test/providers/fixtures/bin/mock_cli + docs/mock-cli-provider.md).

Goal: build out W3-W8 — orchestration-layer tests that exercise the
full handoff / assign / send_message / inbox-watchdog lifecycle using
--provider mock_cli, with zero credentials, runnable in fork CI.

Please:
1. Read docs/mock-cli-provider.md end-to-end.
2. Verify the primitive works locally:
   - test/providers/fixtures/bin/mock_cli --version  (should print "mock_cli 0.1.0")
   - uv run pytest test/providers/test_mock_cli_unit.py -v  (all green)
3. Sketch W3 as a brief plan first (before writing code): the goal is a
   tier-2 "orchestration" test file (test/orchestration/test_handoff_mock.py?)
   that boots cao-server via the existing test/fixtures/cao_server.py
   fixture, spawns a mock_cli terminal, sends a message, waits for
   COMPLETED, extracts the response, and asserts the round-trip.
4. Once W3 design is agreed, implement it as a single small commit.
5. Then plan W4–W8 in one bullet each (without implementing). Likely
   surfaces: async assign + callback, inbox flush on receiver IDLE,
   multi-provider supervisor → worker routing, flow scheduler smoke,
   session cleanup. Confirm the list before implementing.

Hard constraints:
- Zero secrets in any workflow file (even gated). The existing workflows
  use only CODECOV_TOKEN; match that posture.
- Follow the existing tier-1 / integration / e2e split documented in
  docs/mock-cli-provider.md and pyproject.toml's pytest.ini_options.
- Target awslabs/cli-agent-orchestrator upstream when stable. File an
  issue on awslabs first per their CONTRIBUTING.md before the upstream
  PR; iterate locally until ready.
- Black/isort line length 100. Mypy strict on src/. No emojis in code
  or commits.
```
