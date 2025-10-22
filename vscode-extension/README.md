# CLI Agent Orchestrator - VSCode Extension

A Visual Studio Code extension providing a rich UI for managing CLI Agent Orchestrator (CAO) sessions, flows, and agent orchestration.

## Features

### 🎯 Session Management
- View all active CAO sessions
- Create new sessions with specified agents
- Monitor terminal status (IDLE, BUSY, COMPLETED, ERROR)
- Open tmux sessions directly from VSCode
- Delete sessions when done

### ⏰ Flow Management
- View scheduled flows with cron expressions
- Enable/disable flows
- Run flows manually
- View flow configurations and prompts
- Monitor next scheduled run times

### 👥 Agent Profiles
- Browse installed agent profiles
- Install new profiles from files or URLs
- View profile configurations
- See descriptions and metadata

### 🎭 Orchestration Panel
Three orchestration modes available:

1. **Handoff** (🔄)
   - Synchronous task transfer
   - Wait for completion and get results
   - Perfect for sequential workflows

2. **Assign** (✨)
   - Asynchronous task spawning
   - Parallel execution
   - Background processing

3. **Send Message** (💬)
   - Direct communication with agents
   - Queued message delivery
   - Multi-turn conversations

## Prerequisites

- Visual Studio Code 1.75.0 or higher
- CLI Agent Orchestrator installed (`cao-server` running)
- tmux 3.3 or higher
- Node.js 18+ (for development)

## Installation

### From VSIX Package
1. Download the `.vsix` file
2. Open VSCode
3. Go to Extensions view (Ctrl+Shift+X)
4. Click "..." menu → "Install from VSIX..."
5. Select the downloaded file

### From Source
```bash
cd vscode-extension
npm install
npm run build
npm run package
code --install-extension cao-vscode-*.vsix
```

## Usage

### Starting CAO Server
Before using the extension, ensure the CAO server is running:

```bash
cao-server
```

The extension will connect to `http://localhost:9889` by default.

### Opening the Dashboard

1. **Activity Bar**: Click the CAO icon in the activity bar
2. **Command Palette**: Press `Ctrl+Shift+P` and run "CAO: Open Dashboard"

### Creating a Session

1. Navigate to the "Sessions" tab
2. Click "+ New Session"
3. Enter a session name
4. Optionally specify initial agents (comma-separated)
5. Click "Create"

### Orchestrating Tasks

1. Navigate to the "Orchestrate" tab
2. Select orchestration mode (Handoff, Assign, or Send Message)
3. Choose a session
4. Select agent profile (for Handoff/Assign) or terminal (for Send Message)
5. Enter your task/message
6. Click "Execute"

### Managing Flows

1. Navigate to the "Flows" tab
2. View all scheduled flows
3. Use controls to:
   - Run flows manually
   - Enable/disable flows
   - Remove flows
4. Add flows via CLI: `cao flow add <flow-file>`

## Development

### Setup
```bash
npm install
```

### Build
```bash
# Build extension and webview
npm run build

# Watch mode for development
npm run watch
```

### Testing
1. Press F5 in VSCode to open Extension Development Host
2. The extension will be loaded in the new window
3. Open the CAO dashboard to test features

### Project Structure
```
vscode-extension/
├── src/
│   ├── extension/          # VSCode extension code
│   │   ├── extension.ts    # Extension entry point
│   │   └── webviewProvider.ts
│   └── webview/            # React application
│       ├── components/     # UI components
│       ├── api/           # API client
│       ├── types/         # TypeScript types
│       ├── utils/         # Utilities
│       ├── App.tsx        # Main React app
│       └── index.tsx      # React entry point
├── media/                 # Icons and assets
├── out/                   # Build output
├── package.json          # Extension manifest
├── tsconfig.json         # TypeScript config
└── webpack.config.js     # Webpack config
```

## Configuration

The extension connects to the CAO server at `http://localhost:9889` by default. This matches the default port used by `cao-server`.

## Troubleshooting

### Extension shows "Disconnected" status
- Ensure `cao-server` is running
- Check that the server is accessible at `http://localhost:9889`
- Try restarting the server

### Webview shows "Building webview..."
- Run `npm run build:webview` in the extension directory
- Reload the VSCode window

### Cannot open terminal
- Ensure tmux is installed and accessible
- Check that the session name is valid
- Verify tmux sessions with `tmux list-sessions`

## Contributing

Contributions are welcome! Please see the main CAO repository for contribution guidelines.

## License

Apache-2.0

## Links

- [CLI Agent Orchestrator](https://github.com/awslabs/cli-agent-orchestrator)
- [Documentation](https://github.com/awslabs/cli-agent-orchestrator/tree/main/docs)
- [Report Issues](https://github.com/awslabs/cli-agent-orchestrator/issues)
