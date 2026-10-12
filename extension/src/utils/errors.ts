import * as vscode from 'vscode';
import { ApiError } from '../services/apiClient';

export const START_BACKEND_COMMAND = 'npm run dev:backend';

/** Shows an API error; when the API is unreachable, offers concrete ways to fix it. */
export async function showApiError(err: unknown): Promise<void> {
  const message = err instanceof ApiError ? err.message : 'Unexpected error while contacting the Provenyx API.';
  if (!(err instanceof ApiError && err.unreachable)) {
    void vscode.window.showErrorMessage(`Provenyx: ${message}`);
    return;
  }
  const retry = 'Retry';
  const copy = 'Copy Start Command';
  const settings = 'Open Settings';
  const pick = await vscode.window.showErrorMessage(
    `Provenyx: ${message} Start it from the Provenyx repository with "${START_BACKEND_COMMAND}", or point provenyx.apiBaseUrl at a running API.`,
    retry,
    copy,
    settings,
  );
  if (pick === retry) await vscode.commands.executeCommand('provenyx.checkBackend');
  if (pick === copy) {
    await vscode.env.clipboard.writeText(START_BACKEND_COMMAND);
    void vscode.window.showInformationMessage(`Provenyx: Copied "${START_BACKEND_COMMAND}". Run it in a terminal at the Provenyx repository root.`);
  }
  if (pick === settings) await vscode.commands.executeCommand('workbench.action.openSettings', 'provenyx.apiBaseUrl');
}
