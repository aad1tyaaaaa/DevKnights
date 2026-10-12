// Extension Development Host smoke test: `npm run test:smoke` (downloads a VS Code build on first run).
// Runs inside VS Code; verifies activation, contributed commands and the sidebar view.
const assert = require('node:assert');
const vscode = require('vscode');

exports.run = async function run() {
  const ext = vscode.extensions.all.find((e) => e.packageJSON.name === 'provenyx-security');
  assert.ok(ext, 'extension not loaded');
  await ext.activate();
  assert.ok(ext.isActive, 'extension did not activate');

  const commands = await vscode.commands.getCommands(true);
  for (const id of ['provenyx.scanDependencies', 'provenyx.showFindings', 'provenyx.openDashboard', 'provenyx.checkBackend']) {
    assert.ok(commands.includes(id), `missing command ${id}`);
  }

  // Focusing the tree view throws if the view is not contributed/registered.
  await vscode.commands.executeCommand('provenyx.showFindings');
  await vscode.commands.executeCommand('provenyx.checkBackend');

  const lockfiles = await vscode.workspace.findFiles('**/package-lock.json', '**/node_modules/**');
  assert.strictEqual(lockfiles.length, 1, 'sample lockfile not found in workspace');
  console.log('[provenyx smoke] OK: activated, 4 commands registered, sidebar view focused, lockfile located');
};
