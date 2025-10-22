import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export class CAOWebviewProvider implements vscode.WebviewViewProvider {
  constructor(private readonly extensionUri: vscode.Uri) {}

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this.extensionUri],
    };

    webviewView.webview.html = this.getHtmlForWebview(webviewView.webview);

    // Handle messages from the webview
    webviewView.webview.onDidReceiveMessage(message => {
      this.handleMessage(message, webviewView.webview);
    });
  }

  public getHtmlForWebview(webview: vscode.Webview): string {
    const webviewPath = path.join(this.extensionUri.fsPath, 'out', 'webview');
    const indexPath = path.join(webviewPath, 'index.html');

    if (fs.existsSync(indexPath)) {
      let html = fs.readFileSync(indexPath, 'utf8');

      // Update resource URIs to use webview URIs
      const scriptUri = webview.asWebviewUri(
        vscode.Uri.file(path.join(webviewPath, 'webview.js'))
      );

      html = html.replace(
        /src="([^"]*)"/g,
        `src="${scriptUri}"`
      );

      // Add CSP
      const csp = `
        <meta http-equiv="Content-Security-Policy"
          content="default-src 'none';
          style-src ${webview.cspSource} 'unsafe-inline';
          script-src ${webview.cspSource} 'unsafe-inline';
          connect-src http://localhost:9889;">
      `;

      html = html.replace('</head>', `${csp}</head>`);

      return html;
    }

    // Fallback HTML if build doesn't exist
    return `
      <!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CAO Dashboard</title>
      </head>
      <body>
        <div id="root">
          <p>Building webview... Please run 'npm run build:webview' first.</p>
        </div>
      </body>
      </html>
    `;
  }

  public async handleMessage(message: any, webview: vscode.Webview) {
    switch (message.type) {
      case 'error':
        vscode.window.showErrorMessage(message.message);
        break;
      case 'info':
        vscode.window.showInformationMessage(message.message);
        break;
      case 'openTerminal':
        // Open a terminal and attach to tmux session
        const terminal = vscode.window.createTerminal({
          name: `CAO: ${message.sessionName}`,
          shellPath: '/usr/bin/tmux',
          shellArgs: ['attach', '-t', message.sessionName],
        });
        terminal.show();
        break;
      case 'openFile':
        const doc = await vscode.workspace.openTextDocument(message.filePath);
        await vscode.window.showTextDocument(doc);
        break;
    }
  }
}
