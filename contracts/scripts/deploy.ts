// Deploys ReleaseRegistry and writes deployments/<network>.json (address, chain id, ABI)
// for the backend to read.
//   Persistent local node:   npx hardhat node   then   npm run deploy:local
//   Ethereum Sepolia:         npm run deploy:sepolia
//   Throwaway in-process:    npm run deploy
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { network } from "hardhat";

const { viem, networkName } = await network.create();
const publicClient = await viem.getPublicClient();
const registry = await viem.deployContract("ReleaseRegistry");
const chainId = await publicClient.getChainId();

const deployment = {
  network: networkName,
  chainId,
  address: registry.address,
  owner: await registry.read.owner(),
  deployedAt: new Date().toISOString(),
  abi: registry.abi,
};

await mkdir(new URL("../deployments/", import.meta.url), { recursive: true });
const out = new URL(`../deployments/${networkName}.json`, import.meta.url);
await writeFile(out, JSON.stringify(deployment, null, 2) + "\n");

console.log(`ReleaseRegistry deployed to ${registry.address} (chain ${chainId}, network "${networkName}")`);
console.log(`Wrote ${fileURLToPath(out)}`);
