# awslabs Delta Tracker

Tracks divergence between `plauzy/cli-agent-orchestrator.bak` (Pat's repo) and the
awslabs upstream. Purpose: organize commits for eventual CR submission to awslabs once
techniques have hardened.

**Upstream:** `https://github.com/awslabs/cli-agent-orchestrator`
**Last refreshed:** 2026-05-13

---

## Pat's commits not in awslabs upstream

Candidates for upstream CR submission. Merge commits and plauzy-specific CI changes are pre-marked `not-applicable`.

| SHA | Description | Status | Notes |
|-----|-------------|--------|-------|
| 75acc79 | fix(refinery): route update_terminal_shell_command through submit_sync_or_run | pending | |
| da255e5 | feat(v2.5): merge web-design-system-rules into cao/v2.5 | pending | |
| 8bd01d1 | feat(ci): W6a — python-e2e CI gate + PR template (#35) | pending | |
| f5bb2fc | fix(ws/resize): set window-size=latest before PTY attach to fix CI resize | pending | |
| f2701fe | style: apply black formatting to api/main.py | not-applicable | formatting-only; upstream has its own style pass |
| 202cb80 | fix(ws/resize): make tmux resize reliable across window-size policies | pending | |
| dc95ea9 | fix(test/e2e): detach tmux query from calling TTY to fix CI resize check | pending | |
| 3f24de6 | fix(ci): add pre-flight diagnostics for tmux and mock_cli | pending | |
| 7c5136f | fix(test/e2e): use cao_terminal_mock (mock_cli) in scenario 1 | pending | |
| 0192d53 | fix(test/e2e): use mock_cli in authed_terminal fixture for CI portability | pending | |
| 4feeb5c | feat(ci): W6a — python-e2e CI gate + PR template | not-applicable | superseded by #35 above |
| a6e37df | Merge pull request #34 from plauzy/claude/w5-test-infra | not-applicable | merge commit |
| fb24c7a | feat(test/fixtures): W5 — shared JWT/JWKS/terminal infrastructure | pending | |
| 8b211ff | Merge pull request #33 from plauzy/claude/ship-w4-pr-e3Zpw | not-applicable | merge commit |
| 0d96247 | feat(W4): extend MCP Apps iframe smoke test with --iframe flag | pending | |
| 17669ab | Merge pull request #32 from plauzy/claude/w3-handoff-mock-c6446 | not-applicable | merge commit |
| fa46c8f | feat(test/orchestration): W3 — mock_cli handoff lifecycle test | pending | |
| f379886 | fix(providers/mock_cli): strip bracketed-paste markers in REPL, skip empty lines | pending | |
| 4e10a4e | Merge pull request #29 from plauzy/claude/w3-w8-cao-batch-YJSqm | not-applicable | merge commit |
| bc03a7f | Merge remote-tracking branch 'origin/main' into claude/w3-w8-cao-batch-YJSqm | not-applicable | merge commit |
| 9c2ec49 | Merge pull request #30 from plauzy/claude/mock-cli-provider | not-applicable | merge commit |
| faaa4d0 | feat(providers/mock_cli): add deterministic CLI stub for credential-free CI testing | pending | high value for upstream CI |
| 5adad65 | fix(providers/claude_code): fail loud-named on incompatible envs (Tenet #1) | pending | |
| 4783a65 | Merge pull request #28 from plauzy/claude/ci-black-fix-and-batch-prep | not-applicable | merge commit |
| 5d11039 | docs(plan): respond to PR #28 review — why-first tenet + reusable template | not-applicable | Pat-specific planning doc |
| 5bae6ca | chore(ci): fix black formatting + commit W3-W8 batch plan and provider tenet | not-applicable | Pat-specific planning doc |
| 5dc62da | fix(bump_version): anchor version regex to project line, not mypy | pending | |
| f2035d9 | Merge pull request #26 from plauzy/dependabot/uv/urllib3-2.7.0 | not-applicable | merge commit |
| 96c4b2a | Merge pull request #25 from plauzy/claude/w2-ws-integration-smoke | not-applicable | merge commit |
| f509add | build(deps): bump urllib3 from 2.6.3 to 2.7.0 | pending | dependency bump — check if awslabs has equivalent |
| cdc6087 | Merge pull request #24 from plauzy/claude/resume-pr-23-work-Pydlm | not-applicable | merge commit |
| 511b8b5 | test(e2e): W2 WebSocket auth integration smoke (4 scenarios) | pending | |
| 812881a | Merge pull request #23 from plauzy/claude/continue-cao-development-tvOvJ | not-applicable | merge commit |
| 4b9f84b | docs(test): reference W1 managed cao-server fixtures in test/README.md | pending | |
| 0e8be61 | Merge pull request #22 from plauzy/claude/create-mcp-app-WjylS | not-applicable | merge commit |
| 96d4a74 | chore(mcp-apps): rebuild agent.html bundle for WS subprotocol auth | not-applicable | build artifact |
| d09e0cf | test(fixtures): managed cao-server subprocess fixture (W1) | pending | |
| 4e7206b | Merge pull request #21 from plauzy/claude/create-mcp-app-WjylS | not-applicable | merge commit |
| 6b748d7 | chore(release): 2.5.0a3 — close the alpha cycle | not-applicable | Pat-specific release tag |
| 5a11fc9 | feat(security): WebSocket terminal auth — JWT via subprotocol | pending | |
| a764691 | Merge pull request #20 from plauzy/claude/create-mcp-app-WjylS | not-applicable | merge commit |
| 385cdeb | feat(pwa): L2 standalone dashboard PWA + AG-UI bridge | pending | |
| 08f249b | docs(rfc): import cao-mcp-apps-implementation-plan-2026-05-10-v2 parent RFC | not-applicable | Pat-specific RFC doc |
| 8c07067 | Merge pull request #19 from plauzy/claude/create-mcp-app-WjylS | not-applicable | merge commit |
| 9b887c7 | feat(security): Auth0 for MCP — OAuth 2.1 + scope-based RBAC | pending | |
| d2d540d | Merge pull request #18 from plauzy/claude/create-mcp-app-WjylS | not-applicable | merge commit |
| 4dbf039 | feat(mcp-apps): Phase 4+5 — xterm.js + a11y + 2.5.0a2 release | pending | |
| 574918d | Merge pull request #17 from plauzy/claude/create-mcp-app-WjylS | not-applicable | merge commit |
| f628d1f | Merge pull request #16 from plauzy/claude/create-mcp-app-WjylS | not-applicable | merge commit |
| 1283835 | feat(mcp-apps): Phase 3 — real mutations + AI-native loop | pending | |
| 43c8e3b | feat(mcp-apps): Phase 2 — real state propagation | pending | |
| a1429ad | feat(mcp-apps): add SEP-1865 MCP Apps surface (Phase 1 skeleton) | pending | |
| 3ffd3b7 | Merge pull request #14 from plauzy/claude/docs-refresh-and-examples | not-applicable | merge commit |
| 621da9e | docs: refresh post-PR-#12 — clear stale CI claims, add 3 examples | pending | |
| 893ab4e | Merge pull request #12 from plauzy/claude/init-project-setup-rJgHw | not-applicable | merge commit |
| eaca001 | Merge pull request #11 from plauzy/claude/session-start-hook-VHlRB | not-applicable | merge commit |
| 50fb150 | ci: remove Security Scan job (GHAS not available on this private repo) | not-applicable | plauzy-specific (private repo GHAS constraint) |
| a6c2098 | Merge pull request #10 from plauzy/claude/cao-v2.5-cleanup-7KCis | not-applicable | merge commit |
| 2453a4f | ci: grant actions:read so codeql upload-sarif has telemetry access | not-applicable | plauzy-specific CI fix |
| b567491 | docs: add CLAUDE.md for Claude Code guidance | not-applicable | Pat-specific Claude Code config |
| d13602f | fix(test): use monotonic-relative timestamp for hit_rate_5m prune test | pending | |
| 2548324 | chore: add SessionStart hook for Claude Code on the web | not-applicable | Pat-specific Claude Code hook |
| 2f6246e | ci: surface first test failure with --tb=long --maxfail=1 (DEBUG) | pending | |
| 6df5a69 | chore: gitignore coverage.xml + htmlcov/ | pending | |
| 155a40b | test(cache): poll for L2 entry drop instead of fixed sleep | pending | |
| 82fea91 | style: apply black formatting to v2.5 close-out test files | not-applicable | formatting-only |
| bcc74dc | feat(v2.5): close out all remaining follow-ups + acceptance gaps | pending | |
| a7cdbfd | Merge pull request #9 from plauzy/claude/ship-cao-phase-2-dXRNA | not-applicable | merge commit |
| 7cc2497 | fix(cli): drop importlib.resources.abc import for Python 3.10 compat | pending | good upstream fix |
| 50281fb | docs(zellij): bootstrap guide + e2e smoke + flip Phase 2 to shipped | pending | |
| ef51195 | feat(api): wire Zellij bridge into FastAPI lifespan under env gate | pending | |
| 42f4aa9 | feat(cli): add `cao zellij` group (install / start / tail) | pending | |
| eeb846b | Merge pull request #8 from plauzy/dependabot/npm_and_yarn/web/postcss-8.5.14 | not-applicable | merge commit |
| dce1e42 | feat(services): add Zellij hook bridge | pending | |
| 76035f3 | Merge pull request #7 from plauzy/claude/cao-v2.5-unified-synthesis-T2E27 | not-applicable | merge commit |
| 8c66e0c | build(deps-dev): bump postcss from 8.5.8 to 8.5.14 in /web | pending | |
| 49e0382 | build(zellij): add Phase 2 assets + Hatch force-include wiring | pending | |
| bcce310 | Merge pull request #6 from plauzy/claude/cao-v2.5-unified-synthesis-T2E27 | not-applicable | merge commit |
| 3c6811e | docs(v2-5-tasks): mark provider regex fragility tests shipped | not-applicable | v2.5 task tracker — Pat-specific |
| dd2c900 | docs: add operator runbooks for Phase 1/4/5 surfaces | pending | |
| d6343c8 | test(traceparent): pin byte-boundary invariant across all 7 providers | pending | |
| 01ba3d6 | feat(a2a, acp): pluggable executor bridges for task.send + session/prompt | pending | |
| 3a98f86 | feat(cache): wire ThreeLayerCache into FastAPI lifespan + add /cache/stats | pending | |
| 3060fb1 | feat(mcp): migrate _assign_impl through dispatch_task with kill-switch gate | pending | |
| 4b9ce93 | feat(asi): kill-switch operator API + plumb into MCP _handoff_impl | pending | |
| cd5c688 | Merge pull request #5 from plauzy/claude/cao-v2.5-unified-synthesis-T2E27 | not-applicable | merge commit |
| ebac277 | feat: Phase 5 finalization — wire A2A onto :9890 lifespan + CHANGELOG | pending | |
| becea9f | feat(acp): add ACP server scaffolding for Cursor/Zed/Claude Code | pending | |
| 2b469b4 | Merge pull request #4 from plauzy/claude/cao-v2.5-unified-synthesis-T2E27 | not-applicable | merge commit |
| 0a75e61 | feat(web): add AI Manifest fetcher + parser | pending | |
| 64770bb | Merge pull request #3 from plauzy/claude/cao-v2.5-unified-synthesis-T2E27 | not-applicable | merge commit |
| 357b36a | feat(observability): wire Deacon into FastAPI lifespan + dispatch | pending | |
| 6f446f1 | feat(a2a): add SSE stream + REST polling endpoints | pending | |
| e6b8032 | feat(mcp): migrate _handoff_impl through dispatch_task entrypoint | pending | |
| dfe0645 | feat(observability): add AsiSpanProcessor — OTel span → evaluator bridge | pending | |
| 82b1555 | feat(a2a): add A2A v1.0 JSON-RPC endpoint on :9890 | pending | |
| 5fd53fb | feat(observability): add Deacon mitigation handlers | pending | |
| 07fdfe9 | feat(cache): add L2 keep-alive scheduler + ThreeLayerCache orchestrator | pending | |
| 7d1927c | feat(observability): wire Deacon as topology router AsiOracle | pending | |
| 51a8f97 | feat(cache): add L1 (LRU+TTL) + L3 (SQLite) cache primitives | pending | |
| 637e090 | feat(observability): add Deacon ASI evaluator | pending | |
| 080be28 | docs(v2-5): add canonical plan + task tracker; refresh architecture status | not-applicable | Pat-specific planning docs |
| 54831ac | Merge pull request #1 from plauzy/claude/cao-v2.5-unified-synthesis-T2E27 | not-applicable | merge commit |
| 9aec6f8 | feat(orchestration): add high-level dispatch entrypoint wiring all Phase 3 primitives | pending | |
| e510939 | docs(v2.5): document Phase 1 foundation; flag-flip annotation | pending | |
| 675e82e | test(benchmarks): held-out topology-router improvement benchmark | pending | |
| d92f3f8 | feat(orchestration): add hybrid hierarchical-cluster topology | pending | |
| 1de5db8 | feat(orchestration): add Polecat swarm dispatch with Refinery synthesis | pending | |
| 4b00398 | feat(orchestration): add git worktree manager + Polecat spawn/teardown | pending | |
| 1b46553 | feat(tools): add read_only=True filter for Polecat sandbox provisioning | pending | |
| 33054ff | feat(refinery): add single-threaded write queue with policy + Rule-of-Two | pending | |
| 073a991 | feat(orchestration): add AdaptOrch topology router with ASI/budget feedback | pending | |
| e2343fe | feat(orchestration): add TaskDAG + AdaptOrch feature extraction | pending | |
| 9a96813 | feat(ext-apps): add SEP-1865 topology widget + SSE event bus | pending | |
| a380802 | feat(agent-card): publish signed Agent Card on dedicated :9890 listener | pending | |
| 39089ad | feat(persistence): add materialized index + WAL replay on boot | pending | |
| ca99b97 | feat(persistence): add WAL writer in shadow mode | pending | |
| 8dc33e6 | feat(telemetry): thread W3C traceparent through CaoEvent + InboxMessage | pending | |
| 44b2fef | ci: drop dependency-review job (requires GHAS, not enabled here) | not-applicable | plauzy-specific CI constraint |
| 3d2df0a | ci: don't block PRs on GHAS-gated checks (sarif upload, dependency-review) | not-applicable | plauzy-specific CI constraint |
| 24be628 | feat(telemetry): emit execute_tool spans from MCP tools + register OtelSidecarPlugin | pending | |
| 119763c | feat(telemetry): add OTel GenAI scaffolding (no-op by default) for v2.5 | pending | |
| a43a8e0 | docs: add web/CLAUDE.md design-system rules for Figma integration | not-applicable | Pat-specific Claude Code config |

---

## awslabs commits not in this repo

| SHA | Description | Relevance | Notes |
|-----|-------------|-----------|-------|
| acb78e6 | build(deps): bump authlib from 1.6.11 to 1.6.12 (#236) | high | Security/dependency update — pull this in before submitting any CRs to avoid conflicts |

---

## Maintenance

1. Run `scripts/update-delta.sh` — it prints both sides of the delta, then self-cleans the remote.
2. Copy the output into the tables above, preserving existing `Status` and `Notes` annotations.
3. Update **Last refreshed** date at the top.

## CR readiness criteria

A commit is ready for upstream submission when:
- Stable in Pat's repo for ≥ 2 weeks with no regressions
- Tests cover the new behavior (unit + integration)
- `mypy` passes in strict mode
- The commit is self-contained (rebased or cherry-pickable cleanly)
