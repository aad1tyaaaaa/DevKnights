import * as vscode from 'vscode';
import { createGitHubBrowserHandoff } from '../services/apiClient';
import { requireGitHubSession } from '../services/githubAuth';
import { showApiError } from './errors';

export function dashboardUrl(path = ''): string {
  const base = vscode.workspace.getConfiguration('provenyx').get<string>('dashboardUrl', 'http://localhost:3000');
  return base.replace(/\/+$/, '') + path;
}

export function scanPath(scanId: string, findingId?: string): string {
  const query = findingId ? `?finding=${encodeURIComponent(findingId)}` : '';
  return `/scans/${encodeURIComponent(scanId)}${query}`;
}

/** Opens a dashboard page in the browser. Only http(s) URLs are allowed. */
export async function openDashboard(path = ''): Promise<void> {
  const session = await requireGitHubSession();
  if (!session) return;

  let url: string;
  try {
    url = (await createGitHubBrowserHandoff(session.accessToken, path || '/dashboard')).url;
  } catch (err) {
    void showApiError(err);
    return;
  }
  let uri: vscode.Uri;
  try {
    uri = vscode.Uri.parse(url, true);
  } catch {
    uri = vscode.Uri.parse('invalid:');
  }
  if (uri.scheme !== 'http' && uri.scheme !== 'https') {
    void vscode.window.showErrorMessage(`Provenyx: "${url}" is not a valid dashboard URL. Check the provenyx.dashboardUrl setting.`);
    return;
  }
  await vscode.env.openExternal(uri);
}
