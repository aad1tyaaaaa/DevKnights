import * as vscode from 'vscode';
import { scanDependencies } from './commands/scanDependencies';
import { FindingsTreeProvider } from './providers/findingsTreeProvider';
import { ApiError, checkHealth } from './services/apiClient';
import { createLockfileWatcher } from './services/lockfileWatcher';

export function activate(context: vscode.ExtensionContext): void {
  const tree = new FindingsTreeProvider();

  const checkBackend = async (notify: boolean) => {
    try {
      const health = await checkHealth();
      tree.setBackend('connected');
      if (notify) void vscode.window.showInformationMessage(`Provenyx: Connected to ${health.service} ${health.version}.`);
    } catch (err) {
      tree.setBackend('unreachable');
      if (notify) void vscode.window.showErrorMessage(`Provenyx: ${err instanceof ApiError ? err.message : 'Backend check failed.'}`);
    }
  };

  context.subscriptions.push(
    vscode.window.registerTreeDataProvider('provenyx.findings', tree),
    vscode.commands.registerCommand('provenyx.scanDependencies', (uri?: vscode.Uri) =>
      scanDependencies(tree, uri instanceof vscode.Uri ? uri : undefined),
    ),
    vscode.commands.registerCommand('provenyx.showFindings', () =>
      vscode.commands.executeCommand('provenyx.findings.focus'),
    ),
    vscode.commands.registerCommand('provenyx.openDashboard', async () => {
      const url = vscode.workspace.getConfiguration('provenyx').get<string>('dashboardUrl', 'http://localhost:3000');
      let uri: vscode.Uri;
      try {
        uri = vscode.Uri.parse(url, true);
      } catch {
        void vscode.window.showErrorMessage(`Provenyx: "${url}" is not a valid dashboard URL. Check the provenyx.dashboardUrl setting.`);
        return;
      }
      await vscode.env.openExternal(uri);
    }),
    vscode.commands.registerCommand('provenyx.checkBackend', () => checkBackend(true)),
    createLockfileWatcher((uri) => void scanDependencies(tree, uri)),
    vscode.workspace.onDidChangeWorkspaceFolders(() => tree.refresh()),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration('provenyx.apiBaseUrl')) void checkBackend(false);
    }),
  );

  // Local health probe only; no project data is sent.
  void checkBackend(false);
}

export function deactivate(): void {}
