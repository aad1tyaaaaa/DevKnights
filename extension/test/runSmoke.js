const path = require('node:path');
const { runTests } = require('@vscode/test-electron');

runTests({
  extensionDevelopmentPath: path.resolve(__dirname, '..'),
  extensionTestsPath: path.resolve(__dirname, 'smoke.js'),
  launchArgs: [path.resolve(__dirname, '../../demo/sample-project'), '--disable-extensions'],
}).catch((err) => {
  console.error(err);
  process.exit(1);
});
