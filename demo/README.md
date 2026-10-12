# Demo

`sample-project/` is a minimal npm project whose `package-lock.json` (lockfileVersion 3) lists one real package, `ms@2.1.3`.

**Do not run `npm install` here.** Provenyx only reads the lockfile; nothing needs to be installed.

## Try it

1. Start the backend (`docs/development.md` §2).
2. Press F5 at the repository root — the Extension Development Host opens this folder.
3. Run **Provenyx: Scan Dependencies** and confirm.

Expected result in Phase 1: the API returns a `scan_id` with status `accepted` and the message *“Lockfile received. Dependency analysis is not implemented in Phase 1.”* No findings are produced — this is intentional; detection arrives in Phase 2.
