# Development guide

## Prerequisites

| Tool | Version used to verify the project |
| --- | --- |
| Node.js | 24.18 (Hardhat 3 needs ≥ 22.10; extension/frontend need ≥ 20) |
| npm | 12.0 |
| Python | 3.13 (3.11+ supported) |
| VS Code | 1.141 (extension targets ≥ 1.90) |
| Git | any recent |

The first Hardhat compile downloads the solc 0.8.28 compiler; the first extension smoke test downloads a VS Code build. Both need internet access once.

> **npm 12 note:** npm 12 blocks dependency install scripts by default and prints `install-scripts … blocked` warnings for `esbuild` and `@vscode/vsce-sign`. Both still work for our use (esbuild ships its binary as a platform package). Do not blanket-approve install scripts.

## 1. Install dependencies

From the repository root:

```bash
npm run install:all          # extension, frontend, contracts
```

Backend (separate Python virtualenv):

```bash
cd backend
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# Windows (Git Bash):    source .venv/Scripts/activate
# macOS / Linux:         source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env         # optional; PowerShell: Copy-Item .env.example .env
```

## 2. Start the FastAPI backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Tests: `python -m pytest`

## 3. Start the Next.js frontend

```bash
npm run dev:frontend         # http://localhost:3000
```

Optional: `cp frontend/.env.example frontend/.env.local` to point at another API URL.

## 4. Launch the extension (Extension Development Host)

1. Open the **repository root** in VS Code.
2. Press **F5** (or Run and Debug → *Run Provenyx Extension*). This builds the extension and opens a new window on `demo/sample-project`.
3. In the new window: the shield icon in the Activity Bar opens the Provenyx sidebar; `Ctrl+Shift+P` → type “Provenyx”.

For rebuild-on-save run `npm --prefix extension run watch` and reload the host window (`Ctrl+R`).

Automated check (downloads and launches a real VS Code instance, then verifies activation, commands, and the view):

```bash
npm --prefix extension run test:smoke
# also run one real scan against a running backend:
PROVENYX_SMOKE_REAL_API=http://127.0.0.1:8000 npm --prefix extension run test:smoke
```

The smoke test confirms the consent dialog automatically and uses a throwaway in-test API (synthetic data) to check the scan → findings flow and the offline-backend case.

## 5. Check backend connectivity

```bash
curl http://localhost:8000/health
```

PowerShell: `Invoke-RestMethod http://localhost:8000/health`

In VS Code: **Provenyx: Check Backend Connection**, or look at *Backend* in the sidebar. On the dashboard, the status card shows the same.

## 6. Scan the sample lockfile

In the Extension Development Host (opened on `demo/sample-project`): **Provenyx: Scan Dependencies** → confirm **Send to Provenyx API**. Expect: “Lockfile received. Dependency analysis has started.” and *Last scan: Accepted* in the sidebar.

From the dashboard: open <http://localhost:3000/scan/new>, choose `demo/sample-project/package-lock.json`, tick the consent box, and click **Start scan**.

Without VS Code (Git Bash / macOS / Linux):

```bash
curl -X POST http://localhost:8000/api/scans -H "Content-Type: application/json" \
  -d "{\"lockfile\": $(cat demo/sample-project/package-lock.json)}"
```

Use the returned `scan_id` to inspect the completed snapshot and graph:

```bash
curl http://localhost:8000/api/scans/<scan_id>
curl http://localhost:8000/api/scans/<scan_id>/graph
```

PowerShell:

```powershell
$lock = Get-Content demo/sample-project/package-lock.json -Raw | ConvertFrom-Json
Invoke-RestMethod -Method Post http://localhost:8000/api/scans -ContentType application/json `
  -Body (@{ lockfile = $lock } | ConvertTo-Json -Depth 50)
```

## 7. Package the extension as a VSIX

```bash
npm run package:extension    # → extension/provenyx-security-0.1.0.vsix
code --install-extension extension/provenyx-security-0.1.0.vsix
```

## Contracts (local chain)

```bash
npm run compile:contracts
npm run test:contracts
npm --prefix contracts run node          # terminal 3: local chain on :8545 (keep running)
npm --prefix contracts run deploy:local  # writes contracts/deployments/localhost.json for the backend
npm --prefix contracts run anchor:local  # anchors hashes from contracts/anchors.json
```

See `contracts/README.md` for the release id format and how verification results map to API statuses.

## Ports

| Service | Port |
| --- | --- |
| FastAPI | 8000 |
| Next.js | 3000 |
| Hardhat node | 8545 |
