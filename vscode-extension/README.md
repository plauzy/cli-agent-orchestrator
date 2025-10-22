# CLI Agent Orchestrator - VSCode Extension

A visual interface for managing multi-agent orchestration with the CLI Agent Orchestrator (CAO).

## Features

- **Session Management**: Create, view, and delete CAO sessions
- **Terminal Management**: Manage multiple agent terminals within sessions
- **Real-time Status Monitoring**: Track agent status (IDLE, PROCESSING, COMPLETED, ERROR, etc.)
- **Interactive Terminal Interface**: Send input to agents and view their output
- **Flow Scheduling**: View and manage scheduled agent flows
- **Multi-Provider Support**: Works with Q CLI and Claude Code providers

## Prerequisites

1. **CAO API Server**: The extension requires the CAO API server to be running
   ```bash
   cao-server
   ```
   The server runs on `http://localhost:9889` by default

2. **CAO Installation**: Install the CLI Agent Orchestrator package
   ```bash
   pip install git+https://github.com/awslabs/cli-agent-orchestrator.git
   ```

3. **tmux**: Required for terminal management
   ```bash
   # macOS
   brew install tmux

   # Ubuntu/Debian
   sudo apt-get install tmux
   ```

## Installation

### From VSIX (Recommended)

1. Build the extension:
   ```bash
   cd vscode-extension
   npm install
   npm run package
   ```

2. Install in VSCode:
   - Open VSCode
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
   - Type "Install from VSIX"
   - Select the generated `.vsix` file

### From Source

1. Clone and install dependencies:
   ```bash
   cd vscode-extension
   npm install
   ```

2. Open in VSCode and press `F5` to launch the Extension Development Host

## Usage

### Opening the Dashboard

- **Command Palette**: `Cmd+Shift+P` → "CAO: Open Dashboard"
- **Activity Bar**: Click the CAO icon in the sidebar

### Creating a Session

1. Click "New Session" in the Sessions panel
2. Select a provider (Q CLI or Claude Code)
3. Optionally specify an agent profile
4. Click "Create"

### Managing Terminals

1. Select a session from the Sessions panel
2. Click "New Terminal" to create a terminal in that session
3. Click on a terminal to view details and interact with it

### Sending Messages to Agents

1. Select a terminal to view its details
2. Enter your message in the input area
3. Click "Send Message" or press `Ctrl+Enter` (Mac: `Cmd+Enter`)

### Viewing Terminal Output

- Toggle between "Full Output" and "Last Message" modes
- Enable "Auto-refresh" to automatically update output every 3 seconds
- Click "Refresh" to manually update the output

### Managing Flows

1. Switch to the "Flows" tab
2. View scheduled flows and their status
3. Enable/disable flows or run them immediately
4. Use the CLI to add new flows: `cao flow add <file>`

## Configuration

Configure the extension in VSCode settings:

```json
{
  "cao.serverUrl": "http://localhost:9889",
  "cao.autoRefreshInterval": 5000,
  "cao.defaultProvider": "q_cli"
}
```

### Settings

- **cao.serverUrl**: URL of the CAO API server (default: `http://localhost:9889`)
- **cao.autoRefreshInterval**: Auto-refresh interval in milliseconds (default: `5000`)
- **cao.defaultProvider**: Default provider for new terminals (`q_cli` or `claude_code`)

## Commands

The extension provides the following commands:

- **CAO: Open Dashboard** - Open the main CAO dashboard
- **CAO: Create Session** - Quick command to create a new session
- **CAO: Launch Agent** - Quick command to launch an agent in an existing session
- **CAO: Refresh Sessions** - Refresh the sessions list

## Architecture

The extension consists of three main components:

1. **Extension Host** (`src/extension.ts`): Node.js process that manages the webview and communicates with the CAO API server

2. **React Webview** (`src/webview/`): User interface built with React, displaying sessions, terminals, and flows

3. **API Client** (`src/webview/services/apiClient.ts`): Axios-based client for communicating with the CAO FastAPI server

### Message Flow

```
User Interaction → Webview (React)
                     ↓ postMessage
              Extension Host (Node.js)
                     ↓ HTTP Request
              CAO API Server (FastAPI)
                     ↓ Response
              Extension Host
                     ↓ postMessage
              Webview (React) → UI Update
```

## Development

### Building

```bash
npm install
npm run compile
```

### Watching for Changes

```bash
npm run watch
```

### Packaging

```bash
npm run package
```

This creates a `.vsix` file that can be installed in VSCode.

### Testing

```bash
npm test
```

## Troubleshooting

### Extension Can't Connect to Server

- Ensure the CAO API server is running: `cao-server`
- Check the server URL in settings matches your server's address
- Verify the server is accessible at the configured URL

### Sessions Not Appearing

- Make sure you have tmux installed
- Check that CAO sessions exist: `tmux ls`
- Try refreshing the sessions list

### Terminal Output Not Loading

- Verify the terminal exists and is running
- Check terminal logs in `~/.aws/cli-agent-orchestrator/logs/terminal/`
- Try manually refreshing the output

## Links

- [CAO GitHub Repository](https://github.com/awslabs/cli-agent-orchestrator)
- [CAO Documentation](https://github.com/awslabs/cli-agent-orchestrator/blob/main/README.md)
- [Report Issues](https://github.com/awslabs/cli-agent-orchestrator/issues)

## License

Apache-2.0
