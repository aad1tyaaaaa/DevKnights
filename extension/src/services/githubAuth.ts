import * as vscode from 'vscode';

const GITHUB_SCOPES = ['read:user', 'repo'];
const AUTH_PROVIDER = process.env.PROVENYX_AUTH_PROVIDER ?? 'github';
let pendingSession: Thenable<vscode.AuthenticationSession | undefined> | undefined;

export function githubSession(createIfNone: boolean): Thenable<vscode.AuthenticationSession | undefined> {
  if (AUTH_PROVIDER === 'provenyx-test') {
    return Promise.resolve({
      id: 'synthetic-session',
      accessToken: 'synthetic-github-token',
      account: { id: 'synthetic-user', label: 'Synthetic User' },
      scopes: GITHUB_SCOPES,
    });
  }
  if (!pendingSession) {
    pendingSession = Promise.resolve(vscode.authentication.getSession(AUTH_PROVIDER, GITHUB_SCOPES, { createIfNone })).finally(
      () => {
        pendingSession = undefined;
      },
    );
  }
  return pendingSession;
}

export async function requireGitHubSession(): Promise<vscode.AuthenticationSession | undefined> {
  const session = await githubSession(true);
  if (!session) {
    void vscode.window.showWarningMessage('Provenyx: Sign in to GitHub to scan dependencies.');
  }
  return session;
}