const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { runTests } = require('@vscode/test-electron');

const extensionDevelopmentPath = path.resolve(__dirname, '..');

async function main() {
  await runTests({
    extensionDevelopmentPath,
    extensionTestsPath: path.resolve(__dirname, 'smoke.js'),
    launchArgs: [path.resolve(__dirname, '../../demo/sample-project'), '--disable-extensions'],
  });

  const empty = fs.mkdtempSync(path.join(os.tmpdir(), 'provenyx-empty-'));
  try {
    await runTests({
      extensionDevelopmentPath,
      extensionTestsPath: path.resolve(__dirname, 'smoke-empty.js'),
      launchArgs: [empty, '--disable-extensions'],
    });
  } finally {
    fs.rmSync(empty, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
