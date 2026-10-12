# Provenyx contracts

Hardhat 3 workspace for the Provenyx release registry. **Local development only** — no public network, wallet, paid RPC provider, or real cryptocurrency is required or configured.

## Commands

```bash
npm install
npm run compile                    # compile Solidity
npm test                           # run node:test + viem tests on the in-process Hardhat network
npm run deploy                     # deploy to a throwaway in-process chain
npx hardhat node                   # start a persistent local chain on http://127.0.0.1:8545
npm run deploy -- --network localhost
```

## How the future release registry will work

1. A trusted party (initially the Provenyx operator) builds a **release manifest** for an npm package version: canonical JSON of publish metadata such as name, version, tarball integrity (`dist.integrity`), and publisher.
2. Only the **hash** of that manifest is anchored on-chain via `anchor(releaseId, manifestHash)`, where `releaseId = keccak256("name@version")`. Dependency graphs and package source code are never stored on-chain.
3. During a scan, the backend recomputes the manifest hash from registry metadata and calls `matches(releaseId, hash)`.

How results must be interpreted:

- **Match** — the metadata equals what was approved and anchored. It does **not** prove the package is safe.
- **Mismatch** — the metadata differs from the approved record and deserves investigation.
- **No record** — an evidence gap. It is **not** an indication of maliciousness; most packages will have no record.

`ReleaseRegistry.sol` is a Phase 1 scaffold: single owner, write-once records. Multi-signer approval, revocation, and the manifest canonicalisation spec are later-phase work.
