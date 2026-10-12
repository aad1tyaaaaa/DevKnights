import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { network } from "hardhat";
import { keccak256, toHex } from "viem";

import { releaseId as releaseIdOf } from "../scripts/releaseId.ts";

const ZERO = `0x${"00".repeat(32)}` as const;

describe("ReleaseRegistry", async function () {
  const { viem } = await network.create();
  const publicClient = await viem.getPublicClient();
  const [, stranger] = await viem.getWalletClients();

  const releaseId = releaseIdOf("left-pad", "1.3.0");
  const manifestHash = keccak256(toHex('{"example":"manifest"}'));

  it("derives release ids as keccak256(utf8(name@version))", function () {
    assert.equal(releaseId, keccak256(toHex("left-pad@1.3.0")));
    assert.notEqual(releaseIdOf("@scope/pkg", "1.0.0"), releaseIdOf("@scope/pkg", "1.0.1"));
  });

  it("anchors a manifest hash with a timestamp and reports matches", async function () {
    const registry = await viem.deployContract("ReleaseRegistry");
    const hash = await registry.write.anchor([releaseId, manifestHash]);
    const receipt = await publicClient.waitForTransactionReceipt({ hash });
    const block = await publicClient.getBlock({ blockNumber: receipt.blockNumber });

    const [stored, anchoredAt] = await registry.read.recordOf([releaseId]);
    assert.equal(stored, manifestHash);
    assert.equal(anchoredAt, block.timestamp);
    assert.equal(await registry.read.matches([releaseId, manifestHash]), true);
    assert.equal(await registry.read.matches([releaseId, keccak256(toHex("other"))]), false);
  });

  it("emits ReleaseAnchored", async function () {
    const registry = await viem.deployContract("ReleaseRegistry");
    await viem.assertions.emit(registry.write.anchor([releaseId, manifestHash]), registry, "ReleaseAnchored");
  });

  it("returns an empty record and false (not an error) for releases with no record", async function () {
    const registry = await viem.deployContract("ReleaseRegistry");
    const [stored, anchoredAt] = await registry.read.recordOf([releaseId]);
    assert.equal(stored, ZERO);
    assert.equal(anchoredAt, 0n);
    assert.equal(await registry.read.matches([releaseId, manifestHash]), false);
  });

  it("rejects non-owners, empty hashes and overwrites", async function () {
    const registry = await viem.deployContract("ReleaseRegistry");
    await viem.assertions.revertWithCustomError(
      registry.write.anchor([releaseId, manifestHash], { account: stranger.account }),
      registry,
      "NotOwner",
    );
    await viem.assertions.revertWithCustomError(registry.write.anchor([releaseId, ZERO]), registry, "EmptyHash");
    await registry.write.anchor([releaseId, manifestHash]);
    await viem.assertions.revertWithCustomError(registry.write.anchor([releaseId, manifestHash]), registry, "AlreadyAnchored");
  });
});
