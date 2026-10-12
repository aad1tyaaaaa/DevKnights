# Provenyx — Progress Log

Live status of the work. The plan and ownership are in [PROVENYX_END_TO_END_PHASES.md](PROVENYX_END_TO_END_PHASES.md); this file records what is **actually done and verified**.

**Legend:** ✅ done and verified · 🟡 in progress / partly verified · ⬜ not started · ⛔ blocked

## Summary

| Phase | Focus | Owner | Status |
|---|---|---|---|
| 1 | Foundation | Aaditya + Omkar | ✅ Done |
| 2 | VS Code extension | Aaditya | ✅ Done |
| 3 | Real npm scanner | Omkar | ✅ Done |
| 4 | Risk engine | Omkar | ✅ Done |
| 5 | Web dashboard | Aaditya | ✅ Done — verified with real backend data |
| 6 | Blockchain verification | Omkar + Aaditya | ✅ Done |
| 7 | Integration and testing | Both | ✅ Done |
| 8 | Marketplace and demo | Aaditya | ✅ Ready to publish (needs the publisher's token) |

---

## Remaining manual steps (need a person, not code)

| Step | Who | How |
|---|---|---|
| Publish to the Marketplace | Aaditya | Make sure the publisher `Provenyx` exists, then `cd extension && npx vsce login Provenyx` (Personal Access Token, *Marketplace → Manage*) and `npx vsce publish`. Or upload the VSIX in the publisher portal. |
| Rehearse the demo and record a backup video | Aaditya + Omkar | Follow `docs/demo-script.md`; every step has been verified end to end. |
| Confirm the license | Aaditya + Omkar | MIT was applied as the default; change `LICENSE` files and `extension/package.json` if you prefer another. |

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

### 2026-10-12 — Merged `aaditya/phases-2-5-6-8` and `omkar/phase-4-7-implementation` into `main`

- Backend: Omkar's Phases 3–4 taken as-is (SQLite persistence, lockfile parser, NetworkX graph, npm registry client, detection rules, scan comparison, 34 new tests).
- Conflicts: 12 files (extension, dashboard, contract, roadmap). Resolved by keeping Aaditya's extension and dashboard and adapting them to the backend's real responses:
  - `GET /api/scans` and `/findings` return bare JSON arrays.
  - Findings carry `priority_score` (shown, and used to sort within a severity).
  - The project is not a graph node; paths start with `"root"`, so the UI draws a project node linked to the direct dependencies.
  - Scan and graph `warnings` are shown as "Analysis notes"; npm registry metadata (license, published date, deprecation, integrity) appears in the package drawer.
- `docs/api-contract.md` now documents the implemented shapes. `POST /api/releases/verify` remains the agreed Phase 6 shape.
- Roadmap statuses from both branches combined.
- Verified after the merge:
  - backend 40 tests pass
  - contracts 5 tests pass
  - extension smoke test runs a **real** scan to completion in VS Code
  - frontend build passes
  - 14/14 browser checks pass, including real findings, graph and registry data from the merged backend

### 2026-10-12 — Phases 6, 7 and 8 completed (branch `aaditya/complete-phases`)

**Phase 6 — release verification backend** (`backend/app/blockchain/`)
- Canonical manifest (schema 1): `{integrity: npm dist.integrity, name, schema_version, version}`, serialised as sorted-key compact UTF-8 JSON and hashed with keccak256. `pycryptodome` provides Keccak (Python's `sha3_256` uses different padding).
- Cross-language consistency: Python (`manifest.py`) and TypeScript (`contracts/scripts/manifest.ts`) are pinned to the same vectors (release id, manifest bytes, manifest hash, `recordOf` selector).
- `POST /api/releases/verify`:
  - validated input
  - reads `recordOf` over JSON-RPC, read-only with no keys
  - returns match, mismatch, no_record or unavailable, plus the anchor source, time and manifest
- CLI `python -m app.blockchain.manifest name@version` produces `anchors.json` entries from real npm metadata. `demo/anchors.demo.json` holds a real match and a deliberately altered mismatch.
- Verified with 8 new backend tests, and live on a Hardhat chain: approved → match, altered → mismatch, never anchored → no_record, chain stopped → unavailable. The dashboard showed a real match with the local-chain label.

**Phase 7 — remaining integration tests**
- The VS Code smoke test now also covers:
  - lockfile watcher: 3 rapid writes give 1 prompt; declining sends nothing; silent when off
  - an empty workspace: the "No package-lock.json found" warning appears, with no consent dialog
- Fixed test isolation: backend tests had written into the dev `provenyx.db` and triggered real npm calls. An autouse fixture now gives each test a temporary database and an offline registry.

**Phase 8 — Marketplace**
- Publisher `Provenyx`, MIT license (extension, repo root, Solidity SPDX).
- README screenshots in `docs/images/`, captured from real scans of the labelled demo fixtures and a live local chain.
- CHANGELOG, checklist and demo script updated, including the seeded demo data.

**Verification snapshot**

| Check | Result |
|---|---|
| Backend tests | ✅ 48 passed |
| Contract tests | ✅ 6 passing |
| VS Code smoke test (sample project + empty workspace, real backend) | ✅ |
| Frontend production build | ✅ |
| Browser checks (synthetic mock + real backend + live chain) | ✅ 15/15 |
| VSIX package + clean-profile install | ✅ |
