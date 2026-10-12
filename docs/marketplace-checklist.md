# VS Code Marketplace checklist

Nothing has been published. Only items 1, 4, and 10 need a human decision or account; everything else is done and verified.

| # | Item | Status | Action |
| --- | --- | --- | --- |
| 1 | **Publisher ID** | ⛔ Needs account | `extension/package.json` has the placeholder `"publisher": "your-publisher-id"`. Create a publisher at https://marketplace.visualstudio.com/manage (Microsoft account + Azure DevOps organisation) and set the real ID. Publisher IDs allow letters, digits, and hyphens only. |
| 2 | **Extension icon** | ✅ Done | `extension/images/icon.png` (256×256 PNG). |
| 3 | **README** | ✅ Done | Features, privacy, settings, requirements, support. Screenshots are still to add once real (non-synthetic) results exist. Relative image paths are rewritten by vsce from the repository URL. |
| 4 | **License** | ⛔ Needs decision | `extension/LICENSE` is an all-rights-reserved placeholder. Choose a license and update `"license"` in `package.json`. |
| 5 | **Repository URL** | ✅ Done | `repository`, `bugs`, and `homepage` point to `github.com/aad1tyaaaaa/DevKnights`. The `--allow-missing-repository` flag has been removed. |
| 6 | **Privacy disclosure** | ✅ Done | “Privacy and safety” section in the README. Update it if telemetry is ever added (must honour `vscode.env.isTelemetryEnabled`). |
| 7 | **Support contact** | ✅ Done | GitHub issues link in `bugs` and in the README. Add a support email if you have one. |
| 8 | **`.vscodeignore`** | ✅ Verified | The VSIX contains only `dist/extension.js`, `package.json`, README, CHANGELOG, LICENSE, and `images/`. |
| 9 | **VSIX packaging** | ✅ Verified | `npm run package:extension` builds `provenyx-security-0.1.0.vsix` (9 files, ~12 KB). It installs into a clean, isolated VS Code profile, and the minified bundle passes the smoke test. |
| 10 | **Publish** | ⏳ Blocked on 1 and 4 | `npx vsce login <publisher-id>`, then `npx vsce publish`. This needs a Personal Access Token with *Marketplace → Manage* scope; never commit it. Alternatively, upload the VSIX in the publisher portal. |
| 11 | **Preview flag and banner** | ✅ Done | `"preview": true`; `galleryBanner` uses the forest green. |
| 12 | **CHANGELOG** | ✅ Done | `extension/CHANGELOG.md`. |
| 13 | **Backend availability** | ✅ Documented | The README states that the Marketplace hosts only the extension. Users need their own API (default `http://localhost:8000`). Decide on a hosted API and its privacy terms before a general release. |
