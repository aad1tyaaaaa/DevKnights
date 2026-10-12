import * as vscode from 'vscode';
import { scanDependencies } from './commands/scanDependencies';
import { FindingsTreeProvider } from './providers/findingsTreeProvider';
import { checkHealth } from './services/apiClient';
import { createLockfileWatcher } from './services/lockfileWatcher';
import { openDashboard } from './utils/dashboard';
import { showApiError } from './utils/errors';

export function activate(context: vscode.ExtensionContext) {
  const tree = new FindingsTreeProvider();

  const checkBackend = async (notify: boolean) => {
    try {
      const health = await checkHealth();
      tree.setBackend('connected');
      if (notify) void vscode.window.showInformationMessage(`Provenyx: Connected to ${health.service} ${health.version}.`);
    } catch (err) {
      tree.setBackend('unreachable');
      if (notify) void showApiError(err);
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
    // Optional path (e.g. "/scans/<id>") is passed by sidebar items.
    vscode.commands.registerCommand('provenyx.openDashboard', (path?: unknown) =>
      openDashboard(typeof path === 'string' && path.startsWith('/') ? path : ''),
    ),
    vscode.commands.registerCommand('provenyx.checkBackend', () => checkBackend(true)),
    createLockfileWatcher((uri) => void scanDependencies(tree, uri)),
    vscode.workspace.onDidChangeWorkspaceFolders(() => tree.refresh()),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration('provenyx.apiBaseUrl')) void checkBackend(false);
    }),
  );

  // Local health probe only; no project data is sent.
  void checkBackend(false);

  // Exposed for the extension's own smoke tests; not a public API.
  return { tree };
}

export function deactivate(): void {}
