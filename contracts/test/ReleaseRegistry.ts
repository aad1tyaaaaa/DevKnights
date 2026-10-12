import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { network } from "hardhat";
import { keccak256, toFunctionSelector, toHex } from "viem";

import { canonicalManifestJson, manifestHash as canonicalManifestHash } from "../scripts/manifest.ts";
import { releaseId as releaseIdOf } from "../scripts/releaseId.ts";

const ZERO = `0x${"00".repeat(32)}` as const;

describe("ReleaseRegistry", async function () {
  const { viem } = await network.create();
  const publicClient = await viem.getPublicClient();
  const [, stranger] = await viem.getWalletClients();

  const releaseId = releaseIdOf("left-pad", "1.3.0");
  const manifestHash = keccak256(toHex('{"example":"manifest"}'));

  it("matches the backend's cross-language vectors (backend/tests/test_release_verification.py)", function () {
    const integrity = "sha512-6FlzubTLZG3J2a/NVCAleEhjzq5oxgHyaCU9yYXvcLsvoVaHJq/s5xXI6/XXP6tz7R9xAOtHnSO/tXtF3WRTlA==";
    assert.equal(releaseIdOf("ms", "2.1.3"), "0xa43c9c80df88be1fb6a327509e12f4e480ab9950e12150e7a357cd7f8df03228");
    assert.equal(
      canonicalManifestJson("ms", "2.1.3", integrity),
      `{"integrity":"${integrity}","name":"ms","schema_version":1,"version":"2.1.3"}`,
    );
    assert.equal(canonicalManifestHash("ms", "2.1.3", integrity), "0x7bcaaca2890ef8f5e14508703eb31a1dc5fff3e3e5c8e137c0184b179f550d4d");
    assert.equal(toFunctionSelector("recordOf(bytes32)"), "0xd1c60a3a");
  });

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
