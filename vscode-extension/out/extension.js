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
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const CAODashboardProvider_1 = require("./providers/CAODashboardProvider");
const CAOApiClient_1 = require("./api/CAOApiClient");
function activate(context) {
    console.log('CLI Agent Orchestrator extension is now active');
    // Initialize API client
    const config = vscode.workspace.getConfiguration('cliAgentOrchestrator');
    const serverUrl = config.get('serverUrl', 'http://localhost:9889');
    const apiClient = new CAOApiClient_1.CAOApiClient(serverUrl);
    // Register dashboard provider
    const dashboardProvider = new CAODashboardProvider_1.CAODashboardProvider(context.extensionUri, apiClient);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider('caoAgentOrchestrator', dashboardProvider));
    // Register commands
    context.subscriptions.push(vscode.commands.registerCommand('cliAgentOrchestrator.openDashboard', () => {
        dashboardProvider.show();
    }));
    context.subscriptions.push(vscode.commands.registerCommand('cliAgentOrchestrator.launchAgent', async () => {
        const agentProfile = await vscode.window.showQuickPick(['code_supervisor', 'developer', 'reviewer'], { placeHolder: 'Select an agent profile to launch' });
        if (agentProfile) {
            try {
                await apiClient.launchAgent(agentProfile);
                vscode.window.showInformationMessage(`Launched ${agentProfile} agent`);
            }
            catch (error) {
                vscode.window.showErrorMessage(`Failed to launch agent: ${error}`);
            }
        }
    }));
    context.subscriptions.push(vscode.commands.registerCommand('cliAgentOrchestrator.shutdownAll', async () => {
        const confirm = await vscode.window.showWarningMessage('Are you sure you want to shutdown all agent sessions?', 'Yes', 'No');
        if (confirm === 'Yes') {
            try {
                await apiClient.shutdownAll();
                vscode.window.showInformationMessage('All sessions shut down');
            }
            catch (error) {
                vscode.window.showErrorMessage(`Failed to shutdown sessions: ${error}`);
            }
        }
    }));
    // Status bar item
    const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBarItem.text = '$(terminal) CAO';
    statusBarItem.command = 'cliAgentOrchestrator.openDashboard';
    statusBarItem.tooltip = 'Open CLI Agent Orchestrator Dashboard';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);
}
function deactivate() {
    console.log('CLI Agent Orchestrator extension is now deactivated');
}
//# sourceMappingURL=extension.js.map