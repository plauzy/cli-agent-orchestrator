import * as vscode from 'vscode';
import { CAODashboardProvider } from './providers/CAODashboardProvider';
import { CAOApiClient } from './api/CAOApiClient';

export function activate(context: vscode.ExtensionContext) {
    console.log('CLI Agent Orchestrator extension is now active');

    // Initialize API client
    const config = vscode.workspace.getConfiguration('cliAgentOrchestrator');
    const serverUrl = config.get<string>('serverUrl', 'http://localhost:9889');
    const apiClient = new CAOApiClient(serverUrl);

    // Register dashboard provider
    const dashboardProvider = new CAODashboardProvider(context.extensionUri, apiClient);

    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            'caoAgentOrchestrator',
            dashboardProvider
        )
    );

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('cliAgentOrchestrator.openDashboard', () => {
            dashboardProvider.show();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('cliAgentOrchestrator.launchAgent', async () => {
            const agentProfile = await vscode.window.showQuickPick(
                ['code_supervisor', 'developer', 'reviewer'],
                { placeHolder: 'Select an agent profile to launch' }
            );

            if (agentProfile) {
                try {
                    await apiClient.launchAgent(agentProfile);
                    vscode.window.showInformationMessage(`Launched ${agentProfile} agent`);
                } catch (error) {
                    vscode.window.showErrorMessage(`Failed to launch agent: ${error}`);
                }
            }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('cliAgentOrchestrator.shutdownAll', async () => {
            const confirm = await vscode.window.showWarningMessage(
                'Are you sure you want to shutdown all agent sessions?',
                'Yes', 'No'
            );

            if (confirm === 'Yes') {
                try {
                    await apiClient.shutdownAll();
                    vscode.window.showInformationMessage('All sessions shut down');
                } catch (error) {
                    vscode.window.showErrorMessage(`Failed to shutdown sessions: ${error}`);
                }
            }
        })
    );

    // Status bar item
    const statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Left,
        100
    );
    statusBarItem.text = '$(terminal) CAO';
    statusBarItem.command = 'cliAgentOrchestrator.openDashboard';
    statusBarItem.tooltip = 'Open CLI Agent Orchestrator Dashboard';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);
}

export function deactivate() {
    console.log('CLI Agent Orchestrator extension is now deactivated');
}
