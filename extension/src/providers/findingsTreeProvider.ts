import * as vscode from 'vscode';
import type { BackendState, Finding, LastScan } from '../types';
import { projectName } from '../utils/workspace';

export class FindingsTreeProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
  private readonly changed = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.changed.event;

  private backend: BackendState = 'unknown';
  private lastScan: LastScan = { kind: 'none' };
  private findings: Finding[] = [];

  setBackend(state: BackendState): void {
    this.backend = state;
    this.changed.fire();
  }

  setLastScan(scan: LastScan): void {
    this.lastScan = scan;
    this.changed.fire();
  }

  setFindings(findings: Finding[]): void {
    this.findings = findings;
    this.changed.fire();
  }

  refresh(): void {
    this.changed.fire();
  }

  getTreeItem(item: vscode.TreeItem): vscode.TreeItem {
    return item;
  }

  getChildren(): vscode.TreeItem[] {
    const project = item('Project', projectName() ?? 'No folder open', 'folder');

    const backend = {
      unknown: item('Backend', 'Not checked', 'circle-outline'),
      connected: item('Backend', 'Connected', 'pass'),
      unreachable: item('Backend', 'Unreachable', 'error'),
    }[this.backend];
    backend.command = { command: 'provenyx.checkBackend', title: 'Check Backend Connection' };

    let scan: vscode.TreeItem;
    switch (this.lastScan.kind) {
      case 'none':
        scan = item('Last scan', 'Not run yet', 'history');
        break;
      case 'accepted':
        scan = item('Last scan', `Accepted at ${this.lastScan.at.toLocaleTimeString()}`, 'check');
        scan.tooltip = `Scan ID: ${this.lastScan.scanId}\n${this.lastScan.message}`;
        break;
      case 'complete':
        scan = item('Last scan', `Complete · ${this.lastScan.findingCount} finding(s)`, 'check-all');
        scan.tooltip = `Scan ID: ${this.lastScan.scanId}\nCompleted at ${this.lastScan.at.toLocaleTimeString()}`;
        scan.command = {
          command: 'provenyx.openDashboard',
          title: 'Open Scan Dashboard',
          arguments: [this.lastScan.scanId],
        };
        break;
      case 'failed':
        scan = item('Last scan', `Failed at ${this.lastScan.at.toLocaleTimeString()}`, 'warning');
        scan.tooltip = this.lastScan.message;
        break;
    }

    const findings = this.findings.length === 0
      ? [noFindingsItem()]
      : this.findings.map((finding) => findingItem(finding, this.lastScan));

    return [project, backend, scan, ...findings];
  }
}

function noFindingsItem(): vscode.TreeItem {
  const finding = new vscode.TreeItem('No dependency findings');
  finding.iconPath = new vscode.ThemeIcon('pass');
  finding.tooltip = 'No evidence-backed findings were produced for the latest completed scan.';
  return finding;
}

function findingItem(finding: Finding, lastScan: LastScan): vscode.TreeItem {
  const icons = { info: 'info', low: 'warning', medium: 'issues', high: 'error' } as const;
  const item = new vscode.TreeItem(finding.title);
  item.description = `${finding.severity} · ${finding.package}@${finding.version}`;
  item.iconPath = new vscode.ThemeIcon(icons[finding.severity]);
  item.tooltip = [
    finding.explanation,
    `Confidence: ${finding.confidence}`,
    `Priority: ${finding.priority_score}/100`,
    ...finding.evidence.map((evidence) => `${evidence.source}: ${evidence.field}`),
  ].join('\n');
  if (lastScan.kind === 'complete') {
    item.command = {
      command: 'provenyx.openDashboard',
      title: 'Open Finding in Dashboard',
      arguments: [lastScan.scanId],
    };
  }
  return item;
}

function item(label: string, description: string, icon: string): vscode.TreeItem {
  const t = new vscode.TreeItem(label);
  t.description = description;
  t.iconPath = new vscode.ThemeIcon(icon);
  return t;
}
