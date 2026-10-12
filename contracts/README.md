# Provenyx contracts

Hardhat 3 workspace for the Provenyx release registry. Local development uses an in-process chain; production verification can use a registry deployed to Ethereum Sepolia.

## Commands

```bash
npm install
npm run compile          # compile Solidity
npm test                 # node:test + viem tests on the in-process Hardhat network
npm run node             # persistent local chain on http://127.0.0.1:8545 (chain id 31337) — keep running
npm run deploy:local     # deploy to that chain; writes deployments/localhost.json
npm run anchor:local     # anchor hashes listed in anchors.json (copy from anchors.example.json)
npm run deploy:sepolia   # deploy to Sepolia; writes deployments/sepolia.json
npm run anchor:sepolia   # anchor hashes listed in anchors.json on Sepolia
npm run deploy           # deploy to a throwaway in-process chain (smoke check only)
```

Restarting `npm run node` wipes the chain. Re-run `deploy:local` and `anchor:local` afterwards.

## Deploying to Sepolia

Fund a dedicated deployment wallet with Sepolia ETH, then store the Sepolia RPC URL and wallet private key in Hardhat's encrypted keystore:

```bash
npx hardhat keystore set SEPOLIA_RPC_URL
npx hardhat keystore set SEPOLIA_PRIVATE_KEY
```

Enter the values when prompted. The private key must include its `0x` prefix. Never commit it or add it to Render or Vercel.

Deploy the registry:

```bash
npm run deploy:sepolia
```

The command prints the contract address and writes it to `deployments/sepolia.json`. Configure the deployed backend with read-only credentials:

```env
PROVENYX_REGISTRY_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/<ALCHEMY_KEY>
PROVENYX_REGISTRY_ADDRESS=0x<DEPLOYED_CONTRACT_ADDRESS>
PROVENYX_REGISTRY_TIMEOUT_SECONDS=5
```

The deployment wallet remains the registry owner. To add approved releases, generate `anchors.json` as described below and run `npm run anchor:sepolia` from the same machine and Hardhat keystore.

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

The backend's `POST /api/releases/verify` (implemented in `backend/app/blockchain/`) reads the address from this file (or `PROVENYX_REGISTRY_ADDRESS`), calls `recordOf(releaseId)` read-only over JSON-RPC (`PROVENYX_REGISTRY_RPC_URL`, default `http://127.0.0.1:8545`), and compares the result with its recomputed canonical manifest hash:

| On-chain result | API status |
|---|---|
| Stored hash equals the recomputed hash | `match` |
| Stored hash differs | `mismatch` |
| Zero hash | `no_record` |
| Chain unreachable, not deployed, or current npm metadata unreadable | `unavailable` |

## Anchoring approved manifests

`anchors.json` lists releases to anchor:

```json
[{ "package": "ms", "version": "2.1.3", "manifestHash": "0x<64 hex chars>" }]
```

Generate entries from public npm metadata with the backend's canonical serializer (it refuses releases whose metadata is unavailable):

```bash
cd backend && .venv/Scripts/python -m app.blockchain.manifest ms@2.1.3 left-pad@1.3.0 > ../contracts/anchors.json
```

The anchor script itself never computes or guesses hashes, refuses the all-zero placeholder, and skips releases that are already anchored. `scripts/manifest.ts` is the TypeScript reference of the same canonical format; the tests pin both implementations to the same vectors.

For the demo, `demo/anchors.demo.json` contains the real `ms@2.1.3` hash and a **deliberately altered** hash for `ms@2.1.2` (to show a mismatch).

## How results must be interpreted

- **Match:** the metadata equals what was approved and anchored. It does **not** prove the package is safe.
- **Mismatch:** the metadata differs from the approved record and deserves investigation.
- **No record:** an evidence gap, **not** an indication of maliciousness. Most packages will have no record.

Single owner and write-once records are deliberate MVP limits. Multi-signer approval and revocation are post-hackathon work.
