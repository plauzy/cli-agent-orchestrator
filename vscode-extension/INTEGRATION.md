# VSCode Extension Integration Guide

This document explains how the React webview integrates with VSCode and how to extend the functionality.

## Architecture Overview

The extension follows a client-server architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                        VSCode                                │
│  ┌─────────────────┐              ┌────────────────────┐   │
│  │  Extension      │◄────────────►│  React Webview     │   │
│  │  (TypeScript)   │   Messages   │  (React/TypeScript)│   │
│  └────────┬────────┘              └─────────┬──────────┘   │
│           │                                  │               │
│           │ VSCode API                       │ HTTP         │
│           │                                  │               │
└───────────┼──────────────────────────────────┼───────────────┘
            │                                  │
            │                                  │
            │                                  ▼
            │                          ┌──────────────┐
            │                          │  CAO Server  │
            │                          │ (localhost)  │
            │                          └──────┬───────┘
            ▼                                 │
    ┌──────────────┐                          │
    │    tmux      │◄─────────────────────────┘
    │  Sessions    │
    └──────────────┘
```

## Components

### Extension Side (`src/extension/`)

#### extension.ts
The main entry point for the VSCode extension:

```typescript
export function activate(context: vscode.ExtensionContext) {
  // Register webview provider
  const provider = new CAOWebviewProvider(context.extensionUri);

  // Register commands
  vscode.commands.registerCommand('cao.openDashboard', ...);
}
```

**Key Responsibilities:**
- Activate the extension
- Register webview providers
- Register commands
- Handle extension lifecycle

#### webviewProvider.ts
Manages the webview lifecycle and communication:

```typescript
class CAOWebviewProvider implements vscode.WebviewViewProvider {
  public resolveWebviewView(webviewView) {
    // Set up webview
    // Load HTML
    // Handle messages
  }

  public handleMessage(message, webview) {
    // Process messages from webview
  }
}
```

**Key Responsibilities:**
- Create and configure webview
- Inject HTML with proper CSP
- Handle bi-directional messaging
- Manage webview lifecycle

### Webview Side (`src/webview/`)

#### Component Hierarchy

```
App.tsx
├── SessionManager.tsx
│   └── Session cards with terminals
├── FlowManager.tsx
│   └── Flow cards with controls
├── AgentProfiles.tsx
│   └── Profile cards
└── OrchestrationPanel.tsx
    └── Orchestration form with modes
```

#### API Client (api/caoClient.ts)

Handles all communication with the CAO server:

```typescript
class CAOClient {
  // Session management
  async getSessions(): Promise<Session[]>
  async createSession(name, agents): Promise<Session>

  // Terminal operations
  async getTerminals(sessionId): Promise<Terminal[]>
  async sendMessage(terminalId, message): Promise<void>

  // Orchestration
  async handoff(fromId, profile, message): Promise<Terminal>
  async assign(fromId, profile, message): Promise<Terminal>

  // Flows and profiles
  async getFlows(): Promise<Flow[]>
  async getAgentProfiles(): Promise<AgentProfile[]>
}
```

## Message Protocol

The extension and webview communicate via `postMessage`:

### From Webview to Extension

```typescript
// Error notification
vscode.postMessage({
  type: 'error',
  message: 'Error description'
});

// Info notification
vscode.postMessage({
  type: 'info',
  message: 'Success message'
});

// Open terminal
vscode.postMessage({
  type: 'openTerminal',
  sessionName: 'cao-session-1'
});

// Open file
vscode.postMessage({
  type: 'openFile',
  filePath: '/path/to/file.md'
});
```

### From Extension to Webview

Currently, the extension primarily responds to webview messages rather than initiating communication. Future enhancements could include:

```typescript
// Status updates
webview.postMessage({
  type: 'statusUpdate',
  status: 'connected'
});

// Terminal notifications
webview.postMessage({
  type: 'terminalUpdate',
  terminalId: 'abc123',
  status: 'COMPLETED'
});
```

## CAO Server API

The webview communicates with the CAO server REST API:

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server health check |
| GET | `/sessions` | List all sessions |
| POST | `/sessions` | Create new session |
| GET | `/sessions/{id}` | Get session details |
| DELETE | `/sessions/{id}` | Delete session |
| GET | `/sessions/{id}/terminals` | List session terminals |
| POST | `/sessions/{id}/terminals` | Create terminal |
| GET | `/terminals/{id}` | Get terminal details |
| POST | `/terminals/{id}/messages` | Send message to terminal |
| POST | `/terminals/{id}/handoff` | Handoff to new agent |
| POST | `/terminals/{id}/assign` | Assign task to agent |
| GET | `/agent-profiles` | List agent profiles |
| POST | `/agent-profiles` | Install agent profile |
| GET | `/flows` | List flows |
| POST | `/flows` | Add flow |
| POST | `/flows/{name}/enable` | Enable flow |
| POST | `/flows/{name}/disable` | Disable flow |
| POST | `/flows/{name}/run` | Run flow |
| DELETE | `/flows/{name}` | Remove flow |

### Request/Response Examples

**Create Session**
```javascript
POST /sessions
{
  "name": "my-session",
  "agents": ["code_supervisor", "developer"]
}

Response:
{
  "session_id": "abc123",
  "name": "my-session",
  "created_at": "2024-01-01T00:00:00Z",
  "terminals": []
}
```

**Handoff**
```javascript
POST /terminals/{terminalId}/handoff
{
  "agent_profile": "reviewer",
  "message": "Please review the code changes"
}

Response:
{
  "terminal_id": "def456",
  "agent_profile": "reviewer",
  "status": "BUSY",
  ...
}
```

## Extending the Extension

### Adding a New Component

1. Create component in `src/webview/components/`:

```typescript
import React from 'react';
import { CAOClient } from '../api/caoClient';

interface MyComponentProps {
  client: CAOClient;
}

export const MyComponent: React.FC<MyComponentProps> = ({ client }) => {
  // Component logic
  return <div>My Component</div>;
};
```

2. Add to App.tsx:

```typescript
import { MyComponent } from './components/MyComponent';

// In render:
{activeTab === 'myFeature' && <MyComponent client={caoClient} />}
```

### Adding a New API Method

1. Add method to CAOClient:

```typescript
async myNewMethod(param: string): Promise<MyType> {
  const response = await this.api.post('/my-endpoint', { param });
  return response.data;
}
```

2. Use in component:

```typescript
const handleAction = async () => {
  try {
    const result = await client.myNewMethod('value');
    // Handle result
  } catch (error) {
    vscode.showError(`Failed: ${error.message}`);
  }
};
```

### Adding a New Message Type

1. Update webviewProvider.ts:

```typescript
public async handleMessage(message: any, webview: vscode.Webview) {
  switch (message.type) {
    case 'myNewAction':
      // Handle new action
      await this.handleMyNewAction(message.data);
      break;
    // ... existing cases
  }
}
```

2. Use in webview:

```typescript
import { vscode } from '../utils/vscode';

vscode.postMessage({
  type: 'myNewAction',
  data: { /* action data */ }
});
```

## Styling

The extension uses VSCode CSS variables for theming:

```css
/* Colors */
var(--vscode-foreground)
var(--vscode-editor-background)
var(--vscode-button-background)
var(--vscode-focusBorder)

/* Fonts */
var(--vscode-font-family)
var(--vscode-font-size)
var(--vscode-editor-font-family)
```

This ensures the UI adapts to the user's VSCode theme automatically.

## Build Process

### Development Build

```bash
# Terminal 1: Watch extension TypeScript
npm run watch:extension

# Terminal 2: Watch webview React
npm run watch:webview
```

### Production Build

```bash
npm run build
# Creates:
# - out/extension/extension.js
# - out/webview/webview.js
# - out/webview/index.html
```

### Packaging

```bash
npm run package
# Creates: cao-vscode-0.1.0.vsix
```

## Security Considerations

### Content Security Policy (CSP)

The webview uses a strict CSP:

```html
<meta http-equiv="Content-Security-Policy"
  content="default-src 'none';
  style-src ${cspSource} 'unsafe-inline';
  script-src ${cspSource} 'unsafe-inline';
  connect-src http://localhost:9889;">
```

- `default-src 'none'`: Block all by default
- `style-src`: Allow styles from webview and inline
- `script-src`: Allow scripts from webview and inline
- `connect-src`: Allow connections to CAO server only

### API Authentication

Currently, the CAO server runs locally without authentication. For production use:

1. Implement token-based authentication
2. Store tokens securely using VSCode's SecretStorage API
3. Add authentication headers to API requests

## Testing

### Manual Testing

1. Start CAO server: `cao-server`
2. Press F5 to launch Extension Development Host
3. Open CAO dashboard
4. Test each feature:
   - Create session
   - Launch agents
   - Send messages
   - Manage flows

### Automated Testing

Future enhancements could include:

- Unit tests for components (Jest + React Testing Library)
- Integration tests for API client
- E2E tests for extension functionality

## Troubleshooting

### Webview not loading
- Check browser console (Help → Toggle Developer Tools → Console)
- Verify build output exists in `out/webview/`
- Check CSP errors in console

### API calls failing
- Verify CAO server is running
- Check network tab in developer tools
- Verify server is on http://localhost:9889

### Hot reload not working
- Stop watch processes and restart
- Reload VSCode window (Ctrl+R in Extension Development Host)

## Future Enhancements

Potential improvements:

1. **Real-time Updates**: WebSocket support for live terminal status
2. **Terminal Output**: Embedded terminal output viewer
3. **Agent Chat**: Interactive chat interface with agents
4. **Workflow Builder**: Visual workflow designer
5. **Performance Metrics**: Agent performance tracking
6. **Log Viewer**: Centralized log viewing
7. **Configuration**: Extension settings for server URL, polling intervals
8. **Authentication**: Secure token management
9. **Multi-server**: Support for multiple CAO servers

## Resources

- [VSCode Extension API](https://code.visualstudio.com/api)
- [Webview API](https://code.visualstudio.com/api/extension-guides/webview)
- [React Documentation](https://react.dev)
- [CAO Documentation](../docs/)
