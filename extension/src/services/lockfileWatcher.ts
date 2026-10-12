import * as vscode from 'vscode';
import { isProjectLockfile } from '../utils/workspace';

const DEBOUNCE_MS = 1500;

/**
 * When provenyx.autoScanEnabled is on, offers a scan after package-lock.json changes.
 * The scan command still asks for consent before anything is sent.
 */
export function createLockfileWatcher(onChange: (uri: vscode.Uri) => void): vscode.Disposable {
  const watcher = vscode.workspace.createFileSystemWatcher('**/package-lock.json');
  const pending = new Map<string, NodeJS.Timeout>();

  const offer = async (uri: vscode.Uri) => {
    pending.delete(uri.toString());
    if (!vscode.workspace.getConfiguration('provenyx').get<boolean>('autoScanEnabled', false)) return;
    const scan = 'Scan';
    const choice = await vscode.window.showInformationMessage(
      `Provenyx: ${vscode.workspace.asRelativePath(uri)} changed. Scan it?`,
      scan,
    );
    if (choice === scan) onChange(uri);
  };

  // npm often writes the lockfile more than once per install; collapse bursts into one prompt.
  const handler = (uri: vscode.Uri) => {
    if (!isProjectLockfile(uri)) return;
    const key = uri.toString();
    clearTimeout(pending.get(key));
    pending.set(key, setTimeout(() => void offer(uri), DEBOUNCE_MS));
  };

  return vscode.Disposable.from(
    watcher,
    watcher.onDidChange(handler),
    watcher.onDidCreate(handler),
    { dispose: () => pending.forEach(clearTimeout) },
  );
}
