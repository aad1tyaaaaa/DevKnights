# Architecture

```text
 VS Code                                   Browser
┌──────────────────────────┐             ┌──────────────────────────┐
│ Provenyx extension (TS)  │             │ Next.js dashboard :3000  │
│  • find package-lock.json│             │  • /dashboard /scans     │
│  • validate JSON locally │             │  • /settings             │
│  • ask consent ──────────┼──POST───┐   │  • health status         │
│  • sidebar TreeView      │         │   └────────────┬─────────────┘
└──────────┬───────────────┘         │                │ GET /health (CORS)
           │ GET /health             ▼                ▼
           │                ┌─────────────────────────────────┐
           └───────────────►│ FastAPI backend :8000           │
                            │  api/      HTTP routes          │
                            │  models/   Pydantic contract    │
                            │  parsers/  lockfile → model  (P2)│
                            │  graph/    dependency graph  (P2)│
                            │  detection/ explainable rules(P2+)
                            │  blockchain/ hash verification   │
                            └───────────────┬─────────────────┘
                                            │ (later phase, read-only)
                                            ▼
                            ┌─────────────────────────────────┐
                            │ ReleaseRegistry.sol (Hardhat)   │
                            │ releaseId → manifest hash       │
                            └─────────────────────────────────┘
```

## Components

| Path | Stack | Role |
| --- | --- | --- |
| `extension/` | TypeScript, VS Code API, esbuild | Primary product. Finds and validates lockfiles, obtains consent, submits to the API, shows state in a TreeView. |
| `backend/` | Python 3.11+, FastAPI, Pydantic | Validates submissions; future home of parsing, graph building, detection, and verification. |
| `frontend/` | Next.js App Router, Tailwind v4, shadcn/ui conventions, Lucide | Web dashboard for deeper investigation. |
| `contracts/` | Solidity, Hardhat 3, viem | Registry of approved release-manifest hashes. Local network only. |
| `demo/` | — | Sample project with a tiny lockfile for end-to-end checks. |

The monorepo does **not** use npm workspaces: each JS package has its own `node_modules` and lockfile, which keeps vsce packaging, Next.js, and Hardhat 3 (ESM) independent. The root `package.json` only holds convenience scripts. Python dependencies live in `backend/requirements.txt`.

## Trust boundaries and safety rules

- The extension reads `package-lock.json` with `vscode.workspace.fs` and never runs `npm`, package code, or lifecycle scripts.
- Nothing leaves the machine without a modal confirmation for each scan, naming the destination URL. Only the lockfile is sent.
- The backend treats lockfile content as untrusted data: size-capped body (checked while streaming), strict schema, no echo of input in errors.
- Error messages shown to users never include lockfile contents.
- No external network calls are made in Phase 1. `httpx` is installed for the Phase 2 npm registry client.
- Blockchain results are evidence, not verdicts: a match is not proof of safety; no record is not proof of compromise.

## Persistence (planned)

Phase 1 stores nothing. Phase 2 introduces SQLite through SQLAlchemy with a `DATABASE_URL` setting (`sqlite:///./provenyx.db`), so moving to PostgreSQL is a connection-string change plus migrations (Alembic).
