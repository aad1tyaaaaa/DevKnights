# Provenyx contracts

Hardhat 3 workspace for the Provenyx release registry. **Local development only.** No public network, wallet, paid RPC provider, or real cryptocurrency is required or configured.

## Commands

```bash
npm install
npm run compile          # compile Solidity
npm test                 # node:test + viem tests on the in-process Hardhat network
npm run node             # persistent local chain on http://127.0.0.1:8545 (chain id 31337) — keep running
npm run deploy:local     # deploy to that chain; writes deployments/localhost.json
npm run anchor:local     # anchor hashes listed in anchors.json (copy from anchors.example.json)
npm run deploy           # deploy to a throwaway in-process chain (smoke check only)
```

Restarting `npm run node` wipes the chain. Re-run `deploy:local` and `anchor:local` afterwards.

## Contract: `ReleaseRegistry.sol`

| Function | Who | Purpose |
|---|---|---|
| `anchor(bytes32 releaseId, bytes32 manifestHash)` | owner only | Write-once record; stores `block.timestamp` as `anchoredAt`. Emits `ReleaseAnchored`. |
| `recordOf(bytes32 releaseId) → (bytes32 manifestHash, uint64 anchoredAt)` | anyone | Zero hash and `0` mean *no record*. |
| `matches(bytes32 releaseId, bytes32 manifestHash) → bool` | anyone | `false` when there is no record or when it differs. |
| `owner()` | anyone | The account that anchors. |

**Release id:** `keccak256(utf8("<name>@<version>"))`, for example `keccak256("ms@2.1.3")`. Scoped names include the scope (`@scope/pkg@1.0.0`). The reference implementation is `scripts/releaseId.ts`; the backend must produce identical bytes.

## Handoff to the backend (Phase 6)

`npm run deploy:local` writes `deployments/localhost.json` (gitignored, per machine):

```json
{ "network": "localhost", "chainId": 31337, "address": "0x…", "owner": "0x…", "deployedAt": "…", "abi": [ … ] }
```

The backend's `POST /api/releases/verify` reads the address and ABI from this file, calls `recordOf(releaseId)`, and compares the result with its recomputed canonical manifest hash:

| On-chain result | API status |
|---|---|
| Stored hash equals the recomputed hash | `match` |
| Stored hash differs | `mismatch` |
| Zero hash | `no_record` |
| Chain unreachable or not deployed | `unavailable` |

## Anchoring approved manifests

`anchors.json` lists releases to anchor:

```json
[{ "package": "ms", "version": "2.1.3", "manifestHash": "0x<64 hex chars>" }]
```

`manifestHash` must come from the backend's canonical manifest serializer (owner: Omkar). The script does not compute hashes, and it refuses the all-zero placeholder. Releases that are already anchored are skipped.

## How results must be interpreted

- **Match:** the metadata equals what was approved and anchored. It does **not** prove the package is safe.
- **Mismatch:** the metadata differs from the approved record and deserves investigation.
- **No record:** an evidence gap, **not** an indication of maliciousness. Most packages will have no record.

Single owner and write-once records are deliberate MVP limits. Multi-signer approval and revocation are post-hackathon work.
