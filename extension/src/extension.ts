import * as vscode from 'vscode';
import { scanDependencies } from './commands/scanDependencies';
import { FindingsTreeProvider } from './providers/findingsTreeProvider';
import { checkHealth } from './services/apiClient';
import { createLockfileWatcher } from './services/lockfileWatcher';
import { openDashboard } from './utils/dashboard';
import { showApiError } from './utils/errors';
import { findLockfiles } from './utils/workspace';

export function activate(context: vscode.ExtensionContext) {
  const tree = new FindingsTreeProvider();

  const scanExistingLockfiles = async (folder?: vscode.WorkspaceFolder) => {
    if (!vscode.workspace.getConfiguration('provenyx').get<boolean>('autoScanEnabled', true)) return;
    for (const lockfile of await findLockfiles(folder)) await scanDependencies(tree, lockfile);
  };

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
    vscode.workspace.onDidChangeWorkspaceFolders((event) => {
      tree.refresh();
      for (const folder of event.added) void scanExistingLockfiles(folder);
    }),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration('provenyx.apiBaseUrl')) void checkBackend(false);
    }),
  );

  // Local health probe only; no project data is sent.
  void checkBackend(false);

  // File watchers only observe future writes, so scan the lockfile already present when a project opens.
  void scanExistingLockfiles();

  // Exposed for the extension's own smoke tests; not a public API.
  return { tree };
}

export function deactivate(): void {}
