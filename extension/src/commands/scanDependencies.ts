import * as vscode from 'vscode';
import type { FindingsTreeProvider } from '../providers/findingsTreeProvider';
import { ApiError, apiBaseUrl, checkHealth, submitScan } from '../services/apiClient';
import { findLockfiles, projectName, readLockfile } from '../utils/workspace';

const CLIENT = 'vscode-extension/0.1.0';

/**
 * Reads a package-lock.json and, after explicit confirmation, sends it to the Provenyx API.
 * Never installs or executes anything from the scanned project.
 */
export async function scanDependencies(tree: FindingsTreeProvider, target?: vscode.Uri): Promise<void> {
  if (!vscode.workspace.workspaceFolders?.length) {
    void vscode.window.showWarningMessage('Provenyx: Open a project folder to scan its dependencies.');
    return;
  }

  const uri = target ?? (await pickLockfile());
  if (!uri) return;
  const relPath = vscode.workspace.asRelativePath(uri);

  let lockfile;
  try {
    lockfile = await readLockfile(uri);
  } catch (err) {
    void vscode.window.showErrorMessage(`Provenyx: ${(err as Error).message}`);
    return;
  }

  const base = apiBaseUrl();
  const send = 'Send to Provenyx API';
  const choice = await vscode.window.showInformationMessage(
    `Provenyx found ${relPath} (lockfileVersion ${lockfile.lockfileVersion}).`,
    {
      modal: true,
      detail:
        `Send the contents of this lockfile to ${base}?\n\n` +
        'Only package-lock.json is sent. No other project files are uploaded and no packages are installed or executed.',
    },
    send,
  );
  if (choice !== send) return;

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: 'Provenyx: Submitting lockfile…' },
    async () => {
      try {
        await checkHealth();
        tree.setBackend('connected');
      } catch (err) {
        tree.setBackend('unreachable');
        fail(tree, err);
        return;
      }
      try {
        const res = await submitScan({ lockfile, project_name: lockfile.name ?? projectName(), client: CLIENT });
        tree.setLastScan({ kind: 'accepted', scanId: res.scan_id, message: res.message, at: new Date() });
        void vscode.window.showInformationMessage(`Provenyx: ${res.message}`);
      } catch (err) {
        fail(tree, err);
      }
    },
  );
}

async function pickLockfile(): Promise<vscode.Uri | undefined> {
  const found = await findLockfiles();
  if (found.length === 0) {
    void vscode.window.showWarningMessage('Provenyx: No package-lock.json found in this workspace. Run `npm install` in your own project to create one.');
    return undefined;
  }
  if (found.length === 1) return found[0];
  const picked = await vscode.window.showQuickPick(
    found.map((uri) => ({ label: vscode.workspace.asRelativePath(uri), uri })),
    { placeHolder: 'Select the package-lock.json to scan' },
  );
  return picked?.uri;
}

function fail(tree: FindingsTreeProvider, err: unknown): void {
  const message = err instanceof ApiError ? err.message : 'Unexpected error while contacting the Provenyx API.';
  tree.setLastScan({ kind: 'failed', message, at: new Date() });
  void vscode.window.showErrorMessage(`Provenyx: ${message}`);
}
