# Demo

`sample-project/` is a minimal npm project whose `package-lock.json` (lockfileVersion 3) lists one real package, `ms@2.1.3`.

**Do not run `npm install` here.** Provenyx only reads the lockfile; nothing needs to be installed.

## Try it

1. Start the backend (`docs/development.md` §2).
2. Press F5 at the repository root — the Extension Development Host opens this folder.
3. Run **Provenyx: Scan Dependencies** and confirm.

Expected result: the API returns a `scan_id` with status `accepted` while Phase 3 analysis runs. `GET /api/scans/{scan_id}` returns the persisted summary, and `/graph` returns the real `ms@2.1.3` node with npm registry metadata. No findings are produced yet; detection arrives in Phase 4.
