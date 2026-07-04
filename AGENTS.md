# AGENTS.md — CLI Agent Orchestrator

> Navigation guide for AI agents working in this codebase.

## Table of Contents

- [Directory Overview](#directory-overview) — Where things live
- [Architecture](#architecture) — Layered design and request flow
- [Key Entry Points](#key-entry-points) — Where execution starts
- [Provider System](#provider-system) — Adding or modifying CLI providers
- [Repo-Specific Patterns](#repo-specific-patterns) — Deviations from defaults
- [Config-Discoverable Info](#config-discoverable-info) — CI, linters, hooks
- [Detailed Documentation](#detailed-documentation) — Deep-dive reference files

## Directory Overview

```
src/cli_agent_orchestrator/
├── api/main.py           # FastAPI server — all HTTP endpoints in one file
├── cli/commands/          # Click CLI — one file per command (launch, install, shutdown, flow, skills, env, info)
├── clients/
│   ├── tmux.py            # TmuxClient — all tmux subprocess calls
│   └── database.py        # SQLAlchemy ORM — terminals, inbox, flows tables
├── mcp_server/server.py   # FastMCP — handoff, assign, send_message, load_skill tools
├── models/                # Pydantic models — Terminal, Session, InboxMessage, Flow, AgentProfile, ProviderType
├── plugins/               # Event-driven plugin system — CaoPlugin base, PluginRegistry, typed events
├── providers/
│   ├── base.py            # BaseProvider abstract class — the interface all providers implement
│   ├── manager.py         # ProviderManager singleton — terminal_id → provider mapping
│   ├── kiro_cli.py        # Default provider — TUI mode with credits/separator patterns
│   ├── claude_code.py     # ❯ prompt, ─ separator, trust/bypass prompt handling
│   ├── codex.py           # › prompt, • bullet format, trust prompt handling
│   ├── q_cli.py           # Green arrow prompt, requires agent_profile
│   ├── gemini_cli.py      # Query box, spinner, MCP registration, policy rules
│   ├── kimi_cli.py        # Input box, status bar, MCP timeout, agent YAML
│   └── copilot_cli.py     # Footer analysis, trust prompts, runtime MCP config
├── services/
│   ├── terminal_service.py  # Central orchestration — terminal lifecycle, skill injection
│   ├── session_service.py   # Session CRUD wrapping terminal_service
│   ├── inbox_service.py     # Watchdog-based message delivery with two-phase idle detection
│   ├── flow_service.py      # Cron scheduling, gate scripts, prompt templates
│   ├── cleanup_service.py   # 14-day retention cleanup
│   └── settings_service.py  # Agent directory config persistence
├── utils/
│   ├── agent_profiles.py    # Profile discovery and parsing from multiple directories
│   ├── skills.py            # Skill validation, loading, catalog building
│   ├── skill_injection.py   # Refresh Q CLI JSON and Copilot agent.md prompts
│   ├── tool_mapping.py      # CAO tool vocabulary → provider-native translation
│   └── terminal.py          # ID generation, wait helpers
├── agent_store/             # Built-in agent profiles (developer.md, reviewer.md, code_supervisor.md)
├── skills/                  # Bundled skill definitions
└── constants.py             # All config: paths, server settings, role defaults, security prompt

web/                         # React + Zustand + Tailwind SPA
├── src/App.tsx              # Root — tabs: Home, Agents, Flows, Settings
├── src/api.ts               # Typed API client for all endpoints
├── src/store.ts             # Zustand store with 10s polling
└── src/components/          # AgentPanel, FlowsPanel, SettingsPanel, TerminalView, OutputViewer, InboxPanel

test/                        # Mirrors src/ structure — unit, integration, e2e
```

## Architecture

Three entry points → shared service layer → clients + providers:

- **MCP Server** calls **API Server** via HTTP (does not import services directly)
- **Services** delegate to **TmuxClient** and **Database** (never call tmux/SQL directly)
- **ProviderManager** is a module-level singleton mapping terminal_id → provider instance
- **Plugins** receive async events from services; failures are logged, never block

## Key Entry Points

| What | Where | Notes |
|------|-------|-------|
| CLI commands | `cli/commands/*.py` | `cao launch`, `cao install`, `cao shutdown`, etc. |
| HTTP API | `api/main.py` | Single file, ~40 endpoints, WebSocket PTY at `/terminals/{id}/ws` |
| MCP tools | `mcp_server/server.py` | `handoff`, `assign`, `send_message`, `load_skill` |
| Flow daemon | `api/main.py:flow_daemon()` | Background asyncio task, 60s loop |

## Provider System

To add a new provider, implement `BaseProvider` (see `providers/base.py`):

1. **Required methods**: `initialize()`, `get_status()`, `get_idle_pattern_for_log()`, `extract_last_message_from_script()`, `exit_cli()`, `cleanup()`
2. **Register** in `ProviderManager.create_provider()` (`providers/manager.py`)
3. **Add enum** to `ProviderType` (`models/provider.py`)
4. **Add tool mapping** in `utils/tool_mapping.py` for restriction enforcement
5. **Add to constants** `PROVIDERS` list (auto-derived from enum)

Each provider's core job: parse tmux terminal output via regex to detect status (IDLE/PROCESSING/COMPLETED/ERROR/WAITING_USER_ANSWER) and extract the agent's last response.

## Repo-Specific Patterns

- **Bracketed paste for input**: `TmuxClient.send_keys_via_paste()` uses `load-buffer` → `paste-buffer` instead of `send-keys` for reliable multi-line input. `paste_enter_count` (default 2) controls how many Enters follow the paste.
- **Two-phase idle detection**: Inbox service reads log tail first (fast), only calls `provider.get_status()` (expensive tmux capture) if idle pattern found.
- **Skill delivery varies by provider**: Kiro uses native `skill://` resources; Claude/Codex/Gemini/Kimi get runtime prompt injection; Q/Copilot get baked prompts at install time. See `RUNTIME_SKILL_PROMPT_PROVIDERS` in `terminal_service.py`.
- **Module-level singletons**: `provider_manager`, `tmux_client`, SQLAlchemy `engine`/`SessionLocal` — no dependency injection framework.
- **Working directory disabled by default**: `CAO_ENABLE_WORKING_DIRECTORY=true` env var required. Paths validated against blocked system directories.
- **Sender ID injection disabled by default**: `CAO_ENABLE_SENDER_ID_INJECTION=true` for auto-injecting supervisor terminal ID into assign messages.

## Config-Discoverable Info

### Build & Package
- **Build system**: hatchling (`pyproject.toml`)
- **Package manager**: uv (not pip)
- **Wheel includes**: `src/cli_agent_orchestrator/web_ui/**` (bundled frontend)

### Code Quality
- **Formatter**: black (line-length 100, target py310)
- **Import sorter**: isort (black profile, line-length 100)
- **Type checker**: mypy (strict mode)
- **Test runner**: pytest with markers: `asyncio`, `integration`, `e2e`, `slow`
- **Default test exclusion**: e2e tests excluded by default (`addopts = -m 'not e2e'`)

### CI (GitHub Actions)
- `ci.yml`: Unit tests (Python 3.10/3.11/3.12 matrix), code quality, Trivy security scan, dependency review
- Provider-specific workflows: Triggered by path changes to individual provider files

### Security
- Trivy scans for HIGH/CRITICAL vulnerabilities
- Dependabot for automated dependency updates
- DNS rebinding protection via `TrustedHostMiddleware`
- WebSocket rejects non-loopback connections

## Detailed Documentation

For deeper analysis, see `.agents/cao/summary/`:

| File | Content |
|------|---------|
| [index.md](/.agents/cao/summary/index.md) | Documentation navigation guide — start here |
| [architecture.md](/.agents/cao/summary/architecture.md) | Layered architecture, design patterns, security model |
| [components.md](/.agents/cao/summary/components.md) | Every component with responsibilities |
| [interfaces.md](/.agents/cao/summary/interfaces.md) | REST API, MCP tools, WebSocket, CLI, plugin hooks |
| [data_models.md](/.agents/cao/summary/data_models.md) | All Pydantic/SQLAlchemy/TypeScript models |
| [workflows.md](/.agents/cao/summary/workflows.md) | Sequence diagrams for all major workflows |
| [dependencies.md](/.agents/cao/summary/dependencies.md) | Full dependency inventory |

## Skills

CAO ships 5 skills that teach agents how to develop, extend, and orchestrate with CAO. They work as both CAO skills (via `cao skills add`) and Claude Code plugin skills (via `--plugin-dir`).

### Available Skills

| Skill | Purpose | Invoke |
|-------|---------|--------|
| `cao-dev` | Run tests, format, type-check, commit with conventional commits | `/cao-skills:cao-dev` |
| `cao-plugin` | Create a new CAO plugin (Python event hooks) | `/cao-skills:cao-plugin` |
| `cao-provider` | Add a new CLI agent provider (tmux adapter) | `/cao-skills:cao-provider` |
| `cao-supervisor-protocols` | Supervisor orchestration: assign, handoff, messaging | `/cao-skills:cao-supervisor-protocols` |
| `cao-worker-protocols` | Worker callback rules and completion reporting | `/cao-skills:cao-worker-protocols` |

### Installation

**As CAO skills** (available to all CAO-managed agents):
```bash
cao skills add ./skills/cao-dev
cao skills add ./skills/cao-plugin
cao skills add ./skills/cao-provider
# Supervisor/worker protocols are auto-seeded from src/ at server startup
```

**As a Claude Code plugin** (available as slash commands):
```bash
claude --plugin-dir ./skills
# Skills become available as /cao-skills:cao-dev, /cao-skills:cao-plugin, etc.
```

**For Kiro CLI**: Skills are delivered via native `skill://` resources when launched through CAO. No manual install needed.

**Verify installation:**
```bash
cao skills list          # List all installed CAO skills
```

### How Dual-Format Skills Work

Each SKILL.md serves both CAO and Claude Code because the systems read different frontmatter fields:

- **CAO** reads only `name` and `description` — silently ignores `allowed-tools`, `user-invocable`
- **Claude Code** reads all fields including `allowed-tools` and `user-invocable`

This means one file works for both systems with zero compatibility issues. When adding a new skill, include both sets of fields.

The `cao-supervisor-protocols` and `cao-worker-protocols` skills live in `src/cli_agent_orchestrator/skills/` (auto-seeded at server startup) and are symlinked into `skills/` for the Claude Code plugin. If symlinks cause issues in distribution, replace them with copies.

### Quality Tests

`test/utils/test_skill_descriptions.py` auto-discovers all skills in both `skills/` and `src/.../skills/` directories. Adding a new skill folder with a valid SKILL.md automatically includes it in quality checks — no manual test updates needed.

## Custom Instructions
<!-- This section is for human and agent-maintained operational knowledge.
     Add repo-specific conventions, gotchas, and workflow rules here.
     This section is preserved exactly as-is when re-running codebase-summary. -->
