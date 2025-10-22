# VSCode Extension Development Guide

This guide covers development workflows for the CLI Agent Orchestrator VSCode extension.

## Project Structure

```
vscode-extension/
├── src/
│   ├── extension.ts              # Extension host (Node.js process)
│   ├── shared/
│   │   └── types.ts             # Shared TypeScript types
│   └── webview/
│       ├── index.tsx            # React entry point
│       ├── App.tsx              # Main React component
│       ├── styles.css           # Global styles
│       ├── components/          # React components
│       │   ├── SessionsView.tsx
│       │   ├── TerminalsView.tsx
│       │   ├── TerminalDetail.tsx
│       │   └── FlowsView.tsx
│       └── services/
│           └── apiClient.ts     # CAO API client
├── dist/                        # Compiled output
├── package.json                 # Extension manifest
├── tsconfig.json               # TypeScript config
└── webpack.config.js           # Build config
```

## Tech Stack

- **Extension Host**: TypeScript + Node.js + VSCode Extension API
- **Webview**: React 18 + TypeScript
- **Bundler**: Webpack 5
- **HTTP Client**: Axios
- **Styling**: CSS with VSCode theme variables

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- VSCode 1.85.0+

### Installation

```bash
cd vscode-extension
npm install
```

### Development Workflow

#### 1. Watch Mode (Recommended)

Open two terminals:

**Terminal 1 - Build watch:**
```bash
npm run watch
```

**Terminal 2 - VSCode Extension Development Host:**
- Open the `vscode-extension` folder in VSCode
- Press `F5` to launch the Extension Development Host
- The extension will reload automatically when you save changes

#### 2. Manual Build

```bash
npm run compile
```

Then press `F5` in VSCode to launch.

#### 3. Production Build

```bash
npm run package
```

This creates optimized bundles with hidden source maps.

## Architecture

### Extension Host (Node.js)

The extension host (`src/extension.ts`) runs in Node.js and:

1. Creates and manages the webview panel
2. Handles communication between VSCode and the webview
3. Makes HTTP requests to the CAO API server
4. Provides VSCode commands

**Key Responsibilities:**
- Webview lifecycle management
- Message routing between webview and API
- Error handling and user notifications
- Command registration

### Webview (React)

The webview (`src/webview/`) runs in a sandboxed iframe and:

1. Renders the UI using React components
2. Sends messages to the extension host
3. Receives updates from the extension host
4. Manages local UI state

**Key Components:**
- `App.tsx`: Main component with tab navigation
- `SessionsView.tsx`: Sessions list and creation
- `TerminalsView.tsx`: Terminals list for selected session
- `TerminalDetail.tsx`: Terminal output and input interface
- `FlowsView.tsx`: Scheduled flows management

### Communication Flow

```
┌─────────────────┐           ┌──────────────────┐
│  Webview (UI)   │◄─────────►│ Extension Host   │
│  React + TS     │  Messages │  Node.js + TS    │
└─────────────────┘           └──────────────────┘
                                       │
                                       │ HTTP
                                       ▼
                              ┌──────────────────┐
                              │  CAO API Server  │
                              │  FastAPI + Python│
                              └──────────────────┘
```

**Message Types:**

From Webview → Extension:
- `getSessions`, `getTerminals`, `getFlows`
- `createSession`, `createTerminal`
- `deleteSession`, `deleteTerminal`
- `sendInput`, `getOutput`, `sendMessage`

From Extension → Webview:
- `updateSessions`, `updateTerminals`, `updateFlows`
- `updateTerminalOutput`
- `success`, `error`

## Development Tips

### Hot Reload

The watch mode automatically rebuilds on changes. In the Extension Development Host:
- `Cmd+R` (Mac) or `Ctrl+R` (Windows/Linux) to reload the extension
- Webview reloads automatically when the extension reloads

### Debugging

**Extension Host:**
1. Set breakpoints in `src/extension.ts`
2. Press `F5` to start debugging
3. Breakpoints will hit in the main VSCode instance

**Webview:**
1. In the Extension Development Host, press `Cmd+Shift+P` → "Developer: Open Webview Developer Tools"
2. Use Chrome DevTools to debug React components
3. Add `console.log()` statements in webview code

### VSCode Theme Variables

The UI uses VSCode theme variables for consistent styling:

```css
.button {
  background-color: var(--vscode-button-background);
  color: var(--vscode-button-foreground);
}
```

Common variables:
- `--vscode-foreground`, `--vscode-background`
- `--vscode-button-background`, `--vscode-button-foreground`
- `--vscode-input-background`, `--vscode-input-foreground`
- `--vscode-panel-border`
- `--vscode-errorForeground`, `--vscode-successForeground`

### Adding New Commands

1. **Register in package.json:**
```json
{
  "contributes": {
    "commands": [
      {
        "command": "cao.myCommand",
        "title": "My Command",
        "category": "CAO"
      }
    ]
  }
}
```

2. **Implement in extension.ts:**
```typescript
context.subscriptions.push(
  vscode.commands.registerCommand('cao.myCommand', async () => {
    // Command implementation
  })
);
```

### Adding New Components

1. Create component in `src/webview/components/`
2. Import and use in `App.tsx` or parent component
3. Define prop types using TypeScript interfaces
4. Use shared types from `src/shared/types.ts`

Example:
```typescript
import React from 'react';
import { Terminal } from '../../shared/types';

interface MyComponentProps {
  terminal: Terminal;
  onAction: () => void;
}

const MyComponent: React.FC<MyComponentProps> = ({ terminal, onAction }) => {
  return <div>{terminal.name}</div>;
};

export default MyComponent;
```

## Testing

### Manual Testing

1. Start the CAO API server:
   ```bash
   cao-server
   ```

2. Launch the extension in development mode (F5)

3. Test scenarios:
   - Create/delete sessions
   - Create/delete terminals
   - Send messages to terminals
   - View terminal output
   - Enable/disable flows

### Integration Testing

Test against a real CAO server with:
- Multiple sessions with different providers
- Terminals in various states (IDLE, PROCESSING, ERROR)
- Long-running agent tasks
- Flow scheduling

## Common Issues

### Webview Not Loading

- Check webpack build completed successfully
- Verify `dist/webview.js` exists
- Check browser console in Webview DevTools for errors

### Extension Host Errors

- Check DEBUG CONSOLE in VSCode
- Look for TypeScript compilation errors
- Verify axios requests are succeeding

### Styling Issues

- Ensure CSS class names match stylesheet
- Use browser DevTools to inspect elements
- Check that VSCode theme variables are defined

## Building for Production

### Create VSIX Package

```bash
npm install -g vsce
vsce package
```

This creates a `.vsix` file that can be:
- Installed locally in VSCode
- Shared with others
- Published to the VSCode Marketplace

### Pre-publish Checklist

- [ ] All features working
- [ ] No console errors
- [ ] README is complete
- [ ] Version bumped in package.json
- [ ] CHANGELOG updated
- [ ] Extension tested on macOS, Linux, Windows
- [ ] Screenshots added to README

## Publishing to Marketplace

1. Create a [publisher account](https://marketplace.visualstudio.com/manage)

2. Create a Personal Access Token (PAT) from Azure DevOps

3. Login and publish:
   ```bash
   vsce login <publisher-name>
   vsce publish
   ```

## Contributing

When contributing:

1. Follow the existing code style
2. Add TypeScript types for all new code
3. Test on both light and dark themes
4. Update documentation
5. Add comments for complex logic

## Resources

- [VSCode Extension API](https://code.visualstudio.com/api)
- [Webview API](https://code.visualstudio.com/api/extension-guides/webview)
- [React Documentation](https://react.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
