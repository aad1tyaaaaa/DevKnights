# Demo

`sample-project/` is a minimal npm project whose `package-lock.json` (lockfileVersion 3) lists one real package, `ms@2.1.3`.

**Do not run `npm install` here.** Provenyx only reads the lockfile; nothing needs to be installed.

## Try it

1. Start the backend (`docs/development.md` §2).
2. Press F5 at the repository root — the Extension Development Host opens this folder.
3. Run **Provenyx: Scan Dependencies** and confirm.

Expected result: the scan completes with one package, `ms@2.1.3`, plus its npm registry metadata. The first scan has no change findings, but exact-version OSV advisory checks still run.

## Other demo files

- `fixtures/`: **synthetic** baseline and suspicious-update lockfiles. Scan the baseline first, then the update, to produce reproducible findings (see `fixtures/README.md`).
- `anchors.demo.json`: release-registry entries for the demo. `ms@2.1.3` has its real canonical manifest hash and verifies as **match**. `ms@2.1.2` has a **deliberately altered** hash (built from the fake integrity `sha512-ALTERED-for-demo`) and verifies as **mismatch**. Copy it to `contracts/anchors.json` and run `npm --prefix contracts run anchor:local`.
