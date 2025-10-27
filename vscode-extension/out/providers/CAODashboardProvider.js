"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.CAODashboardProvider = void 0;
const vscode = __importStar(require("vscode"));
class CAODashboardProvider {
    constructor(_extensionUri, _apiClient) {
        this._extensionUri = _extensionUri;
        this._apiClient = _apiClient;
    }
    resolveWebviewView(webviewView, context, _token) {
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
                    }
                    catch (error) {
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
                    }
                    catch (error) {
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
                    }
                    catch (error) {
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
                    }
                    catch (error) {
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
                    }
                    catch (error) {
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
                    }
                    catch (error) {
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
                    }
                    catch (error) {
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
                    }
                    catch (error) {
                        webviewView.webview.postMessage({
                            command: 'error',
                            data: `Failed to run flow: ${error}`
                        });
                    }
                    break;
            }
        });
    }
    show() {
        if (this._view) {
            this._view.show?.(true);
        }
    }
    _getHtmlForWebview(webview) {
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'webview', 'dist', 'index.js'));
        const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'webview', 'dist', 'index.css'));
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
exports.CAODashboardProvider = CAODashboardProvider;
CAODashboardProvider.viewType = 'caoAgentOrchestrator';
function getNonce() {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
//# sourceMappingURL=CAODashboardProvider.js.map