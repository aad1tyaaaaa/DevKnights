# Judge demo script (3–5 minutes)

Owner: Aaditya. Presenters alternate between Aaditya and Omkar.

## Before the demo (10 minutes, run once)

| # | Terminal | Command | Check |
|---|---|---|---|
| 1 | backend | `cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000` | `curl localhost:8000/health` returns `ok` |
| 2 | chain | `npm --prefix contracts run node` | stays running on :8545 |
| 3 | chain | `npm --prefix contracts run deploy:local`, then copy `demo/anchors.demo.json` to `contracts/anchors.json` and run `npm --prefix contracts run anchor:local` | Prints `anchor ms@2.1.3` and `anchor ms@2.1.2` |
| 4 | frontend | `npm run dev:frontend` | <http://localhost:3000/dashboard> shows **Backend connected** |
| 5 | VS Code | Install **Provenyx Security** (`OmkarPramodBandikatte.provenyx-security`) from the Marketplace (or press F5) and open a real npm project | Provenyx sidebar shows **Backend: Connected** |

`demo/anchors.demo.json` holds the real `ms@2.1.3` manifest hash (it matches) and a deliberately altered hash for `ms@2.1.2` (it mismatches). To anchor other releases, generate entries with `python -m app.blockchain.manifest name@version` in `backend/`.

Seed findings before the demo: scan `demo/fixtures/baseline-package-lock.json`, then `demo/fixtures/suspicious-update-package-lock.json` (upload both on `/scan/new`, in that order). Restarting the chain wipes the anchors; repeat step 3.

## Script

| Step | Presenter | Do | Say |
|---|---|---|---|
| 1 | Aaditya | Open a real npm project. Show the Provenyx sidebar. | "Provenyx lives in your editor. It reads the lockfile and never installs or runs packages." |
| 2 | Aaditya | Run **Provenyx: Scan Dependencies** and show the consent dialog. Confirm. | "Nothing leaves the machine until you say so, and only the lockfile is sent." |
| 3 | Omkar | Sidebar: scan completes. Show the package count. | "We parse lockfile v2/v3 and fetch public npm metadata, with timeouts and caching." |
| 4 | Omkar | Switch to the **clearly labelled synthetic** suspicious lockfile and scan again. Show the finding in the sidebar. | "This is a synthetic fixture, so the result is reproducible. Each finding shows its rule, evidence, and confidence." |
| 5 | Aaditya | Click the finding to open the dashboard. Show the drawer, the evidence, and the highlighted path in the graph. | "This is the blast radius: exactly how this package reaches your app." |
| 6 | Omkar | Open the sample project's scan, click `ms` in the graph, and click **Verify release** (match). Then show `ms@2.1.2` (mismatch) with `curl -X POST localhost:8000/api/releases/verify -H "Content-Type: application/json" -d '{"package":"ms","version":"2.1.2"}'`. | "A match means the metadata equals the approved record, not that the package is safe. A missing record is an evidence gap, not an accusation." |
| 7 | Aaditya | Show the Marketplace listing if it is live; otherwise show the VSIX and the submission status. | "Marketplace processing can lag, so the VSIX is our tested install path." |

## Fallbacks

- **Chain down:** verification shows *Verification unavailable*. That is the honest result; restart the node, redeploy, and re-anchor.
- **Backend down:** the sidebar shows *Unreachable* and the scan fails cleanly. This doubles as the "offline handling" story.
- **Marketplace install fails:** install a packaged `extension/provenyx-security-<version>.vsix`. Uninstall the obsolete `Provenyx.provenyx-security` first.
- **Live demo fails:** play the backup recording (record it after Phase 7).
