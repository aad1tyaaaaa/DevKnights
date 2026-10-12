// Anchors approved release-manifest hashes listed in anchors.json into the deployed ReleaseRegistry.
//   1. npm run deploy:local          (writes deployments/localhost.json)
//   2. cp anchors.example.json anchors.json and fill in real manifest hashes
//   3. npm run anchor:local
// The manifest hash must come from the backend's canonical manifest serializer (Phase 6, Omkar);
// this script does not compute or guess hashes.
import { readFile } from "node:fs/promises";
import { network } from "hardhat";
import { isHex } from "viem";

import { releaseId } from "./releaseId.ts";

type Anchor = { package: string; version: string; manifestHash: string };

const { viem, networkName } = await network.create();
const deployment = JSON.parse(await readFile(new URL(`../deployments/${networkName}.json`, import.meta.url), "utf8"));
const anchors: Anchor[] = JSON.parse(await readFile(new URL("../anchors.json", import.meta.url), "utf8"));

const registry = await viem.getContractAt("ReleaseRegistry", deployment.address);
const publicClient = await viem.getPublicClient();

for (const a of anchors) {
  if (!isHex(a.manifestHash) || a.manifestHash.length !== 66) {
    throw new Error(`${a.package}@${a.version}: manifestHash must be a 32-byte 0x-prefixed hex string`);
  }
  if (BigInt(a.manifestHash) === 0n) {
    throw new Error(`${a.package}@${a.version}: manifestHash is the all-zero placeholder; use a real canonical manifest hash`);
  }
  const id = releaseId(a.package, a.version);
  const [existing] = await registry.read.recordOf([id]);
  if (BigInt(existing) !== 0n) {
    console.log(`skip   ${a.package}@${a.version} (already anchored: ${existing})`);
    continue;
  }
  const hash = await registry.write.anchor([id, a.manifestHash as `0x${string}`]);
  await publicClient.waitForTransactionReceipt({ hash });
  console.log(`anchor ${a.package}@${a.version} → ${a.manifestHash}`);
}
