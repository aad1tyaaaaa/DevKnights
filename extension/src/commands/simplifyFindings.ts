import * as vscode from 'vscode';
import type { FindingsTreeProvider } from '../providers/findingsTreeProvider';
import { simplifyScan } from '../services/apiClient';
import { requireGitHubSession } from '../services/githubAuth';
import { showApiError } from '../utils/errors';

/**
 * Calls the OpenRouter LLM connector to simplify scan findings and changes into plain, easy-to-understand English.
 */
export async function simplifyFindingsCommand(tree: FindingsTreeProvider): Promise<void> {
  const lastScan = tree.lastScan;
  if (lastScan.kind !== 'complete') {
    void vscode.window.showInformationMessage('Provenyx: Run a dependency scan first to simplify its findings.');
    return;
  }

  const session = await requireGitHubSession();
  if (!session) return;

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: 'Provenyx: Simplifying findings in plain English via OpenRouter…',
    },
    async () => {
      try {
        const result = await simplifyScan(lastScan.scan.scan_id, session.accessToken, 'English');
        const doc = await vscode.workspace.openTextDocument({
          language: 'markdown',
          content: renderSimplifiedMarkdown(result),
        });
        await vscode.window.showTextDocument(doc, { preview: true, viewColumn: vscode.ViewColumn.Beside });
      } catch (err) {
        showApiError(err);
      }
    },
  );
}

function renderSimplifiedMarkdown(res: import('../types').SimplifiedScanResponse): string {
  const providerLabel = res.provider === 'openrouter' ? `OpenRouter LLM (${res.model})` : 'Deterministic Explanation';
  const lines: string[] = [
    '# 🛡️ Provenyx Plain-English Security Summary',
    `*Powered by ${providerLabel}*`,
    '',
    `## **${res.headline}**`,
    '',
    `> **Risk Level**: **${res.risk_level.toUpperCase()}**`,
    '',
    res.summary,
    '',
  ];

  if (res.key_points && res.key_points.length > 0) {
    lines.push('### 🔑 Key Points');
    for (const point of res.key_points) {
      lines.push(`- ${point}`);
    }
    lines.push('');
  }

  if (res.simplified_findings && res.simplified_findings.length > 0) {
    lines.push('### 📦 Findings Simplified');
    for (const f of res.simplified_findings) {
      lines.push(`#### \`${f.package}@${f.version}\`: ${f.title}`);
      lines.push(`- **What happened**: ${f.what_happened}`);
      lines.push(`- **Why it matters**: ${f.why_it_matters}`);
      lines.push(`- **Recommendation**: ${f.recommendation}`);
      lines.push('');
    }
  }

  if (res.action_items && res.action_items.length > 0) {
    lines.push('### 💡 Recommended Actions');
    for (const action of res.action_items) {
      lines.push(`1. ${action}`);
    }
    lines.push('');
  }

  return lines.join('\n');
}
