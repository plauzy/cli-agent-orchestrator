# Quick Start Guide

Get the CLI Agent Orchestrator VSCode extension up and running in 5 minutes.

## Prerequisites Check

Before starting, verify you have:

```bash
# Check tmux version (need 3.3+)
tmux -V

# Check if CAO is installed
cao --version

# Check Node.js version (need 18+)
node --version

# Check npm
npm --version
```

If anything is missing, see the [Installation](#installation) section below.

## Installation

### 1. Install tmux (if not installed)

```bash
bash <(curl -s https://raw.githubusercontent.com/awslabs/cli-agent-orchestrator/refs/heads/main/tmux-install.sh)
```

### 2. Install CLI Agent Orchestrator

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install CAO
uv tool install git+https://github.com/awslabs/cli-agent-orchestrator.git@main --upgrade
```

### 3. Install Agent Profiles

```bash
cao install code_supervisor
cao install developer
cao install reviewer
```

### 4. Build the VSCode Extension

```bash
cd vscode-extension
npm install
npm run build
```

### 5. Install the Extension

```bash
# Package the extension
npm run package

# Install in VSCode
code --install-extension cao-vscode-*.vsix
```

## First Run

### 1. Start CAO Server

Open a terminal and run:

```bash
cao-server
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://localhost:9889
```

Keep this terminal running.

### 2. Open VSCode Extension

In VSCode:
1. Click the CAO icon in the activity bar (left sidebar)
   - Or press `Ctrl+Shift+P` and run "CAO: Open Dashboard"
2. You should see the dashboard with a "Connected" status indicator

### 3. Create Your First Session

1. Navigate to the "Sessions" tab
2. Click "+ New Session"
3. Enter a name: `test-session`
4. Enter agents (optional): `code_supervisor`
5. Click "Create"

### 4. Try Orchestration

1. Navigate to the "Orchestrate" tab
2. Select mode: "Handoff"
3. Select your session: `test-session`
4. Select agent profile: `developer`
5. Enter a message: `List all Python files in the current directory`
6. Click "Execute Handoff"

The extension will create a new terminal with the developer agent and send your message.

### 5. View the Terminal

Back in the "Sessions" tab:
1. Find your session
2. Click the expand arrow (▶) to see terminals
3. Click "Open Terminal" to attach to the tmux session
4. You'll see the agent working on your task

## Common Workflows

### Sequential Code Review

Use **Handoff** mode:

1. Start with code_supervisor agent
2. Handoff to developer to implement feature
3. Handoff to reviewer to review code
4. Results return to code_supervisor

### Parallel Testing

Use **Assign** mode:

1. Start with code_supervisor agent
2. Assign test suite 1 to developer agent 1
3. Assign test suite 2 to developer agent 2
4. Both run in parallel
5. Results sent back when complete

### Interactive Development

Use **Send Message** mode:

1. Create session with developer agent
2. Send initial task message
3. Monitor progress
4. Send follow-up messages as needed
5. Agent processes messages when idle

## Scheduled Flows

### 1. Create a Flow Definition

Create `morning-trivia.md`:

```yaml
---
name: morning-trivia
schedule: "30 7 * * *"  # 7:30 AM daily
agent_profile: developer
---

Give me an interesting world trivia fact.
```

### 2. Add the Flow

```bash
cao flow add morning-trivia.md
```

### 3. Manage via Extension

In the extension:
1. Navigate to "Flows" tab
2. You'll see your flow listed
3. Use buttons to:
   - Run now (test)
   - Enable/disable
   - Remove

## Troubleshooting

### "Disconnected" Status

**Problem**: Extension shows disconnected status

**Solutions**:
```bash
# Check if server is running
ps aux | grep cao-server

# Check if port is in use
lsof -i :9889

# Restart server
pkill -f cao-server
cao-server
```

### "Building webview..." Message

**Problem**: Webview shows build message

**Solution**:
```bash
cd vscode-extension
npm run build:webview
# Reload VSCode window: Ctrl+R
```

### Cannot Create Session

**Problem**: Error creating session

**Solutions**:
```bash
# Check agent profiles are installed
cao install code_supervisor
cao install developer

# Check server logs for errors
# (in terminal running cao-server)
```

### Terminal Won't Open

**Problem**: "Open Terminal" button doesn't work

**Solutions**:
```bash
# Check tmux is installed
tmux -V

# List existing sessions
tmux list-sessions

# Check session exists
cao shutdown --all  # Clean up
# Create new session via extension
```

## Development Mode

For developing the extension:

### 1. Watch Mode

```bash
cd vscode-extension

# Terminal 1: Watch extension
npm run watch:extension

# Terminal 2: Watch webview
npm run watch:webview
```

### 2. Launch Extension Development Host

In VSCode:
1. Open the `vscode-extension` folder
2. Press `F5`
3. A new VSCode window opens with the extension loaded
4. Make changes to code
5. Reload the window: `Ctrl+R`

### 3. Debug

- Extension side: Use VSCode debugger (F5)
- Webview side: Help → Toggle Developer Tools
- Check Console tab for errors
- Check Network tab for API calls

## Next Steps

### Explore Features

- Try all three orchestration modes
- Create custom agent profiles
- Set up scheduled flows
- Experiment with different workflows

### Read Documentation

- [README.md](README.md) - Full feature documentation
- [INTEGRATION.md](INTEGRATION.md) - Integration details
- [Main CAO Docs](../docs/) - CAO server documentation

### Customize

- Create custom agent profiles
- Design custom workflows
- Add your own flows
- Extend the extension (see INTEGRATION.md)

## Example: Full Workflow

Here's a complete example workflow:

### 1. Start Server
```bash
cao-server
```

### 2. Create Session (via extension)
- Name: `feature-development`
- Agents: `code_supervisor`

### 3. Orchestrate Tasks

**Task 1**: Implement feature (Handoff)
- Mode: Handoff
- Profile: developer
- Message: "Implement user authentication with JWT"

**Task 2**: Write tests (Assign)
- Mode: Assign
- Profile: developer
- Message: "Write comprehensive tests for authentication"

**Task 3**: Review code (Handoff)
- Mode: Handoff
- Profile: reviewer
- Message: "Review the authentication implementation"

### 4. Monitor Progress
- Watch terminals in Sessions tab
- Open tmux to see agent work
- Check status indicators

### 5. Cleanup
```bash
cao shutdown --session feature-development
```

## Tips

1. **Keep server running**: The cao-server must run continuously
2. **Use tmux**: Attach to sessions to see agent work in real-time
3. **Start simple**: Begin with single handoff tasks
4. **Monitor status**: Watch terminal status indicators
5. **Check logs**: Server logs show detailed operation info

## Getting Help

- GitHub Issues: https://github.com/awslabs/cli-agent-orchestrator/issues
- Documentation: ../docs/
- Examples: ../examples/

## Keyboard Shortcuts

Within VSCode:
- `Ctrl+Shift+P` → "CAO: Open Dashboard" - Open dashboard
- `Ctrl+R` (in Extension Development Host) - Reload window
- `Ctrl+Shift+I` - Toggle developer tools (webview debugging)

Within tmux:
- `Ctrl+b, d` - Detach from session
- `Ctrl+b, [` - Enter scroll mode
- `Ctrl+b, ]` - Paste buffer

Enjoy using the CLI Agent Orchestrator VSCode Extension!
