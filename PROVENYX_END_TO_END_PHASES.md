# Provenyx Security — End-to-End Phase-Wise Roadmap

**Tagline:** Trust Every Dependency. Verify Every Release.  
**Goal:** Build an npm dependency intelligence VS Code extension, web dashboard, blockchain release verification, and publish to the VS Code Marketplace.  
**Hackathon:** 24 hours, 2 members — **Aaditya** and **Omkar**. **MVP:** npm `package-lock.json` v2/v3.  
**Cost:** Local development and Marketplace publication can be free. Cloud hosting and public-chain transactions may cost money.

## Guiding principles

- Never execute scanned npm packages or lifecycle scripts.
- Suspicious signals are not proof of compromise; matching anchored hashes are not proof of safety; missing records are not proof of maliciousness.
- Ask permission before uploading project lockfiles to remote services.
- Use real npm metadata; never invent vulnerabilities, release histories, or blockchain records.
- Keep a tested `.vsix` backup: Marketplace processing can be delayed.

## Timeline

| Phase | Focus | Budget | Owner | Support | Status | Deliverable |
|---|---|---:|---|---|---|---|
| 1 | Foundation | 2 h | Aaditya + Omkar | — | ✅ Done | Running project scaffolds and API contract |
| 2 | VS Code extension | 3 h | **Aaditya** | Omkar (API) | 🟡 Mostly done | Scan command, sidebar, API connection |
| 3 | Real npm scanner | 4 h | **Omkar** | — | ✅ Done | Lockfile parser, registry lookup, graph |
| 4 | Risk engine | 4 h | **Omkar** | Aaditya (fixtures review) | ✅ Done | Explainable findings and blast radius |
| 5 | Web dashboard | 3 h | **Aaditya** | — | 🟡 Investigation views working | Investigation UI with real data |
| 6 | Blockchain verification | 3 h | **Omkar** (manifest + backend) | **Aaditya** (contract + UI) | 🟡 Contract scaffolded | Anchored manifest verification |
| 7 | Integration and testing | 3 h | Aaditya + Omkar | — | 🟡 Mostly done | Core scan workflow tested; Phase 6 cases remain |
| 8 | Marketplace and demo | 2 h | **Aaditya** | Omkar (backend demo setup) | 🟡 VSIX packages | Tested VSIX and publication submission |

These are effort budgets. Run independent tasks in parallel. Publication processing is not included.

### Workload per person

| Developer | Owns | Est. remaining effort |
|---|---|---:|
| **Aaditya** | Extension (2), Dashboard (5), contract + verification UI (6, half), Marketplace + demo (8) | ~7.5 h |
| **Omkar** | Scanner (3), Risk engine (4), canonical manifest + backend verification (6, half) | ~9.5 h |

Phase 2 is mostly finished, so Aaditya also owns the Phase 6 contract and UI work to even out the load. Both developers share Phases 1 and 7.

### Working agreement

- **Contract first:** `docs/api-contract.md` is the source of truth. Omkar publishes response shapes (findings, graph, verification) before implementing them, so Aaditya can build the UI against them in parallel.
- **Handoffs:** Omkar → Aaditya: `GET /api/scans/{id}`, `/findings`, `/graph` (end of Phase 3/4), `POST /api/releases/verify` (Phase 6). Aaditya → Omkar: deployed local `ReleaseRegistry` address + ABI (Phase 6).
- **Fixtures:** Omkar owns `demo/` fixtures; Aaditya reviews that synthetic ones are clearly labeled.
- **Git:** one branch per task (`aaditya/<task>`, `omkar/<task>`), PR into `main`, reviewed by the other developer. Keep the extension types (`extension/src/types/index.ts`) and backend schemas (`backend/app/models/schemas.py`) in sync in the same PR.

---

## Phase 1 — Project foundation (2 hours)

**Owners:** Aaditya + Omkar · **Status:** ✅ Done (2026-10-12)

> Implemented without `yo code`: the extension was set up by hand with esbuild, giving the same result with fewer generated files. Details: `docs/development.md`. Planned endpoints and draft finding/graph/verification schemas are in `docs/api-contract.md`.

### Objective
Create a clean monorepo, configure development tools, and agree on the API contract.

### Structure
```text
provenyx/
├── extension/      # TypeScript, VS Code API, esbuild
├── backend/        # Python 3.11+, FastAPI, Pydantic, pytest
├── frontend/       # Next.js App Router, Tailwind, shadcn/ui
├── contracts/      # Solidity, Hardhat local chain
├── demo/           # Benign and synthetic suspicious fixtures
├── docs/           # API contract, security model, development guide
├── .gitignore
└── README.md
```

### Tasks
1. Initialize Git and project folders.
2. Scaffold extension with `npm install -g yo generator-code` and `yo code`; test F5 Extension Development Host.
3. Start FastAPI with `GET /health`.
4. Scaffold Next.js frontend and Hardhat contract workspace.
5. Add `.env.example`, scripts, tests, and README.
6. Agree on scan IDs, finding schema, graph schema, and error responses.
7. Create Marketplace publisher account early; record the exact unique publisher ID. — **Aaditya, still open** (`extension/package.json` has the placeholder `your-publisher-id`).

### Initial API contract
| Endpoint | Purpose |
|---|---|
| Endpoint | Purpose | Status | Owner |
|---|---|---|---|
| `GET /health` | Connectivity | ✅ Implemented | — |
| `POST /api/scans` | Accept validated lockfile, return scan ID | ✅ Implemented with background analysis | — |
| `GET /api/scans/{id}` | Status and summary | ✅ Implemented | Omkar (Phase 3) |
| `GET /api/scans/{id}/findings` | Evidence-backed findings | ✅ Implemented | Omkar (Phase 4) |
| `GET /api/scans/{id}/graph` | Nodes and edges | ✅ Implemented | Omkar (Phase 3) |
| `POST /api/releases/verify` | Trusted manifest verification | ⬜ Draft schema | Omkar (Phase 6) |

### Done when
- [x] Extension activates in development host (automated smoke test: `npm --prefix extension run test:smoke`).
- [x] FastAPI health endpoint responds (6 backend tests pass).
- [x] Next.js starts (production build passes type-checking).
- [x] Hardhat compiles (3 contract tests pass).
- [x] API schema documented (`docs/api-contract.md`).

---

## Phase 2 — VS Code extension (3 hours)

**Owner:** Aaditya · **Support:** Omkar (API) · **Status:** 🟡 Mostly done — all features below were built during Phase 1.

### Objective
Let developers scan dependencies without leaving VS Code.

### Remaining work (Aaditya)
- [ ] Manual F5 test: click **Send to Provenyx API** in the consent dialog and confirm *Last scan: Accepted* in the sidebar.
- [ ] Manual test with the backend stopped: sidebar shows *Unreachable*, no crash.
- [x] List real Phase 4 findings in the sidebar after analysis completes.
- [x] Open the dashboard on the matching scan (`/scans/{id}`) after a scan.

### Features
- Provenyx Activity Bar icon and TreeView sidebar.
- Commands: **Scan Dependencies**, **Show Findings**, **Open Dashboard**.
- Find and safely read `package-lock.json` using `vscode.workspace.fs`.
- Validate JSON; show clear errors for missing or invalid files.
- Connect to configurable FastAPI URL with timeouts and error handling.
- Request consent before transmitting lockfiles to a remote API.
- Settings: `provenyx.apiBaseUrl`, `provenyx.dashboardUrl`, `provenyx.autoScanEnabled` (default false).
- Optional debounced file watcher on `**/package-lock.json`, avoiding duplicate scans.
- Show real scan status and findings, never fabricated risk counts.

### Done when
- [x] F5 starts extension and commands appear.
- [x] Scan reads a real npm project lockfile.
- [ ] Backend receives request and returns scan ID — verified via `curl`; in-editor click still to test manually.
- [ ] Sidebar shows scan result or meaningful error — implemented; still to test manually.
- [ ] Offline backend does not crash extension — implemented; still to test manually.

---

## Phase 3 — Real npm dependency scanner (4 hours)

**Owner:** Omkar · **Status:** ✅ Done (2026-10-12) · **Where:** `backend/app/parsers/`, `backend/app/graph/`

**Hands off to Aaditya:** `GET /api/scans/{id}` and `GET /api/scans/{id}/graph`, matching the draft schemas in `docs/api-contract.md`.

### Objective
Parse installed dependencies and retrieve public npm metadata without installing or executing packages.

### Features
1. [x] Support npm `package-lock.json` versions 2 and 3, including scoped names and nested install paths (v1 remains supported too).
2. [x] Extract package identity, exact version, dependency declarations, resolved URL, and integrity when present.
3. [x] Preserve multiple installed versions of the same package.
4. [x] Construct direct/transitive dependency graph with NetworkX.
5. [x] Query npm registry metadata using bounded concurrency, caching, timeouts, and retry limits.
6. [x] Save scan snapshots with SQLite and SQLAlchemy.
7. [x] Compare persisted scans for additions, removals, upgrades, and new transitive edges.
8. [x] Mark unavailable metadata as unknown; never guess.

### Done when
- [x] Four real repository lockfiles produce correct, distinct graphs.
- [x] Multiple versions of a package remain distinct.
- [x] Network failure is handled as unavailable metadata.
- [x] No scanned package code is executed.

---

## Phase 4 — Explainable risk detection (4 hours)

**Owner:** Omkar · **Support:** Aaditya (reviews synthetic fixture labeling) · **Status:** ✅ Done (2026-10-12) · **Where:** `backend/app/detection/`, `demo/`

**Hands off to Aaditya:** `GET /api/scans/{id}/findings`.

### Objective
Flag suspicious release changes with traceable evidence and confidence limits.

### MVP rules
| Signal | Evidence | Caveat |
|---|---|---|
| New dependency | Baseline/current lockfile diff | Not inherently malicious |
| Unexpected dependency expansion | New graph edges after update | Requires version comparison |
| Unusual release timing | npm release timestamps | Requires sufficient history |
| Trusted manifest mismatch | Approved hash vs current canonical manifest | Deferred to Phase 6 verification |
| Maintainer/publisher change (optional) | Reliable historical snapshots | Do not infer from current metadata alone |
| Known vulnerability (optional) | OSV advisory | Separate from anomaly detection |

### Tasks
- Create deterministic, documented scoring for investigation priority.
- Show every signal contributing to a finding, evidence sources, and unknowns.
- Compute dependency paths from direct dependencies to flagged packages (blast-radius context).
- Add curated **synthetic** suspicious fixtures, clearly labeled as such.
- Keep confidence and severity distinct.

### Done when
- [x] Normal upgrade is not automatically high risk.
- [x] Synthetic suspicious fixture triggers expected findings.
- [x] Every finding has supporting evidence, confidence, severity, and deterministic priority.
- [x] Dependency paths are correct.

---

## Phase 5 — Premium web dashboard (3 hours)

**Owner:** Aaditya · **Status:** 🟡 Scaffolded — `/`, `/dashboard`, `/scans`, `/settings`, sidebar, backend status card and empty states exist with the target design · **Where:** `frontend/`

Start against the draft schemas in `docs/api-contract.md` while Omkar builds Phases 3–4. Use real responses only, never mock data shown as real.

### Objective
Build the investigation experience with Next.js and optionally v0.app for UI scaffolding.

### Design
White/off-white cards, deep forest-green sidebar, mint accents, subtle borders, readable tables, restrained animation, responsive layouts.

### Pages
- `/` — Landing.
- `/dashboard` — Recent scans and real metrics.
- `/scan/new` — Lockfile upload or labeled demo.
- `/scans/[id]` — Overview, dependency graph, findings, release verification.
- `/reports` — JSON/HTML exports if time permits.

### Components
`AppSidebar`, `AppHeader`, `ScanDropzone`, `ScanProgress`, `MetricCard`, `FindingsTable`, `DependencyGraph` (Cytoscape.js), `PackageDetailDrawer`, `VerificationStatus`, `EmptyState`, `ErrorState`.

### Done when
- [ ] Dashboard consumes real backend results.
- [ ] Graph supports zoom, pan, node selection, and highlighted paths.
- [ ] VS Code opens the correct scan.
- [ ] Loading/error/empty states are clear.
- [ ] No fabricated production metrics.

---

## Phase 6 — Blockchain verification (3 hours)

### Objective
Verify that current release evidence matches a previously approved anchored manifest.

**Owners:** Omkar (manifest + backend) · Aaditya (contract + UI) · **Status:** 🟡 Contract scaffolded · **Where:** `contracts/`, `backend/app/blockchain/`, `frontend/`

### Tasks
| # | Task | Owner | Status |
|---|---|---|---|
| 1 | Define canonical manifest fields: package, version, selected trusted metadata, schema version. | Omkar | ⬜ |
| 2 | Serialize deterministically and hash; test cross-language consistency. | Omkar | ⬜ |
| 3 | Create `ReleaseRegistry.sol` with authorized anchoring and public lookup. | Aaditya | ✅ Scaffolded (`anchor`, `matches`, write-once, owner-only; 3 tests) |
| 4 | Deploy to local Hardhat chain only; share address + ABI with Omkar. | Aaditya | 🟡 `scripts/deploy.ts` works |
| 5 | Implement backend verification and return `match`, `mismatch`, `no_record`, or `unavailable`. | Omkar | ⬜ |
| 6 | Show the source of the anchor, manifest details, and local-demo-chain labeling. | Aaditya | ⬜ |

### Done when
- [ ] Approved manifest matches.
- [ ] Altered manifest mismatches.
- [ ] Unknown manifest returns no record.
- [ ] Offline chain returns unavailable.
- [ ] UI does not claim hash match proves safety.

---

## Phase 7 — Integration, security, testing (3 hours)

**Owners:** Aaditya + Omkar (each tests the other's side) · **Status:** 🟡 Mostly done — blockchain verification waits on Phase 6; manual clean-profile packaging remains

### End-to-end test cases
| | Test | Owner |
|---|---|---|
| 🟡 | VS Code → FastAPI → npm analysis → findings → dashboard (implemented; extension smoke + live API/dashboard validated, consent click remains manual). | Aaditya + Omkar |
| ✅ | Valid lockfile scans correctly. | Omkar |
| ✅ | Malformed or oversized lockfile is rejected safely (backend tests). | Omkar |
| ⬜ | No lockfile is handled (implemented; to test manually). | Aaditya |
| ✅ | Backend offline and npm registry timeout are handled. | Aaditya (offline) · Omkar (registry) |
| ✅ | Benign update does not trigger unjustified high risk. | Omkar |
| ✅ | Labeled synthetic suspicious fixture triggers expected rule. | Omkar |
| ⬜ | Missing blockchain record is not treated as mismatch. | Omkar |
| ⬜ | Watcher is debounced and respects user consent (implemented; to test manually). | Aaditya |
| ✅ | No dependency scripts execute. | Omkar |
| ⬜ | VSIX installs in a clean VS Code profile. | Aaditya |

### Deliverables
Passing tests, fixed blockers, tagged commit, tested VSIX, backup demo recording.

---

## Phase 8 — Marketplace publishing and demo (2 hours of team effort)

**Owner:** Aaditya · **Support:** Omkar (backend + local chain running for the demo) · **Status:** 🟡 VSIX packages (`npm run package:extension`); see `docs/marketplace-checklist.md` for open listing items.

### Publisher account
1. Visit [Marketplace publisher management](https://marketplace.visualstudio.com/manage/publishers/).
2. Create publisher **Name** and unique **ID** (e.g. `Provenyx` / `provenyx` only if available).
3. Domain verification is optional.
4. Prefer an account the team can retain long term.

### Listing readiness
- [ ] Exact publisher ID in extension `package.json`.
- [ ] Display name, description, version, VS Code engine compatibility.
- [ ] Genuine icon (128×128 PNG), screenshots, README.
- [ ] Repository, license, support details, privacy disclosure.
- [ ] Backend availability documented: Marketplace does **not** host FastAPI.
- [ ] `.vscodeignore` excludes secrets, large dev files, and fixtures not required at runtime.

### Package and publish
```bash
cd extension
npm install
npm run vsix          # builds and packages; vsce is already a dev dependency
```

Install the generated `.vsix` and test in a clean VS Code profile. Configure supported publishing credentials according to the [official publishing guide](https://code.visualstudio.com/api/working-with-extensions/publishing-extension), then:

```bash
npx vsce login <publisher-id>
npx vsce publish
```

You can also upload a packaged VSIX through the publisher portal. Never commit credentials. Processing may delay public availability.

### Judge demo (3–5 minutes)
| Step | Presenter |
|---|---|
| 1. Open an actual npm project in VS Code. | Aaditya |
| 2. Run Provenyx Scan Dependencies. | Aaditya |
| 3. Show real lockfile parsing and npm metadata retrieval. | Omkar |
| 4. Load a **clearly labeled synthetic suspicious update** to demonstrate a reproducible finding. | Omkar |
| 5. Open the dashboard; inspect evidence and blast-radius paths. | Aaditya |
| 6. Show blockchain match and mismatch using approved release manifests. | Omkar |
| 7. Show Marketplace listing if live; otherwise show the working VSIX and accurate submission status. | Aaditya |

### Done when
- [ ] VSIX works independently of Marketplace approval.
- [ ] Marketplace submission succeeds or blocker is documented.
- [ ] Demo works with a backup plan.

---

## Team split

| Developer | Area | Phases | Main directories |
|---|---|---|---|
| **Aaditya** | Extension + Dashboard + Contract/UI + Marketplace | 2, 5, 6 (contract + UI), 8 | `extension/`, `frontend/`, `contracts/` |
| **Omkar** | Backend + Detection + Verification logic | 3, 4, 6 (manifest + backend) | `backend/`, `demo/` |

Both collaborate on Phase 1 (done) and Phase 7. Agree on the API contract and fixtures first.

**Suggested order**
1. **Omkar:** Phase 3 → Phase 4 → Phase 6 backend. Publish response shapes early.
2. **Aaditya:** finish Phase 2 manual checks and the publisher account → Phase 5 against the draft schemas → Phase 6 contract deploy and UI → Phase 8.
3. **Both:** Phase 7 once Phases 3–5 have merged, then rehearse the demo.

## Scope cuts if behind schedule

**Keep:** Real npm lockfile parsing, two explainable risk rules, VS Code scan command, real findings, tested VSIX.  
**Simplify:** SQLite instead of PostgreSQL; selected-package graph instead of huge graph; JSON report instead of PDF.  
**Defer:** AI anomaly models, multi-ecosystem support, GitHub App, production authentication, public blockchain deployment, automatic PR comments.  
**Never cut:** Security claims accuracy, upload consent, input validation, and a reliable demo.

## Final definition of done

A developer can install Provenyx in VS Code, scan a real npm project without executing packages, inspect evidence-backed dependency findings and graph paths, open the matching web dashboard, and verify an approved manifest against a local blockchain record.

**Marketplace submission** is separate from **Marketplace public availability**.

## Official references

- [Your First VS Code Extension](https://code.visualstudio.com/api/get-started/your-first-extension)
- [VS Code Extension API](https://code.visualstudio.com/api)
- [Publishing VS Code Extensions](https://code.visualstudio.com/api/working-with-extensions/publishing-extension)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Hardhat](https://hardhat.org/)
