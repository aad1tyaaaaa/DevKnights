# Judge demo script (3–5 minutes)

Owner: Aaditya. Steps 3, 4, and 6 need Omkar's Phase 3, 4, and 6 endpoints. Until they are merged, use the fallback lines.

## Before the demo (10 minutes, run once)

| # | Terminal | Command | Check |
|---|---|---|---|
| 1 | backend | `cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000` | `curl localhost:8000/health` returns `ok` |
| 2 | chain | `npm --prefix contracts run node` | stays running on :8545 |
| 3 | chain | `npm --prefix contracts run deploy:local`, then `npm --prefix contracts run anchor:local` | `contracts/deployments/localhost.json` exists |
| 4 | frontend | `npm run dev:frontend` | <http://localhost:3000/dashboard> shows **Backend connected** |
| 5 | VS Code | Install `extension/provenyx-security-0.1.0.vsix` (or press F5) and open a real npm project | Provenyx sidebar shows **Backend: Connected** |

`anchors.json` must contain manifest hashes produced by the backend's canonical serializer: one release that matches and one deliberately altered release for the mismatch.

## Script

| Step | Presenter | Do | Say |
|---|---|---|---|
| 1 | Aaditya | Open a real npm project. Show the Provenyx sidebar. | "Provenyx lives in your editor. It reads the lockfile and never installs or runs packages." |
| 2 | Aaditya | Run **Provenyx: Scan Dependencies** and show the consent dialog. Confirm. | "Nothing leaves the machine until you say so, and only the lockfile is sent." |
| 3 | Omkar | Sidebar: scan completes. Show the package count. | "We parse lockfile v2/v3 and fetch public npm metadata, with timeouts and caching." |
| 4 | Omkar | Switch to the **clearly labelled synthetic** suspicious lockfile and scan again. Show the finding in the sidebar. | "This is a synthetic fixture, so the result is reproducible. Each finding shows its rule, evidence, and confidence." |
| 5 | Aaditya | Click the finding to open the dashboard. Show the drawer, the evidence, and the highlighted path in the graph. | "This is the blast radius: exactly how this package reaches your app." |
| 6 | Omkar | In the drawer, click **Verify release** for the matching release, then for the altered one. | "A match means the metadata equals the approved record, not that the package is safe. A missing record is an evidence gap, not an accusation." |
| 7 | Aaditya | Show the Marketplace listing if it is live; otherwise show the VSIX and the submission status. | "Marketplace processing can lag, so the VSIX is our tested install path." |

## Fallbacks

- **Endpoints not merged yet:** steps 3–6 show the honest "not available yet" states. Narrate the planned flow using `docs/api-contract.md`. Never show mock data as real results.
- **Backend down:** the sidebar shows *Unreachable* and the scan fails cleanly. This doubles as the "offline handling" story.
- **Marketplace pending:** install from `provenyx-security-0.1.0.vsix`.
- **Live demo fails:** play the backup recording (record it after Phase 7).
