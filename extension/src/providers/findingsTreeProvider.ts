import * as vscode from 'vscode';
import type { BackendState, Finding, LastScan, Severity } from '../types';
import { apiBaseUrl } from '../services/apiClient';
import { scanPath } from '../utils/dashboard';
import { START_BACKEND_COMMAND } from '../utils/errors';
import { projectName } from '../utils/workspace';

const SEVERITY_ORDER: Severity[] = ['high', 'medium', 'low', 'info'];
const SEVERITY_ICON: Record<Severity, vscode.ThemeIcon> = {
  high: new vscode.ThemeIcon('error', new vscode.ThemeColor('problemsErrorIcon.foreground')),
  medium: new vscode.ThemeIcon('warning', new vscode.ThemeColor('problemsWarningIcon.foreground')),
  low: new vscode.ThemeIcon('info', new vscode.ThemeColor('problemsInfoIcon.foreground')),
  info: new vscode.ThemeIcon('circle-outline'),
};

type Node = vscode.TreeItem & { children?: vscode.TreeItem[] };

export class FindingsTreeProvider implements vscode.TreeDataProvider<Node> {
  private readonly changed = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.changed.event;

  backend: BackendState = 'unknown';
  lastScan: LastScan = { kind: 'none' };

  setBackend(state: BackendState): void {
    this.backend = state;
    this.changed.fire();
  }

  setLastScan(scan: LastScan): void {
    this.lastScan = scan;
    this.changed.fire();
  }

  refresh(): void {
    this.changed.fire();
  }

  getTreeItem(item: Node): vscode.TreeItem {
    return item;
  }

  getChildren(parent?: Node): Node[] {
    if (parent) return parent.children ?? [];

    const project = item('Project', projectName() ?? 'No folder open', 'folder');

    const backend = {
      unknown: item('Backend', 'Not checked', 'circle-outline'),
      connected: item('Backend', 'Connected', 'pass'),
      unreachable: item('Backend', 'Unreachable — click to retry', 'error'),
    }[this.backend];
    backend.tooltip =
      this.backend === 'unreachable'
        ? `Cannot reach the Provenyx API at ${apiBaseUrl()}.
Start it from the Provenyx repository: ${START_BACKEND_COMMAND}
or change the provenyx.apiBaseUrl setting.`
        : `Provenyx API: ${apiBaseUrl()}`;
    backend.command = { command: 'provenyx.checkBackend', title: 'Check Backend Connection' };

    return [project, backend, this.scanItem(), ...this.findingItems()];
  }

  private scanItem(): Node {
    const s = this.lastScan;
    switch (s.kind) {
      case 'none':
        return item('Last scan', 'Not run yet', 'history');
      case 'in-progress': {
        const t = item('Last scan', `${s.status === 'analyzing' ? 'Analyzing' : 'Accepted'} at ${s.at.toLocaleTimeString()}`, s.status === 'analyzing' ? 'sync~spin' : 'check');
        t.tooltip = `Scan ID: ${s.scanId}\n${s.message}`;
        t.command = openScan(s.scanId);
        return t;
      }
      case 'complete': {
        const sum = s.scan.summary;
        const t = item('Last scan', `Complete at ${s.at.toLocaleTimeString()}`, 'pass-filled');
        t.tooltip = `Scan ID: ${s.scan.scan_id}` + (sum ? `\n${sum.packages} packages (${sum.direct} direct, ${sum.transitive} transitive)` : '');
        t.command = openScan(s.scan.scan_id);
        return t;
      }
      case 'failed': {
        const t = item('Last scan', `Failed at ${s.at.toLocaleTimeString()}`, 'warning');
        t.tooltip = s.message;
        return t;
      }
    }
  }

  private findingItems(): Node[] {
    const s = this.lastScan;
    if (s.kind !== 'complete' || s.findings === undefined) {
      const t = new vscode.TreeItem('No dependency findings yet') as Node;
      t.iconPath = new vscode.ThemeIcon('info');
      t.tooltip =
        s.kind === 'in-progress'
          ? 'The scan was accepted. Findings appear here once the API provides analysis results.'
          : 'Run “Provenyx: Scan Dependencies” to analyze this project.';
      return [t];
    }
    if (s.findings.length === 0) {
      const t = new vscode.TreeItem('No findings reported for this scan') as Node;
      t.iconPath = new vscode.ThemeIcon('pass');
      t.tooltip = 'No rule matched. This is not a guarantee that every dependency is safe.';
      return [t];
    }

    const sorted = [...s.findings].sort(
      (a, b) => effectivePriority(b) - effectivePriority(a) || SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity),
    );
    const group = new vscode.TreeItem(`Findings (${sorted.length})`, vscode.TreeItemCollapsibleState.Expanded) as Node;
    group.iconPath = new vscode.ThemeIcon('list-tree');
    group.children = sorted.map((f) => findingItem(s.scan.scan_id, f));
    return [group];
  }
}

function findingItem(scanId: string, f: Finding): vscode.TreeItem {
  const t = new vscode.TreeItem(`${f.package}@${f.version}`);
  t.description = f.title;
  t.iconPath = SEVERITY_ICON[f.severity] ?? SEVERITY_ICON.info;
  const md = new vscode.MarkdownString();
  md.appendMarkdown(`**${f.title}**\n\n`);
  const ranking = f.ranking_source === 'gemini' && f.ai_priority_score != null
    ? `Gemini: ${f.ai_priority_score}/100 · Rule score: ${f.priority_score}/100`
    : `Priority: ${f.priority_score}/100`;
  md.appendText(`Severity: ${f.severity} · Confidence: ${f.confidence} · ${ranking} · Rule: ${f.rule_id}\n\n${f.explanation}`);
  if (f.ranking_source === 'gemini' && f.ai_rationale) md.appendText(`\n\nGemini rationale: ${f.ai_rationale}`);
  if (f.paths[0]) md.appendText(`\n\nPath: ${f.paths[0].join(' → ')}`);
  t.tooltip = md;
  t.command = openScan(scanId, f.id);
  return t;
}

function effectivePriority(finding: Finding): number {
  return finding.ranking_source === 'gemini' && finding.ai_priority_score != null
    ? finding.ai_priority_score
    : finding.priority_score;
}

function openScan(scanId: string, findingId?: string): vscode.Command {
  return { command: 'provenyx.openDashboard', title: 'Open in Dashboard', arguments: [scanPath(scanId, findingId)] };
}

function item(label: string, description: string, icon: string): Node {
  const t = new vscode.TreeItem(label) as Node;
  t.description = description;
  t.iconPath = new vscode.ThemeIcon(icon);
  return t;
}
