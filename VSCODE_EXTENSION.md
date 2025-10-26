# CLI Agent Orchestrator - VSCode Extension

A comprehensive VSCode extension that provides a visual interface for managing multi-agent workflows using TMUX-based orchestration, built with AWS Cloudscape components.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      VSCode Extension                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐         ┌──────────────────┐                 │
│  │              │         │                  │                 │
│  │   Extension  │◄────────┤  Webview Panel   │                 │
│  │   Host       │         │  (React + AWS    │                 │
│  │  (TypeScript)│         │   Cloudscape)    │                 │
│  │              │         │                  │                 │
│  └──────┬───────┘         └────────┬─────────┘                 │
│         │                          │                           │
│         │                          │                           │
└─────────┼──────────────────────────┼───────────────────────────┘
          │                          │
          │    HTTP/WebSocket        │
          ▼                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              CAO Server (FastAPI - Port 9889)                    │
├─────────────────────────────────────────────────────────────────┤
│  • Session Management                                            │
│  • Terminal Orchestration                                        │
│  • Agent Coordination (Handoff, Assign, Send Message)           │
│  • Flow Scheduling                                               │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TMUX Sessions                                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │ Agent 1  │  │ Agent 2  │  │ Agent 3  │  ...                 │
│  │Terminal  │  │Terminal  │  │Terminal  │                      │
│  └──────────┘  └──────────┘  └──────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

## Features

### 1. **Multi-Panel Dashboard**
- **Session List**: View all active agent sessions and terminals
- **Terminal Viewer**: Real-time output from selected agent terminal
- **Agent Controls**: Launch new agents with different profiles
- **Flow Manager**: Manage scheduled agent workflows

### 2. **Real-Time Monitoring**
- Live updates of agent status (IDLE, BUSY, COMPLETED, ERROR)
- Terminal output streaming
- Session metrics and health checks
- Auto-refresh with configurable intervals

### 3. **Agent Orchestration**
Following multi-agent best practices:
- **Handoff**: Synchronous task delegation with wait-for-completion
- **Assign**: Asynchronous parallel task execution
- **Send Message**: Direct communication between agents

### 4. **AWS Cloudscape UI**
- Professional, accessible AWS-themed interface
- Responsive split-panel layouts
- Consistent design system
- Optimized for developer workflows

### 5. **Dev Container Support**
- Fully containerized development environment
- Pre-configured with all dependencies
- One-command setup
- Consistent across team members

## Directory Structure

```
vscode-extension/
├── package.json                    # Extension manifest
├── tsconfig.json                   # TypeScript config
├── src/
│   ├── extension.ts                # Extension entry point
│   ├── api/
│   │   └── CAOApiClient.ts         # API client for CAO server
│   └── providers/
│       └── CAODashboardProvider.ts # Webview provider
│
└── webview/                        # React application
    ├── package.json
    ├── vite.config.ts
    ├── src/
    │   ├── main.tsx                # React entry point
    │   ├── App.tsx                 # Main app component
    │   ├── types.ts                # TypeScript types
    │   ├── hooks/
    │   │   └── useVSCodeAPI.ts     # VSCode API hook
    │   └── components/
    │       ├── SessionList.tsx     # Session/terminal table
    │       ├── TerminalViewer.tsx  # Terminal output viewer
    │       ├── AgentControls.tsx   # Agent launch controls
    │       └── FlowManager.tsx     # Flow management UI
    └── dist/                       # Built webview assets
```

## Installation and Setup

### Prerequisites

1. **TMUX** (v3.3 or higher)
```bash
bash <(curl -s https://raw.githubusercontent.com/awslabs/cli-agent-orchestrator/main/tmux-install.sh)
```

2. **uv** (Python package manager)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. **Node.js** (v20 or higher)
```bash
# Install via nvm, fnm, or your preferred method
```

### Option 1: Using Dev Container (Recommended)

1. **Open in VSCode with Dev Containers**:
```bash
# Ensure Docker is running
code .
# VSCode will prompt to reopen in container
# Or use Command Palette: "Dev Containers: Reopen in Container"
```

2. **Container will automatically**:
   - Install all dependencies
   - Set up CAO server
   - Build the extension
   - Configure the environment

3. **Start developing**:
   - Press `F5` to launch extension in debug mode
   - The webview will open automatically

### Option 2: Manual Setup

1. **Install CAO**:
```bash
cd /path/to/cli-agent-orchestrator
uv tool install -e .

# Install agent profiles
cao install code_supervisor
cao install developer
cao install reviewer

# Initialize database
cao init
```

2. **Build Extension**:
```bash
cd vscode-extension

# Install extension dependencies
npm install

# Install webview dependencies
cd webview
npm install

# Build webview
npm run build

# Go back to extension root
cd ..

# Compile extension
npm run compile
```

3. **Run Extension**:
```bash
# Open extension in VSCode
code .

# Press F5 to launch Extension Development Host
```

## Development Workflow

### Starting CAO Server

Before using the extension, start the CAO server:

```bash
# Terminal 1: Start CAO server
cao-server

# Output:
# INFO:     Started server process [12345]
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:9889
```

### Using the Extension

1. **Open Dashboard**:
   - Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`)
   - Type: "CAO: Open Agent Orchestrator Dashboard"
   - Or click the "CAO" status bar item

2. **Launch an Agent**:
   - In the dashboard sidebar, select agent profile
   - Click "Launch Agent"
   - Agent will appear in the session list

3. **View Terminal Output**:
   - Click on any terminal in the session list
   - Split panel opens with real-time output
   - Send commands via the input box

4. **Manage Flows**:
   - View scheduled flows in the sidebar
   - Run flows manually with "Run Now"
   - See next scheduled execution time

### Development Commands

```bash
# Extension development
npm run compile          # Compile TypeScript
npm run watch           # Watch mode for TypeScript

# Webview development
cd webview
npm run dev             # Start Vite dev server (http://localhost:5173)
npm run build           # Build for production
npm run preview         # Preview production build

# Testing
npm run lint            # Lint TypeScript
npm run test            # Run tests (if configured)
```

### Hot Reload During Development

1. **Extension Code** (TypeScript):
   - Run `npm run watch` in extension root
   - Press `Cmd+R` / `Ctrl+R` in Extension Development Host to reload

2. **Webview Code** (React):
   - Changes require rebuilding: `cd webview && npm run build`
   - Then reload Extension Development Host

## Configuration

### Extension Settings

Configure via VSCode settings (`settings.json` or UI):

```json
{
  "cliAgentOrchestrator.serverUrl": "http://localhost:9889",
  "cliAgentOrchestrator.autoRefresh": true,
  "cliAgentOrchestrator.refreshInterval": 2000
}
```

- **serverUrl**: CAO server endpoint (default: `http://localhost:9889`)
- **autoRefresh**: Enable automatic status updates (default: `true`)
- **refreshInterval**: Update interval in milliseconds (default: `2000`)

## UI Components Guide

### SessionList Component

Displays all active terminals across sessions with:
- Session name and agent profile
- Real-time status indicators
- Created/updated timestamps
- Actions (View, Delete)

**Key Features**:
- Sortable columns
- Single-selection mode
- Status badges (Idle, Busy, Completed, Error)
- Collection preferences

### TerminalViewer Component

Shows detailed terminal information:
- **Output Tab**: Real-time terminal output
- **Info Tab**: Terminal metadata
- **Input Box**: Send commands to agent

**Key Features**:
- Auto-scrolling output
- Syntax-highlighted terminal view
- Input disabled when agent is busy
- Health check indicators

### AgentControls Component

Launch new agents:
- Select from available profiles
- One-click launch
- Profile descriptions

**Available Profiles**:
- **Code Supervisor**: Coordinates multi-agent workflows
- **Developer**: Implements features and fixes
- **Reviewer**: Reviews code and provides feedback

### FlowManager Component

Manage scheduled workflows:
- View all flows
- See schedule (cron format)
- Check next run time
- Manually trigger flows

## Multi-Agent Workflow Patterns

### 1. Handoff (Sequential)

**Use Case**: Task requires sequential steps with results

```typescript
// Supervisor delegates to specialist, waits for completion
await apiClient.handoff(
  supervisorTerminalId,
  'developer',
  'Implement authentication feature based on spec.md'
);
// Returns when developer completes task
```

**UI Flow**:
1. Supervisor terminal shows "Busy"
2. New developer terminal created
3. Developer works on task
4. Developer completes, terminal closes
5. Supervisor receives results, continues

### 2. Assign (Parallel)

**Use Case**: Independent tasks can run simultaneously

```typescript
// Supervisor spawns multiple workers in parallel
const tasks = [
  apiClient.assign(supervisorId, 'developer', 'Write unit tests'),
  apiClient.assign(supervisorId, 'developer', 'Update documentation'),
  apiClient.assign(supervisorId, 'reviewer', 'Review PR #123')
];

// All run in parallel
await Promise.all(tasks);
```

**UI Flow**:
1. Multiple terminals created simultaneously
2. All show "Busy" status
3. Work progresses in parallel
4. Workers send results back to supervisor
5. Supervisor synthesizes final output

### 3. Send Message (Coordination)

**Use Case**: Ongoing communication between agents

```typescript
// Direct message to specific agent
await apiClient.sendMessage(
  receiverTerminalId,
  senderTerminalId,
  'Please review the changes in the feature branch'
);
```

**UI Flow**:
1. Message queued in receiver's inbox
2. Delivered when receiver is idle
3. Receiver processes message
4. Can respond with another send_message

## Troubleshooting

### Extension Not Loading

1. **Check CAO Server**:
```bash
# Verify server is running
curl http://localhost:9889/health

# Expected output: {"status":"healthy"}
```

2. **Check Extension Logs**:
   - Open Output panel (`Cmd+Shift+U` / `Ctrl+Shift+U`)
   - Select "CLI Agent Orchestrator" from dropdown

3. **Rebuild Extension**:
```bash
cd vscode-extension
npm run compile
cd webview
npm run build
```

### Webview Not Displaying

1. **Check Browser Console**:
   - Open webview
   - Right-click → "Inspect"
   - Check Console for errors

2. **Verify Webview Build**:
```bash
cd vscode-extension/webview
ls -la dist/
# Should contain: index.js, index.css
```

3. **Check CSP Errors**:
   - Content Security Policy might block resources
   - Check `CAODashboardProvider.ts` CSP settings

### Terminals Not Updating

1. **Check Auto-Refresh**:
```json
{
  "cliAgentOrchestrator.autoRefresh": true,
  "cliAgentOrchestrator.refreshInterval": 2000
}
```

2. **Manually Refresh**:
   - Reload webview: `Cmd+R` / `Ctrl+R`
   - Restart extension host

3. **Check Network**:
   - Verify CAO server is reachable
   - Check firewall settings

### Agent Launch Fails

1. **Verify Agent Profiles Installed**:
```bash
cao install code_supervisor
cao install developer
cao install reviewer

# List installed profiles
ls ~/.aws/cli-agent-orchestrator/agent-store/
```

2. **Check TMUX**:
```bash
# Verify TMUX is installed
tmux -V

# List active sessions
tmux list-sessions
```

3. **Check Logs**:
```bash
# CAO server logs
tail -f ~/.aws/cli-agent-orchestrator/logs/cao-server.log

# Terminal logs
tail -f ~/.aws/cli-agent-orchestrator/logs/terminal-<id>.log
```

## Best Practices

### 1. Agent Design
- Start with single agent before multi-agent
- Use handoff for sequential workflows
- Use assign for parallel tasks
- Provide complete context to subagents

### 2. UI Interaction
- Monitor agent status before sending input
- Use split panel for detailed terminal view
- Leverage flows for recurring tasks
- Clean up completed terminals regularly

### 3. Performance
- Limit auto-refresh interval for many agents
- Use flows for scheduled tasks
- Monitor resource usage in large deployments

### 4. Security
- Run CAO server on localhost only
- Use authentication for production deployments
- Regularly update dependencies
- Review agent logs for issues

## Contributing

### Adding New Components

1. **Create Component**:
```typescript
// vscode-extension/webview/src/components/MyComponent.tsx
import { Container, Header } from '@cloudscape-design/components';

export function MyComponent() {
  return (
    <Container header={<Header>My Component</Header>}>
      {/* Component content */}
    </Container>
  );
}
```

2. **Import in App**:
```typescript
// vscode-extension/webview/src/App.tsx
import { MyComponent } from './components/MyComponent';
```

3. **Build and Test**:
```bash
cd webview
npm run build
cd ..
npm run compile
# Press F5 to test
```

### Adding API Endpoints

1. **Update API Client**:
```typescript
// vscode-extension/src/api/CAOApiClient.ts
async myNewEndpoint(param: string): Promise<MyType> {
  const response = await this.client.post('/my-endpoint', { param });
  return response.data;
}
```

2. **Add Message Handler**:
```typescript
// vscode-extension/src/providers/CAODashboardProvider.ts
case 'myNewCommand':
  const result = await this._apiClient.myNewEndpoint(message.param);
  webviewView.webview.postMessage({
    command: 'myNewResult',
    data: result
  });
  break;
```

3. **Use in Webview**:
```typescript
// vscode-extension/webview/src/components/MyComponent.tsx
const handleAction = () => {
  sendMessage({ command: 'myNewCommand', param: 'value' });
};
```

## Packaging and Distribution

### Build VSIX Package

```bash
# Install vsce
npm install -g @vscode/vsce

# Package extension
cd vscode-extension
vsce package

# Output: cli-agent-orchestrator-vscode-0.1.0.vsix
```

### Install VSIX

```bash
# Via command line
code --install-extension cli-agent-orchestrator-vscode-0.1.0.vsix

# Or in VSCode:
# Extensions → ... menu → Install from VSIX
```

### Publish to Marketplace

```bash
# Create publisher account at https://marketplace.visualstudio.com

# Login
vsce login <publisher-name>

# Publish
vsce publish
```

## Resources

- [CAO Documentation](../README.md)
- [AWS Cloudscape Components](https://cloudscape.design/)
- [VSCode Extension API](https://code.visualstudio.com/api)
- [Multi-Agent Best Practices](../docs/multi-agent-practices.md)

## License

Apache-2.0 License - see [LICENSE](../LICENSE)
