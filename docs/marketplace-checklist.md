# VS Code Marketplace checklist

Nothing has been published. Complete every item before running `vsce publish`.

| # | Item | Status | Action |
| --- | --- | --- | --- |
| 1 | **Publisher ID** | ⛔ Placeholder | `extension/package.json` has `"publisher": "your-publisher-id"`. Create a publisher at https://marketplace.visualstudio.com/manage (requires a Microsoft account + Azure DevOps organisation), then set the real ID. Note: publisher IDs allow letters, digits and hyphens only — `YOUR_PUBLISHER_ID` is rejected by vsce. |
| 2 | **Extension icon** | ✅ Done | `extension/images/icon.png` (256×256 PNG). Replace with final brand artwork if available. SVG icons are not allowed. |
| 3 | **README** | ✅ Draft | `extension/README.md`. Add screenshots/GIFs of the sidebar before publishing; image URLs must be HTTPS. |
| 4 | **License** | ⛔ Placeholder | `extension/LICENSE` is an all-rights-reserved placeholder. Choose a license and update `"license"` in `package.json`. |
| 5 | **Repository URL** | ⛔ Missing | Add `"repository": { "type": "git", "url": "https://github.com/<org>/<repo>" }`, then drop `--allow-missing-repository` from the `vsix` script. |
| 6 | **Privacy disclosure** | ✅ Draft | “Privacy and safety” section in the extension README. Review with legal before a hosted API is offered; update if telemetry is ever added (must honour `vscode.env.isTelemetryEnabled`). |
| 7 | **Support contact** | ⛔ Missing | Add `"bugs": { "url": "…" }` and/or `"homepage"`, and a support email in README. |
| 8 | **`.vscodeignore`** | ✅ Done | VSIX contains only `dist/extension.js`, `package.json`, README, LICENSE, `images/` (verify with `npx vsce ls --no-dependencies`). |
| 9 | **VSIX packaging** | ✅ Verified | `npm run package:extension` produces `provenyx-security-0.1.0.vsix` (~10 KB). |
| 10 | **Listing validation** | ⏳ Pending | After 1/4/5/7: run `npx vsce package` *without* `--allow-missing-repository`, install the VSIX in a clean VS Code profile, check categories/keywords/galleryBanner, then `npx vsce publish` (requires a Personal Access Token with *Marketplace → Manage* scope — never commit it). |
| 11 | **Default API URL** | ⏳ Decide | Default `provenyx.apiBaseUrl` is `http://localhost:8000`, which only works for users running the backend themselves. Decide on a hosted API and its privacy terms before a public release. |
| 12 | **Version / CHANGELOG** | ⏳ Pending | Add `extension/CHANGELOG.md`; mark the listing as *Preview* (`"preview": true`) while analysis is incomplete. |
