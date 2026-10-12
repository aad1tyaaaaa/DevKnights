# Provenyx — Progress Log

Live status of the work. The plan and ownership are in [PROVENYX_END_TO_END_PHASES.md](PROVENYX_END_TO_END_PHASES.md); this file records what is **actually done and verified**.

**Legend:** ✅ done and verified · 🟡 in progress / partly verified · ⬜ not started · ⛔ blocked

## Summary

| Phase | Focus | Owner | Status |
|---|---|---|---|
| 1 | Foundation | Aaditya + Omkar | ✅ Done |
| 2 | VS Code extension | Aaditya | ✅ Done |
| 3 | Real npm scanner | Omkar | ⬜ Not started |
| 4 | Risk engine | Omkar | ⬜ Not started |
| 5 | Web dashboard | Aaditya | ✅ Done (UI); real data arrives with Phases 3–4 |
| 6 | Blockchain verification | Omkar + Aaditya | 🟡 Aaditya's part ✅ · Omkar's part ⬜ |
| 7 | Integration and testing | Both | ⬜ Not started |
| 8 | Marketplace and demo | Aaditya | 🟡 Ready; ⛔ blocked on publisher ID + license |

---

## Blockers and decisions needed

| Item | Who | Notes |
|---|---|---|
| ⛔ Marketplace publisher ID | Aaditya | Create the publisher (Microsoft account + Azure DevOps org) and set `publisher` in `extension/package.json`. |
| ⛔ License | Aaditya + Omkar | `extension/LICENSE` is an all-rights-reserved placeholder. Pick one and update the `license` field. |
| ⏳ Endpoints for real data | Omkar | `GET /api/scans`, `/api/scans/{id}`, `/graph`, `/findings`, `POST /api/releases/verify`, shapes in `docs/api-contract.md`. The extension and dashboard already consume them. |

## Handoff to Omkar

- **API shapes:** follow `docs/api-contract.md` exactly. The UI treats `404`/`405`/`501` as "not available yet", so endpoints can merge one at a time.
- **Contract:** run `npm --prefix contracts run node`, then `deploy:local`. Read `contracts/deployments/localhost.json` (address, chain id, ABI) and call `recordOf(releaseId)`.
- **Release id:** `releaseId = keccak256(utf8("name@version"))`. Reference implementation: `contracts/scripts/releaseId.ts`.
- **Anchoring for the demo:** put your canonical manifest hashes in `contracts/anchors.json`, then run `npm --prefix contracts run anchor:local`.

## Log

### 2026-10-12 — Phase 1 complete

- Monorepo created: `extension/`, `backend/`, `frontend/`, `contracts/`, `demo/`, `docs/`.
- Verified: 6 backend tests pass; extension type-checks, bundles, and passes the VS Code smoke test; frontend production build passes; 3 contract tests pass; VSIX packages.

### 2026-10-12 — Aaditya's phases (2, 5, 6, 8) started

Branch: `aaditya/phases-2-5-6-8`.

#### Phase 6 (Aaditya's part) — contract + deploy handoff ✅

- `ReleaseRegistry.sol` now stores `anchoredAt` per record and exposes `recordOf(releaseId)`. It also keeps `matches()`, the write-once rule, and the owner-only anchor.
- Added `scripts/releaseId.ts` as the reference for `keccak256(utf8("name@version"))`.
- `npm run deploy:local` writes `contracts/deployments/localhost.json` (address, chain id, ABI) for Omkar's backend.
- `npm run anchor:local` anchors hashes from `anchors.json`. It skips releases that are already anchored and refuses the all-zero placeholder.
- Verified: 5 contract tests pass. Deploy and anchor were run against a real `hardhat node` (chain 31337), including the skip and placeholder-refusal paths.

#### Phase 2 — extension ✅

- After a scan is accepted, the extension polls `GET /api/scans/{id}` and then loads `GET /api/scans/{id}/findings`. If the API doesn't provide these yet, it shows the honest "No dependency findings yet" state.
- The sidebar lists findings by severity with explanation tooltips. Clicking a finding opens `/scans/{id}?finding={fid}` in the dashboard.
- The "scan accepted" notification has an **Open in Dashboard** button. `provenyx.openDashboard` only allows http(s) URLs.
- Verified with the automated smoke test in a real VS Code instance (`npm --prefix extension run test:smoke`):
  - consent dialog shown before sending
  - Phase-1-style API: scan accepted, no findings claimed
  - full-contract API: scan completes and the sidebar shows the findings
  - backend offline: shown as *Unreachable*, scan fails cleanly, no crash
  - real FastAPI backend: scan accepted (`PROVENYX_SMOKE_REAL_API=http://127.0.0.1:8000`)
- Synthetic findings exist only inside the test's throwaway HTTP server.

#### Phase 5 — dashboard ✅ (UI)

- New pages:
  - `/scan/new`: lockfile upload with in-browser validation, an explicit consent checkbox naming the API URL, and the submit result.
  - `/scans/[id]`: polls while the scan runs; then shows metrics, a findings table with severity filter, a dependency graph (Cytoscape) and a package drawer (evidence, unknowns, paths, release verification).
- `/dashboard` and `/scans` show real scan history from `GET /api/scans`. Metrics appear only when the API returns real data; otherwise the page shows an honest "not available yet" state.
- Graph: zoom, pan, fit, node selection, and highlighted paths. Selecting a finding highlights its paths; selecting a package highlights everything that depends on it. Graphs over 400 packages are reduced to the project, direct dependencies, and packages involved in findings.
- Verified with 12 automated headless-Edge interaction checks (scripts kept outside the repo):
  - **Against a contract-shaped synthetic mock API:** dashboard metrics; deep link `?finding=` opens the drawer; graph renders; node click highlights dependents; severity filter; mismatch and no-record copy; in-progress polling; no horizontal scroll at 390px.
  - **Against the real FastAPI backend:** honest empty states; an invalid file is rejected in the browser; upload → consent → scan accepted; an unknown scan page says so honestly.
- Fixed while testing: visually hidden table header text was widening the page on phones (absolute `sr-only` span escaping its scroll container).

#### Phase 6 (Aaditya's part) — verification UI ✅

- `VerificationStatus` (in the package drawer) calls `POST /api/releases/verify` and shows match, mismatch, no record, or unavailable.
- Wording follows the rules: a match is not a safety verdict; no record is an evidence gap, not a risk signal.
- It shows the release id, current and anchored hashes, anchor time, registry address and chain, a "Local Hardhat demo chain" label, and the canonical manifest fields.

#### Phase 8 — Marketplace readiness 🟡

- `extension/package.json` now has `repository`, `bugs`, `homepage`, `preview: true` and `galleryBanner`. The `--allow-missing-repository` flag has been removed.
- Added `extension/CHANGELOG.md` and rewrote the README (features, privacy, settings, requirements, support).
- VSIX `provenyx-security-0.1.0.vsix` (9 files, 12 KB) installs into a clean, isolated VS Code profile. The shipped minified bundle passes the smoke test, including a real scan against the backend.
- Added `docs/demo-script.md` (setup, 7-step script with presenters, fallbacks) and refreshed `docs/marketplace-checklist.md`.
- Remaining: publisher ID and license (see Blockers), screenshots once real results exist, rehearsal and backup recording after Phase 7.

#### Verification snapshot (2026-10-12, branch `aaditya/phases-2-5-6-8`)

| Check | Result |
|---|---|
| Backend tests | ✅ 6 passed |
| Contract tests | ✅ 5 passing; deploy + anchor on a live `hardhat node` |
| Extension smoke test (dev and shipped bundle) | ✅ all scenarios, including the real backend |
| VSIX package + clean-profile install | ✅ |
| Frontend production build (type-checked) | ✅ |
| Dashboard interaction checks | ✅ 12/12 |
