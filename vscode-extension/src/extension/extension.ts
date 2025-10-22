import * as vscode from 'vscode';
import { CAOWebviewProvider } from './webviewProvider';

export function activate(context: vscode.ExtensionContext) {
  console.log('CAO extension is now active');

  // Register the webview provider for the sidebar
  const provider = new CAOWebviewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('cao.dashboard', provider)
  );

  // Register command to open dashboard
  const openDashboardCommand = vscode.commands.registerCommand('cao.openDashboard', () => {
    const panel = vscode.window.createWebviewPanel(
      'caoDashboard',
      'CAO Dashboard',
      vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
      }
    );

    panel.webview.html = provider.getHtmlForWebview(panel.webview);

    // Handle messages from the webview
    panel.webview.onDidReceiveMessage(
      message => provider.handleMessage(message, panel.webview),
      undefined,
      context.subscriptions
    );
  });

  context.subscriptions.push(openDashboardCommand);
}

export function deactivate() {
  console.log('CAO extension is now deactivated');
}
