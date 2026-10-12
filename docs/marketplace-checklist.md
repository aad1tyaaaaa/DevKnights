# VS Code Marketplace checklist

Nothing has been published. Only item 10 remains, and it needs the publisher's Personal Access Token; everything else is done and verified.

| # | Item | Status | Action |
| --- | --- | --- | --- |
| 1 | **Publisher ID** | ✅ Done | `"publisher": "Provenyx"`. The publisher must exist at https://marketplace.visualstudio.com/manage under that exact ID. |
| 2 | **Extension icon** | ✅ Done | `extension/images/icon.png` (256×256 PNG). |
| 3 | **README** | ✅ Done | Features, screenshots (real scans of the labelled demo fixtures, live local chain), privacy, settings, requirements, support. Images are HTTPS links to `docs/images/` on `main`, so they render once `main` is pushed. |
| 4 | **License** | ✅ Done | MIT (`extension/LICENSE`, root `LICENSE`, `"license": "MIT"`). |
| 5 | **Repository URL** | ✅ Done | `repository`, `bugs`, and `homepage` point to `github.com/aad1tyaaaaa/DevKnights`. The `--allow-missing-repository` flag has been removed. |
| 6 | **Privacy disclosure** | ✅ Done | “Privacy and safety” section in the README. Update it if telemetry is ever added (must honour `vscode.env.isTelemetryEnabled`). |
| 7 | **Support contact** | ✅ Done | GitHub issues link in `bugs` and in the README. Add a support email if you have one. |
| 8 | **`.vscodeignore`** | ✅ Verified | The VSIX contains only `dist/extension.js`, `package.json`, README, CHANGELOG, LICENSE, and `images/`. |
| 9 | **VSIX packaging** | ✅ Verified | `npm run package:extension` builds `provenyx-security-0.1.0.vsix` (9 files, ~12 KB). It installs into a clean, isolated VS Code profile, and the minified bundle passes the smoke test. |
| 10 | **Publish** | ⏳ Needs your token | `cd extension && npx vsce login Provenyx` (paste a Personal Access Token with *Marketplace → Manage* scope; never commit it), then `npx vsce publish`. Or upload `provenyx-security-0.1.0.vsix` at https://marketplace.visualstudio.com/manage/publishers/Provenyx. |
| 11 | **Preview flag and banner** | ✅ Done | `"preview": true`; `galleryBanner` uses the forest green. |
| 12 | **CHANGELOG** | ✅ Done | `extension/CHANGELOG.md`. |
| 13 | **Backend availability** | ✅ Documented | The README states that the Marketplace hosts only the extension. Users need their own API (default `http://localhost:8000`). Decide on a hosted API and its privacy terms before a general release. |
