import * as vscode from 'vscode';
import type { BackendState, LastScan } from '../types';
import { projectName } from '../utils/workspace';

export class FindingsTreeProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
  private readonly changed = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.changed.event;

  private backend: BackendState = 'unknown';
  private lastScan: LastScan = { kind: 'none' };

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
      case 'failed':
        scan = item('Last scan', `Failed at ${this.lastScan.at.toLocaleTimeString()}`, 'warning');
        scan.tooltip = this.lastScan.message;
        break;
    }

    const findings = new vscode.TreeItem('No dependency findings yet');
    findings.iconPath = new vscode.ThemeIcon('info');
    findings.tooltip = 'Dependency analysis is not implemented yet. Scans currently only validate and submit the lockfile.';

    return [project, backend, scan, findings];
  }
}

function item(label: string, description: string, icon: string): vscode.TreeItem {
  const t = new vscode.TreeItem(label);
  t.description = description;
  t.iconPath = new vscode.ThemeIcon(icon);
  return t;
}
