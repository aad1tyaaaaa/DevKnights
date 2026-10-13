import * as vscode from 'vscode';
import { scanDependencies } from './commands/scanDependencies';
import { simplifyFindingsCommand } from './commands/simplifyFindings';
import { FindingsTreeProvider } from './providers/findingsTreeProvider';
import { checkHealth, DEFAULT_API_BASE_URL } from './services/apiClient';
import { githubSession, requireGitHubSession } from './services/githubAuth';
import { createLockfileWatcher } from './services/lockfileWatcher';
import { openDashboard } from './utils/dashboard';
import { showApiError } from './utils/errors';
import { findLockfiles } from './utils/workspace';

const API_URL_MIGRATION_KEY = 'provenyx.apiBaseUrlMigratedToRender';
const LEGACY_EXTENSION_ID = 'Provenyx.provenyx-security';
const LEGACY_API_URLS = new Set(['http://localhost:8000', 'http://127.0.0.1:8000']);

async function migrateLegacyApiUrl(context: vscode.ExtensionContext): Promise<void> {
  if (context.globalState.get<boolean>(API_URL_MIGRATION_KEY)) return;

  const configuration = vscode.workspace.getConfiguration('provenyx');
  const inspected = configuration.inspect<string>('apiBaseUrl');
  if (inspected?.globalValue && LEGACY_API_URLS.has(inspected.globalValue.replace(/\/+$/, ''))) {
    await configuration.update('apiBaseUrl', DEFAULT_API_BASE_URL, vscode.ConfigurationTarget.Global);
  }
  if (inspected?.workspaceValue && LEGACY_API_URLS.has(inspected.workspaceValue.replace(/\/+$/, ''))) {
    await configuration.update('apiBaseUrl', DEFAULT_API_BASE_URL, vscode.ConfigurationTarget.Workspace);
  }
  for (const folder of vscode.workspace.workspaceFolders ?? []) {
    const folderConfiguration = vscode.workspace.getConfiguration('provenyx', folder.uri);
    const folderValue = folderConfiguration.inspect<string>('apiBaseUrl')?.workspaceFolderValue;
    if (folderValue && LEGACY_API_URLS.has(folderValue.replace(/\/+$/, ''))) {
      await folderConfiguration.update('apiBaseUrl', DEFAULT_API_BASE_URL, vscode.ConfigurationTarget.WorkspaceFolder);
    }
  }
  await context.globalState.update(API_URL_MIGRATION_KEY, true);
}

async function warnAboutLegacyExtension(): Promise<void> {
  if (!vscode.extensions.getExtension(LEGACY_EXTENSION_ID)) return;
  const uninstall = 'Uninstall';
  const open = 'Show Legacy Extension';
  const choice = await vscode.window.showWarningMessage(
    'Provenyx: The obsolete Provenyx.provenyx-security extension is also installed and can override the deployed API URL. Uninstall it, then reload VS Code.',
    uninstall,
    open,
  );
  if (choice === open) {
    await vscode.commands.executeCommand('workbench.extensions.search', `@id:${LEGACY_EXTENSION_ID}`);
  } else if (choice === uninstall) {
    await vscode.commands.executeCommand('workbench.extensions.uninstallExtension', LEGACY_EXTENSION_ID);
    const reload = 'Reload Window';
    if ((await vscode.window.showInformationMessage('Provenyx: Legacy extension uninstalled.', reload)) === reload) {
      await vscode.commands.executeCommand('workbench.action.reloadWindow');
    }
  }
}

// The legacy extension registers the same command IDs; if it activated first, registering
// ours throws. Skip the duplicate so the rest of activation (sidebar, watcher) still runs.
function registerCommand(id: string, handler: (...args: any[]) => unknown): vscode.Disposable {
  try {
    return vscode.commands.registerCommand(id, handler);
  } catch {
    return new vscode.Disposable(() => undefined);
  }
}

export async function activate(context: vscode.ExtensionContext) {
  await migrateLegacyApiUrl(context);
  void warnAboutLegacyExtension();
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
    registerCommand('provenyx.scanDependencies', (uri?: vscode.Uri) =>
      scanDependencies(tree, uri instanceof vscode.Uri ? uri : undefined),
    ),
    registerCommand('provenyx.showFindings', () =>
      vscode.commands.executeCommand('provenyx.findings.focus'),
    ),
    // Optional path (e.g. "/scans/<id>") is passed by sidebar items.
    registerCommand('provenyx.openDashboard', (path?: unknown) =>
      openDashboard(typeof path === 'string' && path.startsWith('/') ? path : ''),
    ),
    vscode.commands.registerCommand('provenyx.simplifyFindings', () =>
      simplifyFindingsCommand(tree),
    ),
    vscode.commands.registerCommand('provenyx.checkBackend', () => checkBackend(true)),
    vscode.commands.registerCommand('provenyx.signIn', () => requireGitHubSession()),
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

  // VS Code owns and securely stores the GitHub session; Provenyx never persists it locally.
  void Promise.resolve(githubSession(true)).catch(() => undefined);

  // File watchers only observe future writes, so scan the lockfile already present when a project opens.
  void scanExistingLockfiles();

  // Exposed for the extension's own smoke tests; not a public API.
  return { tree };
}

export function deactivate(): void {}
