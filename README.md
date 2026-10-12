# Provenyx Security

**Trust Every Dependency. Verify Every Release.**

Software supply-chain security for JavaScript and TypeScript projects using npm. Provenyx analyzes `package-lock.json` files from inside VS Code — without installing or executing packages — and links to a web dashboard for deeper investigation, including blockchain-anchored release verification.

> **Status: Phase 1 (foundation).** The extension, API, dashboard, and contract workspace are wired together and tested. Dependency analysis and detection are **not implemented yet**; no findings are produced.

## Repository layout

| Path | What |
| --- | --- |
| `extension/` | VS Code extension (TypeScript, esbuild) |
| `backend/` | FastAPI service (Python 3.11+) |
| `frontend/` | Next.js dashboard (App Router, Tailwind, shadcn/ui) |
| `contracts/` | Hardhat 3 release-registry contract (local network only) |
| `demo/` | Sample project for end-to-end checks |
| `docs/` | Architecture, API contract, development guide, Marketplace checklist |

## Quick start

```bash
npm run install:all
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000                      # terminal 1
npm run dev:frontend                                                                    # terminal 2 (repo root)
```

Then open the repo in VS Code and press **F5**. Full instructions: [docs/development.md](docs/development.md).

## Safety principles

- Never executes untrusted packages, `npm install`, or lifecycle scripts in scanned projects.
- Never uploads anything without explicit, per-scan consent.
- Never presents fabricated findings.
- A missing blockchain record is not evidence of maliciousness; a matching hash is not proof of safety.

## Docs

- [Architecture](docs/architecture.md)
- [API contract](docs/api-contract.md)
- [Development](docs/development.md)
- [Marketplace checklist](docs/marketplace-checklist.md)
