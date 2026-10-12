// Extension Development Host smoke test: `npm run test:smoke` (downloads a VS Code build on first run).
// Runs inside VS Code against a throwaway in-test HTTP server that implements docs/api-contract.md.
// All data served below is SYNTHETIC test data and never leaves this test.
const assert = require('node:assert');
const fs = require('node:fs');
const http = require('node:http');
const vscode = require('vscode');

const SCAN_ID = '00000000-0000-4000-8000-000000000001';
const SYNTHETIC_FINDING = {
  id: 'f-1',
  rule_id: 'synthetic-test-rule',
  package: 'synthetic-pkg',
  version: '0.0.1',
  severity: 'medium',
  confidence: 'high',
  priority_score: 60,
  title: 'SYNTHETIC test finding',
  explanation: 'Test fixture only.',
  evidence: [{ source: 'lockfile', field: 'test', value: 'test', observed_at: '2026-10-12T00:00:00Z' }],
  paths: [['root', 'synthetic-pkg@0.0.1']],
};

/** mode "phase1": only health + POST /api/scans exist (older backend). mode "full": scan status + findings like the current backend. */
function startFakeApi(mode) {
  const server = http.createServer((req, res) => {
    const send = (status, body) => {
      res.writeHead(status, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(body));
    };
    let body = '';
    req.on('data', (c) => (body += c));
    req.on('end', () => {
      if (req.method === 'GET' && req.url === '/health') return send(200, { status: 'ok', service: 'provenyx-api', version: '0.1.0' });
      if (req.method === 'POST' && req.url === '/api/scans') {
        const parsed = JSON.parse(body);
        assert.strictEqual(parsed.lockfile.lockfileVersion, 3, 'extension must send the parsed lockfile');
        server.lastProjectName = parsed.project_name;
        server.posts = (server.posts ?? 0) + 1;
        return send(202, { scan_id: SCAN_ID, status: 'accepted', message: 'Lockfile received.' });
      }
      if (mode === 'full' && req.url === `/api/scans/${SCAN_ID}`) {
        return send(200, {
          scan_id: SCAN_ID, status: 'complete', created_at: new Date().toISOString(), project_name: 'x', error: null,
          summary: { packages: 2, direct: 1, transitive: 1, findings: 1 }, warnings: [],
        });
      }
      if (mode === 'full' && req.url === `/api/scans/${SCAN_ID}/findings`) return send(200, [SYNTHETIC_FINDING]);
      send(404, { detail: 'Not Found' });
    });
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)));
}

async function useApi(url) {
  await vscode.workspace.getConfiguration('provenyx').update('apiBaseUrl', url, vscode.ConfigurationTarget.Global);
}

const labels = (items) => items.map((i) => `${i.label}${i.description ? ` | ${i.description}` : ''}`);

exports.run = async function run() {
  try {
    await runChecks();
  } catch (err) {
    console.error('[provenyx smoke] FAILED:', err && err.stack ? err.stack : err);
    throw err;
  }
};

async function runChecks() {
  const ext = vscode.extensions.all.find((e) => e.packageJSON.name === 'provenyx-security');
  assert.ok(ext, 'extension not loaded');
  const { tree } = await ext.activate();
  assert.ok(ext.isActive, 'extension did not activate');

  const commands = await vscode.commands.getCommands(true);
  for (const id of ['provenyx.scanDependencies', 'provenyx.showFindings', 'provenyx.openDashboard', 'provenyx.checkBackend']) {
    assert.ok(commands.includes(id), `missing command ${id}`);
  }
  await vscode.commands.executeCommand('provenyx.showFindings'); // throws if the view is not registered

  const lockfiles = await vscode.workspace.findFiles('**/package-lock.json', '**/node_modules/**');
  assert.strictEqual(lockfiles.length, 1, 'sample lockfile not found in workspace');

  // Auto-confirm the consent dialog (and only that dialog) so the flow can run unattended.
  const originalInfo = vscode.window.showInformationMessage;
  let consentShown = 0;
  let watcherPrompts = 0;
  vscode.window.showInformationMessage = (message, ...rest) => {
    if (/changed\. Scan it\?/.test(message)) watcherPrompts++;
    const opts = rest[0];
    if (opts && typeof opts === 'object' && opts.modal) {
      consentShown++;
      assert.match(opts.detail, /Only package-lock\.json is sent/);
      return Promise.resolve('Send to Provenyx API');
    }
    return Promise.resolve(undefined);
  };

  try {
    // 1. Backend like today's Phase 1 API: scan accepted, no findings endpoint yet.
    let api = await startFakeApi('phase1');
    await useApi(`http://127.0.0.1:${api.address().port}`);
    await vscode.commands.executeCommand('provenyx.scanDependencies');
    assert.strictEqual(consentShown, 1, 'consent dialog must be shown before sending');
    assert.strictEqual(api.lastProjectName, 'provenyx-sample-project');
    assert.strictEqual(tree.backend, 'connected');
    assert.strictEqual(tree.lastScan.kind, 'in-progress');
    assert.ok(labels(tree.getChildren()).includes('No dependency findings yet'), labels(tree.getChildren()).join(', '));
    api.close();

    // 2. Full contract: scan completes and findings appear in the sidebar.
    api = await startFakeApi('full');
    await useApi(`http://127.0.0.1:${api.address().port}`);
    await vscode.commands.executeCommand('provenyx.scanDependencies');
    assert.strictEqual(tree.lastScan.kind, 'complete');
    const group = tree.getChildren().find((i) => String(i.label).startsWith('Findings'));
    assert.ok(group, 'findings group missing');
    assert.strictEqual(group.label, 'Findings (1)');
    const [finding] = tree.getChildren(group);
    assert.strictEqual(finding.label, 'synthetic-pkg@0.0.1');
    assert.deepStrictEqual(finding.command.arguments, [`/scans/${SCAN_ID}?finding=f-1`]);
    api.close();

    // 3. Backend offline: no crash, clear state.
    await useApi('http://127.0.0.1:9');
    await vscode.commands.executeCommand('provenyx.checkBackend');
    assert.strictEqual(tree.backend, 'unreachable');
    await vscode.commands.executeCommand('provenyx.scanDependencies');
    assert.strictEqual(tree.lastScan.kind, 'failed');
    assert.match(tree.lastScan.message, /Cannot reach the Provenyx API/);

    // 4. Lockfile watcher (autoScanEnabled): a burst of writes gives ONE prompt, and declining sends nothing.
    api = await startFakeApi('full');
    await useApi(`http://127.0.0.1:${api.address().port}`);
    await vscode.workspace.getConfiguration('provenyx').update('autoScanEnabled', true, vscode.ConfigurationTarget.Global);
    const lockPath = lockfiles[0].fsPath;
    const original = fs.readFileSync(lockPath, 'utf8');
    for (let i = 0; i < 3; i++) {
      fs.writeFileSync(lockPath, original);
      await new Promise((r) => setTimeout(r, 150));
    }
    await new Promise((r) => setTimeout(r, 3500)); // > 1.5 s debounce
    assert.strictEqual(watcherPrompts, 1, `watcher prompts: ${watcherPrompts}`);
    assert.strictEqual(api.posts ?? 0, 0, 'declining the watcher prompt must not send the lockfile');
    await vscode.workspace.getConfiguration('provenyx').update('autoScanEnabled', undefined, vscode.ConfigurationTarget.Global);
    fs.writeFileSync(lockPath, original);
    await new Promise((r) => setTimeout(r, 2000));
    assert.strictEqual(watcherPrompts, 1, 'watcher must stay silent when autoScanEnabled is off');
    api.close();

    // 5. Optional: the real backend, if PROVENYX_SMOKE_REAL_API is set (e.g. http://127.0.0.1:8000).
    const real = process.env.PROVENYX_SMOKE_REAL_API;
    if (real) {
      await useApi(real);
      await vscode.commands.executeCommand('provenyx.scanDependencies');
      const s = tree.lastScan;
      assert.strictEqual(s.kind, 'complete', `real API: ${JSON.stringify(s)}`);
      assert.ok(Array.isArray(s.findings), 'real API: findings should load after completion');
      console.log(`[provenyx smoke] real API ${real}: scan ${s.scan.scan_id} complete, ${s.scan.summary?.packages} packages, ${s.findings.length} findings`);
    }
  } finally {
    vscode.window.showInformationMessage = originalInfo;
    await useApi(undefined);
  }

  console.log('[provenyx smoke] OK: activation, commands, consent, scan→findings, offline backend, debounced watcher');
};
