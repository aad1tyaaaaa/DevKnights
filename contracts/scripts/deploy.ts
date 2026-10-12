// Deploys ReleaseRegistry to a local chain.
//   In-process (throwaway):  npx hardhat run scripts/deploy.ts
//   Persistent local node:   npx hardhat node   then   npx hardhat run scripts/deploy.ts --network localhost
import { network } from "hardhat";

const { viem, networkName } = await network.create();
const registry = await viem.deployContract("ReleaseRegistry");
console.log(`ReleaseRegistry deployed to ${registry.address} on network "${networkName}"`);
