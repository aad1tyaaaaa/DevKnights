import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { network } from "hardhat";
import { keccak256, toHex } from "viem";

describe("ReleaseRegistry", async function () {
  const { viem } = await network.create();
  const [, stranger] = await viem.getWalletClients();

  const releaseId = keccak256(toHex("left-pad@1.3.0"));
  const manifestHash = keccak256(toHex('{"example":"manifest"}'));

  it("anchors a manifest hash and reports matches", async function () {
    const registry = await viem.deployContract("ReleaseRegistry");
    await viem.assertions.emitWithArgs(registry.write.anchor([releaseId, manifestHash]), registry, "ReleaseAnchored", [
      releaseId,
      manifestHash,
    ]);
    assert.equal(await registry.read.manifestHashOf([releaseId]), manifestHash);
    assert.equal(await registry.read.matches([releaseId, manifestHash]), true);
    assert.equal(await registry.read.matches([releaseId, keccak256(toHex("other"))]), false);
  });

  it("returns false (not an error) for releases with no record", async function () {
    const registry = await viem.deployContract("ReleaseRegistry");
    assert.equal(await registry.read.matches([releaseId, manifestHash]), false);
  });

  it("rejects non-owners, empty hashes and overwrites", async function () {
    const registry = await viem.deployContract("ReleaseRegistry");
    await viem.assertions.revertWithCustomError(
      registry.write.anchor([releaseId, manifestHash], { account: stranger.account }),
      registry,
      "NotOwner",
    );
    await viem.assertions.revertWithCustomError(registry.write.anchor([releaseId, `0x${"00".repeat(32)}`]), registry, "EmptyHash");
    await registry.write.anchor([releaseId, manifestHash]);
    await viem.assertions.revertWithCustomError(registry.write.anchor([releaseId, manifestHash]), registry, "AlreadyAnchored");
  });
});
