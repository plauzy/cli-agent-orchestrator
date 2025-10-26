import * as vscode from 'vscode';
import { CAOApiClient } from '../api/CAOApiClient';

export class CAODashboardProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'caoAgentOrchestrator';
    private _view?: vscode.WebviewView;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly _apiClient: CAOApiClient
    ) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                vscode.Uri.joinPath(this._extensionUri, 'webview', 'dist')
            ]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // Handle messages from the webview
        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.command) {
                case 'getSessions':
                    try {
                        const sessions = await this._apiClient.getSessions();
                        webviewView.webview.postMessage({
                            command: 'sessionsData',
                            data: sessions
                        });
                    } catch (error) {
                        webviewView.webview.postMessage({
                            command: 'error',
                            data: `Failed to fetch sessions: ${error}`
                        });
                    }
                    break;

                case 'getTerminals':
                    try {
                        const terminals = await this._apiClient.getTerminals(message.sessionId);
                        webviewView.webview.postMessage({
                            command: 'terminalsData',
                            data: terminals
                        });
                    } catch (error) {
                        webviewView.webview.postMessage({
                            command: 'error',
                            data: `Failed to fetch terminals: ${error}`
                        });
                    }
                    break;

                case 'getTerminalOutput':
                    try {
                        const output = await this._apiClient.getOutput(message.terminalId);
                        webviewView.webview.postMessage({
                            command: 'terminalOutput',
                            terminalId: message.terminalId,
                            data: output
                        });
                    } catch (error) {
                        webviewView.webview.postMessage({
                            command: 'error',
                            data: `Failed to fetch terminal output: ${error}`
                        });
                    }
                    break;

                case 'sendInput':
                    try {
                        await this._apiClient.sendInput(message.terminalId, message.input);
                        webviewView.webview.postMessage({
                            command: 'inputSent',
                            terminalId: message.terminalId
                        });
                    } catch (error) {
                        webviewView.webview.postMessage({
                            command: 'error',
                            data: `Failed to send input: ${error}`
                        });
                    }
                    break;

                case 'launchAgent':
                    try {
                        const terminal = await this._apiClient.launchAgent(message.agentProfile);
                        webviewView.webview.postMessage({
                            command: 'agentLaunched',
                            data: terminal
                        });
                    } catch (error) {
                        webviewView.webview.postMessage({
                            command: 'error',
                            data: `Failed to launch agent: ${error}`
                        });
                    }
                    break;

                case 'deleteTerminal':
                    try {
                        await this._apiClient.deleteTerminal(message.terminalId);
                        webviewView.webview.postMessage({
                            command: 'terminalDeleted',
                            terminalId: message.terminalId
                        });
                    } catch (error) {
                        webviewView.webview.postMessage({
                            command: 'error',
                            data: `Failed to delete terminal: ${error}`
                        });
                    }
                    break;

                case 'getFlows':
                    try {
                        const flows = await this._apiClient.getFlows();
                        webviewView.webview.postMessage({
                            command: 'flowsData',
                            data: flows
                        });
                    } catch (error) {
                        webviewView.webview.postMessage({
                            command: 'error',
                            data: `Failed to fetch flows: ${error}`
                        });
                    }
                    break;

                case 'runFlow':
                    try {
                        await this._apiClient.runFlow(message.flowName);
                        webviewView.webview.postMessage({
                            command: 'flowRun',
                            flowName: message.flowName
                        });
                    } catch (error) {
                        webviewView.webview.postMessage({
                            command: 'error',
                            data: `Failed to run flow: ${error}`
                        });
                    }
                    break;
            }
        });
    }

    public show() {
        if (this._view) {
            this._view.show?.(true);
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        const scriptUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'webview', 'dist', 'index.js')
        );
        const styleUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'webview', 'dist', 'index.css')
        );

        const nonce = getNonce();

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
    <link href="${styleUri}" rel="stylesheet">
    <title>CLI Agent Orchestrator</title>
</head>
<body>
    <div id="root"></div>
    <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
    }
}

function getNonce() {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
