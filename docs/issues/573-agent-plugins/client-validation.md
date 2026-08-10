# Client validation — measured evidence

Evidence log for #573 AC2's foreign-client question: can a compatible client install
`agent-plugin/cao` and reach its skills and `cao-ops` tools? Each client below was measured
live against a real package tree — nothing here is inferred from documentation. The method is
the same five-row matrix per client so results stay comparable; the Antigravity run also used
binary-string inspection of `agy` itself to locate its expected filenames before probing.

Method note: "protocol-level" means the `cao-ops` server was driven directly over MCP stdio
(spawn the exact `mcp.json` command, then `initialize` → `tools/list` → `tools/call`);
"runtime-level" means the client's own plugin runtime mounted the server. Protocol-level
evidence is client-agnostic — the command line under test is identical for every client.

## Claude Code (2.1.226) — verified, runtime-level

| Surface | Measured behavior |
| --- | --- |
| `skills/` discovery | Works on the untouched portable layout |
| Package identity | Read only from `.claude-plugin/plugin.json`; root `plugin.json` not consulted. Marketplace installs tolerate its absence (the entry supplies identity); strict `claude plugin validate` fails without it: *"No manifest found in directory. Expected .claude-plugin/marketplace.json or .claude-plugin/plugin.json"* |
| MCP servers | Read only from a root `.mcp.json`; portable `mcp.json` not consulted. The `mcpServers` shape (including `type: "stdio"`) is accepted as-is |
| Bridge cost | Two generated files (`.claude-plugin/plugin.json`, `.mcp.json`) |
| `cao-ops` reachable | **Runtime-level.** With the overlay, the package installs from a marketplace and Claude Code mounts it natively: all four skills registered, all 11 `cao-ops` tools live in-session with the server's instructions loaded — zero manual configuration. Protocol-level also verified against the published `cli-agent-orchestrator==2.4.1` pin: structured error naming operation + cause with no `cao-server` (Requirement 20), `{"success":true,"sessions":[]}` with one running |

With the overlay present, strict `claude plugin validate` passes (one optional-author warning).

## Antigravity CLI (1.1.11) — verified, install-level

| Surface | Measured behavior |
| --- | --- |
| `skills/` discovery | **Works on the untouched portable layout** — `agy plugin install <dir>` on the pure package reports `✔ skills: 4 processed` |
| Package identity | **Read from the portable root `plugin.json`** — the pure package (no overlay anywhere) installs as `cao`, named from the manifest, not the directory. Closest-to-native Agent Plugins behavior of any measured client |
| MCP servers | Read only from a root `mcp_config.json` (the binary's own help: *"MCP Servers defined in `plugins/<name>/mcp_config.json`"*). Neither the portable `mcp.json` nor Claude Code's `.mcp.json` nor a `mcpServers` manifest field is consulted. A byte-copy of `mcp.json` as `mcp_config.json` reports `✔ mcpServers: 1 processed` (`$schema` key tolerated) |
| Bridge cost | One generated file (`mcp_config.json`) |
| `cao-ops` reachable | **Install-level** (`✔ mcpServers: 1 processed`; the package lands verbatim under `~/.gemini/config/plugins/cao/` and `agy plugin list` records the import). Runtime tool invocation requires Google sign-in, unavailable in the verification environment — an honest gap, not a failure. Protocol-level proof carries over unchanged: the command `agy` would spawn is the identical `uvx --from cli-agent-orchestrator==2.4.1 cao-ops-mcp-server` already exercised end-to-end |

Also measured: `agy plugin validate <dir>` accepts the portable package; `agy plugin
uninstall`/`enable`/`disable` behave as documented; `agy plugin import claude` exists
(cross-import from an existing Claude Code installation) but was not needed here.

## What this means for AC2

Both measured clients reach the package's skills, and each needed at most a filename bridge for
MCP — now generated into the packages and drift-guarded (`scripts/build_agent_plugin.py`), so
`cao plugin`-style consumers, Claude Code, and Antigravity all install the same committed tree.
Neither client is among the clients #573 names (Kiro, VS Code, Cursor, GitHub Copilot,
ChatGPT/Codex), so AC2's letter still needs a run in one of those; the matrix above is the
template. The remaining runtime gap for Antigravity — an authenticated session invoking a
`cao-ops` tool — needs a signed-in `agy`, and is the one row a follow-up run should fill in.
