// VSCode Extension Host - manages webview lifecycle and API communication
import * as vscode from 'vscode';
import * as path from 'path';
import axios from 'axios';
import {
  MessageFromWebview,
  MessageToWebview,
  Session,
  Terminal,
  InboxMessage,
  Flow
} from './shared/types';

let dashboardPanel: vscode.WebviewPanel | undefined;

export function activate(context: vscode.ExtensionContext) {
  console.log('CLI Agent Orchestrator extension is now active');

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand('cao.openDashboard', () => {
      openDashboard(context);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('cao.createSession', async () => {
      await createSessionCommand(context);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('cao.launchAgent', async () => {
      await launchAgentCommand(context);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('cao.refreshSessions', () => {
      if (dashboardPanel) {
        sendMessageToWebview(dashboardPanel, { type: 'getSessions' });
      }
    })
  );

  // Auto-open dashboard on activation if configured
  const config = vscode.workspace.getConfiguration('cao');
  if (config.get('autoOpenDashboard', false)) {
    openDashboard(context);
  }
}

function openDashboard(context: vscode.ExtensionContext) {
  if (dashboardPanel) {
    dashboardPanel.reveal(vscode.ViewColumn.One);
    return;
  }

  dashboardPanel = vscode.window.createWebviewPanel(
    'caoDashboard',
    'CAO Dashboard',
    vscode.ViewColumn.One,
    {
      enableScripts: true,
      retainContextWhenHidden: true,
      localResourceRoots: [
        vscode.Uri.file(path.join(context.extensionPath, 'dist'))
      ]
    }
  );

  // Set webview content
  dashboardPanel.webview.html = getWebviewContent(context, dashboardPanel.webview);

  // Handle messages from webview
  dashboardPanel.webview.onDidReceiveMessage(
    async (message: MessageFromWebview) => {
      await handleWebviewMessage(message, dashboardPanel!);
    },
    undefined,
    context.subscriptions
  );

  // Clean up when panel is closed
  dashboardPanel.onDidDispose(
    () => {
      dashboardPanel = undefined;
    },
    null,
    context.subscriptions
  );
}

async function handleWebviewMessage(
  message: MessageFromWebview,
  panel: vscode.WebviewPanel
) {
  const config = vscode.workspace.getConfiguration('cao');
  const serverUrl = config.get<string>('serverUrl', 'http://localhost:9889');
  const client = axios.create({ baseURL: serverUrl, timeout: 30000 });

  try {
    switch (message.type) {
      case 'getSessions': {
        const response = await client.get<Session[]>('/sessions');
        sendMessageToWebview(panel, {
          type: 'updateSessions',
          sessions: response.data
        });
        break;
      }

      case 'getTerminals': {
        const response = await client.get<Terminal[]>(
          `/sessions/${message.sessionName}/terminals`
        );
        sendMessageToWebview(panel, {
          type: 'updateTerminals',
          terminals: response.data
        });
        break;
      }

      case 'createSession': {
        const response = await client.post<Terminal>('/sessions', message.request);
        sendMessageToWebview(panel, {
          type: 'success',
          message: `Session created with terminal ${response.data.id}`
        });
        // Refresh sessions
        const sessionsResponse = await client.get<Session[]>('/sessions');
        sendMessageToWebview(panel, {
          type: 'updateSessions',
          sessions: sessionsResponse.data
        });
        break;
      }

      case 'createTerminal': {
        const response = await client.post<Terminal>(
          `/sessions/${message.sessionName}/terminals`,
          message.request
        );
        sendMessageToWebview(panel, {
          type: 'success',
          message: `Terminal ${response.data.id} created`
        });
        // Refresh terminals for this session
        const terminalsResponse = await client.get<Terminal[]>(
          `/sessions/${message.sessionName}/terminals`
        );
        sendMessageToWebview(panel, {
          type: 'updateTerminals',
          terminals: terminalsResponse.data
        });
        break;
      }

      case 'deleteSession': {
        await client.delete(`/sessions/${message.sessionName}`);
        sendMessageToWebview(panel, {
          type: 'success',
          message: `Session ${message.sessionName} deleted`
        });
        // Refresh sessions
        const response = await client.get<Session[]>('/sessions');
        sendMessageToWebview(panel, {
          type: 'updateSessions',
          sessions: response.data
        });
        break;
      }

      case 'deleteTerminal': {
        await client.delete(`/terminals/${message.terminalId}`);
        sendMessageToWebview(panel, {
          type: 'success',
          message: `Terminal ${message.terminalId} deleted`
        });
        break;
      }

      case 'sendInput': {
        await client.post(
          `/terminals/${message.terminalId}/input`,
          null,
          { params: { message: message.message } }
        );
        sendMessageToWebview(panel, {
          type: 'success',
          message: 'Message sent to terminal'
        });
        break;
      }

      case 'getOutput': {
        const response = await client.get(
          `/terminals/${message.terminalId}/output`,
          { params: { mode: message.mode } }
        );
        sendMessageToWebview(panel, {
          type: 'updateTerminalOutput',
          terminalId: message.terminalId,
          output: response.data.output
        });
        break;
      }

      case 'sendMessage': {
        await client.post(
          `/terminals/${message.receiverId}/inbox/messages`,
          null,
          {
            params: {
              sender_id: message.request.sender_id,
              message: message.request.message
            }
          }
        );
        sendMessageToWebview(panel, {
          type: 'success',
          message: 'Message queued for delivery'
        });
        break;
      }

      case 'getFlows': {
        try {
          const response = await client.get<Flow[]>('/flows');
          sendMessageToWebview(panel, {
            type: 'updateFlows',
            flows: response.data
          });
        } catch (error) {
          // Flow endpoints might not be implemented yet
          sendMessageToWebview(panel, {
            type: 'updateFlows',
            flows: []
          });
        }
        break;
      }

      case 'enableFlow': {
        await client.post(`/flows/${message.flowName}/enable`);
        sendMessageToWebview(panel, {
          type: 'success',
          message: `Flow ${message.flowName} enabled`
        });
        break;
      }

      case 'disableFlow': {
        await client.post(`/flows/${message.flowName}/disable`);
        sendMessageToWebview(panel, {
          type: 'success',
          message: `Flow ${message.flowName} disabled`
        });
        break;
      }

      case 'runFlow': {
        await client.post(`/flows/${message.flowName}/run`);
        sendMessageToWebview(panel, {
          type: 'success',
          message: `Flow ${message.flowName} started`
        });
        break;
      }
    }
  } catch (error: any) {
    const errorMessage = error.response?.data?.detail || error.message || 'Unknown error';
    sendMessageToWebview(panel, {
      type: 'error',
      message: `Error: ${errorMessage}`
    });
    vscode.window.showErrorMessage(`CAO Error: ${errorMessage}`);
  }
}

function sendMessageToWebview(panel: vscode.WebviewPanel, message: MessageToWebview) {
  panel.webview.postMessage(message);
}

async function createSessionCommand(context: vscode.ExtensionContext) {
  const provider = await vscode.window.showQuickPick(['q_cli', 'claude_code'], {
    placeHolder: 'Select provider'
  });

  if (!provider) {
    return;
  }

  const agentProfile = await vscode.window.showInputBox({
    placeHolder: 'Agent profile name (optional)',
    prompt: 'Enter agent profile name or leave empty'
  });

  const sessionName = await vscode.window.showInputBox({
    placeHolder: 'Session name (optional)',
    prompt: 'Enter custom session name or leave empty for auto-generated'
  });

  if (!dashboardPanel) {
    openDashboard(context);
  }

  if (dashboardPanel) {
    sendMessageToWebview(dashboardPanel, {
      type: 'createSession',
      request: {
        provider: provider as any,
        agent_profile: agentProfile || undefined,
        session_name: sessionName || undefined
      }
    } as any);
  }
}

async function launchAgentCommand(context: vscode.ExtensionContext) {
  const sessions = await getSessions();

  if (sessions.length === 0) {
    const create = await vscode.window.showInformationMessage(
      'No sessions found. Create a new session?',
      'Yes',
      'No'
    );
    if (create === 'Yes') {
      await createSessionCommand(context);
    }
    return;
  }

  const sessionName = await vscode.window.showQuickPick(
    sessions.map(s => s.name),
    { placeHolder: 'Select session' }
  );

  if (!sessionName) {
    return;
  }

  const provider = await vscode.window.showQuickPick(['q_cli', 'claude_code'], {
    placeHolder: 'Select provider'
  });

  if (!provider) {
    return;
  }

  const agentProfile = await vscode.window.showInputBox({
    placeHolder: 'Agent profile name (optional)',
    prompt: 'Enter agent profile name or leave empty'
  });

  if (!dashboardPanel) {
    openDashboard(context);
  }

  if (dashboardPanel) {
    sendMessageToWebview(dashboardPanel, {
      type: 'createTerminal',
      sessionName,
      request: {
        provider: provider as any,
        agent_profile: agentProfile || undefined
      }
    } as any);
  }
}

async function getSessions(): Promise<Session[]> {
  const config = vscode.workspace.getConfiguration('cao');
  const serverUrl = config.get<string>('serverUrl', 'http://localhost:9889');

  try {
    const response = await axios.get<Session[]>(`${serverUrl}/sessions`);
    return response.data;
  } catch (error) {
    return [];
  }
}

function getWebviewContent(context: vscode.ExtensionContext, webview: vscode.Webview): string {
  const scriptUri = webview.asWebviewUri(
    vscode.Uri.file(path.join(context.extensionPath, 'dist', 'webview.js'))
  );

  return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src ${webview.cspSource}; connect-src http://localhost:9889;">
    <title>CAO Dashboard</title>
    <style>
        body {
            padding: 0;
            margin: 0;
            font-family: var(--vscode-font-family);
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
        }
        #root {
            width: 100%;
            height: 100vh;
        }
    </style>
</head>
<body>
    <div id="root"></div>
    <script src="${scriptUri}"></script>
</body>
</html>`;
}

export function deactivate() {
  if (dashboardPanel) {
    dashboardPanel.dispose();
  }
}
