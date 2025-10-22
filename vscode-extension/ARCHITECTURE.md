# Architecture Documentation

## Overview

The CLI Agent Orchestrator VSCode Extension is a sophisticated webview-based interface that provides visual management of CAO sessions, agents, flows, and orchestration patterns. The extension is built using:

- **Frontend**: React 18 with TypeScript
- **Backend**: VSCode Extension API (TypeScript)
- **Communication**: REST API via axios + VSCode message passing
- **Build**: Webpack + TypeScript compiler
- **Styling**: CSS with VSCode theme variables

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           VSCode Window                              │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                      Activity Bar                               │ │
│  │                    [CAO Icon] ◄─── User clicks                  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                              │                                        │
│                              ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                     Webview Panel                               │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │              React Application                            │  │ │
│  │  │  ┌────────┬─────────┬──────────┬────────────────┐       │  │ │
│  │  │  │Sessions│  Flows  │ Profiles │ Orchestration  │       │  │ │
│  │  │  └────────┴─────────┴──────────┴────────────────┘       │  │ │
│  │  │                                                           │  │ │
│  │  │  Components:                                              │  │ │
│  │  │  • SessionManager    - Manage CAO sessions               │  │ │
│  │  │  • FlowManager       - Manage scheduled flows            │  │ │
│  │  │  • AgentProfiles     - Browse agent profiles             │  │ │
│  │  │  • OrchestrationPanel - Execute orchestration patterns   │  │ │
│  │  │                                                           │  │ │
│  │  │  API Client (CAOClient):                                 │  │ │
│  │  │  • HTTP client for CAO server                            │  │ │
│  │  │  • Axios-based REST communication                        │  │ │
│  │  └───────────────────────┬───────────────────────────────────┘  │ │
│  │                          │                                       │ │
│  │                          │ postMessage                           │ │
│  │                          ▼                                       │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │         VSCode Webview Provider                           │  │ │
│  │  │  • Handle webview lifecycle                               │  │ │
│  │  │  • Process messages from React app                        │  │ │
│  │  │  • Trigger VSCode actions (open terminal, show messages)  │  │ │
│  │  └───────────────────────┬───────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                              │                                        │
│                              │ VSCode API                             │
│                              ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                  VSCode Terminal                                │ │
│  │              (tmux session attachment)                          │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               │ HTTP (axios)
                               ▼
                    ┌────────────────────┐
                    │    CAO Server      │
                    │  localhost:9889    │
                    │                    │
                    │  • REST API        │
                    │  • Session mgmt    │
                    │  • Flow scheduling │
                    │  • Orchestration   │
                    └─────────┬──────────┘
                              │
                              │ tmux protocol
                              ▼
                    ┌────────────────────┐
                    │   tmux Sessions    │
                    │                    │
                    │  • Agent terminals │
                    │  • Session mgmt    │
                    └────────────────────┘
```

## Component Details

### Extension Components

#### 1. extension.ts
**Purpose**: Extension activation and registration

**Responsibilities**:
- Activate extension on command
- Register webview view provider
- Register commands (`cao.openDashboard`)
- Manage extension lifecycle

**Key Code**:
```typescript
export function activate(context: vscode.ExtensionContext) {
  const provider = new CAOWebviewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('cao.dashboard', provider)
  );
}
```

#### 2. webviewProvider.ts
**Purpose**: Webview lifecycle and communication

**Responsibilities**:
- Create and configure webview
- Load HTML with proper CSP
- Handle bi-directional messaging
- Trigger VSCode actions

**Message Handlers**:
- `error` → Show error notification
- `info` → Show info notification
- `openTerminal` → Create terminal with tmux attach
- `openFile` → Open file in editor

### React Components

#### 1. App.tsx
**Purpose**: Main application container

**Features**:
- Tab navigation (Sessions, Flows, Profiles, Orchestrate)
- Server health monitoring
- Tab state management
- Component routing

**State**:
```typescript
- activeTab: 'sessions' | 'flows' | 'agents' | 'orchestrate'
- serverStatus: 'connected' | 'disconnected' | 'checking'
- caoClient: CAOClient instance
```

#### 2. SessionManager.tsx
**Purpose**: Manage CAO sessions and terminals

**Features**:
- List all active sessions
- Create new sessions with agents
- View session terminals
- Expand/collapse session details
- Open tmux sessions
- Delete sessions
- Real-time status updates (3s polling)

**State**:
```typescript
- sessions: Session[]
- loading: boolean
- error: string | null
- showCreateDialog: boolean
- newSessionName: string
- selectedAgents: string[]
- expandedSessions: Set<string>
```

#### 3. FlowManager.tsx
**Purpose**: Manage scheduled flows

**Features**:
- List all flows with schedules
- Enable/disable flows
- Run flows manually
- Remove flows
- View flow configurations
- Show next run time
- Real-time updates (5s polling)

**State**:
```typescript
- flows: Flow[]
- loading: boolean
- error: string | null
```

#### 4. AgentProfiles.tsx
**Purpose**: Browse and install agent profiles

**Features**:
- Grid view of installed profiles
- Install profiles (built-in, file, URL)
- View profile files
- Profile descriptions and metadata

**State**:
```typescript
- profiles: AgentProfile[]
- loading: boolean
- error: string | null
- showInstallDialog: boolean
- installSource: string
```

#### 5. OrchestrationPanel.tsx
**Purpose**: Execute orchestration patterns

**Features**:
- Three modes: Handoff, Assign, Send Message
- Session selection
- Terminal selection (for Send Message)
- Agent profile selection (for Handoff/Assign)
- Message composition
- Interactive help guide

**State**:
```typescript
- mode: 'handoff' | 'assign' | 'send_message'
- sessions: Session[]
- profiles: AgentProfile[]
- selectedSession: string
- selectedTerminal: string
- selectedProfile: string
- message: string
- loading: boolean
```

### API Client

#### CAOClient.ts
**Purpose**: HTTP client for CAO server API

**Methods**:

**Health**:
- `getHealth()` → Check server status

**Sessions**:
- `getSessions()` → List all sessions
- `getSession(id)` → Get session details
- `createSession(name, agents)` → Create new session
- `deleteSession(id)` → Delete session

**Terminals**:
- `getTerminals(sessionId)` → List terminals
- `getTerminal(id)` → Get terminal details
- `createTerminal(sessionId, profile, message)` → Create terminal
- `sendMessage(id, message)` → Send message to terminal
- `getTerminalOutput(id)` → Get terminal output

**Orchestration**:
- `handoff(fromId, profile, message)` → Handoff to agent
- `assign(fromId, profile, message)` → Assign task to agent

**Profiles**:
- `getAgentProfiles()` → List profiles
- `installAgentProfile(source)` → Install profile

**Flows**:
- `getFlows()` → List flows
- `addFlow(definition)` → Add flow
- `removeFlow(name)` → Remove flow
- `enableFlow(name)` → Enable flow
- `disableFlow(name)` → Disable flow
- `runFlow(name)` → Run flow

## Data Models

### Session
```typescript
interface Session {
  session_id: string;
  name: string;
  created_at: string;
  terminals: Terminal[];
}
```

### Terminal
```typescript
interface Terminal {
  terminal_id: string;
  session_id: string;
  agent_profile: string;
  status: 'IDLE' | 'BUSY' | 'COMPLETED' | 'ERROR';
  created_at: string;
  inbox: InboxMessage[];
}
```

### Flow
```typescript
interface Flow {
  name: string;
  schedule: string;        // Cron expression
  agent_profile: string;
  script?: string;
  prompt: string;
  enabled: boolean;
  next_run?: string;
}
```

### AgentProfile
```typescript
interface AgentProfile {
  name: string;
  description?: string;
  path: string;
}
```

## Communication Patterns

### 1. Webview → Extension → VSCode

```
React Component
  │
  │ vscode.postMessage({type: 'openTerminal', ...})
  ▼
WebviewProvider.handleMessage()
  │
  │ vscode.window.createTerminal()
  ▼
VSCode Terminal API
  │
  ▼
tmux attach -t session-name
```

### 2. Webview → CAO Server

```
React Component
  │
  │ client.createSession(...)
  ▼
CAOClient.createSession()
  │
  │ axios.post('/sessions', ...)
  ▼
CAO Server REST API
  │
  ▼
Session created
  │
  ▼
Response → React state update
```

### 3. Polling for Updates

```
useEffect(() => {
  loadSessions();
  const interval = setInterval(loadSessions, 3000);
  return () => clearInterval(interval);
}, []);
```

## Build Pipeline

### Development Build

```
src/extension/*.ts  →  tsc  →  out/extension/*.js
src/webview/*.tsx   →  webpack + ts-loader  →  out/webview/webview.js
src/webview/*.css   →  webpack + style-loader  →  bundled in webview.js
```

### Production Build

```
npm run build
  ├─ npm run build:extension
  │   └─ tsc -p tsconfig.extension.json
  │       └─ out/extension/extension.js
  └─ npm run build:webview
      └─ webpack --mode production
          ├─ out/webview/webview.js (minified)
          └─ out/webview/index.html
```

### Packaging

```
npm run package
  └─ vsce package
      └─ cao-vscode-0.1.0.vsix
          ├─ extension/
          ├─ webview/
          ├─ media/
          └─ package.json
```

## Security Model

### Content Security Policy

The webview enforces strict CSP:

1. **Default deny**: All sources blocked by default
2. **Script sources**: Only webview resources + inline
3. **Style sources**: Only webview resources + inline
4. **Connect sources**: Only localhost:9889
5. **No eval**: Script evaluation disabled

### Resource Loading

All resources loaded via webview URIs:

```typescript
const scriptUri = webview.asWebviewUri(
  vscode.Uri.file(path.join(webviewPath, 'webview.js'))
);
```

### API Security

- **Local only**: Server runs on localhost
- **No authentication**: Currently trust-based (local server)
- **Future**: Token-based auth via VSCode SecretStorage

## Performance Considerations

### 1. Polling Intervals
- Sessions: 3 seconds
- Flows: 5 seconds
- Health: 5 seconds

### 2. Rendering Optimization
- Conditional rendering based on activeTab
- List virtualization for large terminal lists (future)
- Memoization for expensive computations (future)

### 3. Bundle Size
- React production build: ~150KB
- Extension code: ~50KB
- Total package: ~200KB

## Extension Points

### Adding New Features

1. **New Tab**:
   - Add tab button in App.tsx
   - Create new component
   - Add to tab routing

2. **New API Endpoint**:
   - Add method to CAOClient
   - Use in component

3. **New Message Type**:
   - Add handler in webviewProvider.ts
   - Use vscode.postMessage() from webview

4. **New VSCode Command**:
   - Register in package.json `contributes.commands`
   - Implement in extension.ts

## Testing Strategy

### Manual Testing
1. Start cao-server
2. Launch Extension Development Host (F5)
3. Test each feature in dashboard
4. Verify error handling
5. Check VSCode integration (terminals, notifications)

### Automated Testing (Future)
1. **Unit Tests**: Jest + React Testing Library
2. **Integration Tests**: Mock CAO server
3. **E2E Tests**: VSCode Extension Test Runner

## Deployment

### Local Installation
```bash
npm run build
npm run package
code --install-extension cao-vscode-*.vsix
```

### Marketplace Publication (Future)
```bash
vsce publish
```

## Monitoring and Debugging

### Extension Logs
- Output channel: CAO Extension
- Console: Extension Development Host

### Webview Logs
- Developer Tools: Help → Toggle Developer Tools
- Console tab: React errors, API calls
- Network tab: HTTP requests

### Server Logs
- Terminal running cao-server
- FastAPI/Uvicorn logs

## Future Architecture Improvements

1. **WebSocket Support**: Real-time updates instead of polling
2. **State Management**: Redux/Zustand for complex state
3. **Virtual Scrolling**: Handle large lists efficiently
4. **Offline Support**: Cache data, queue operations
5. **Multi-server**: Connect to multiple CAO servers
6. **Authentication**: Token management via SecretStorage
7. **Telemetry**: Usage analytics (opt-in)
8. **Extensions API**: Allow third-party extensions

## References

- [VSCode Extension API](https://code.visualstudio.com/api)
- [Webview API](https://code.visualstudio.com/api/extension-guides/webview)
- [React Docs](https://react.dev)
- [TypeScript Docs](https://www.typescriptlang.org/docs/)
- [Webpack Docs](https://webpack.js.org/)
