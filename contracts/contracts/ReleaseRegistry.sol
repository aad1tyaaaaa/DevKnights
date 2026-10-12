// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.28;

/// @title Provenyx release registry (Phase 1 scaffold)
/// @notice Stores hashes of approved release manifests. It never stores dependency graphs or package source.
/// A recorded hash proves only that this exact manifest was anchored by the registry owner;
/// it is not a statement that the package is safe. A missing record is not evidence of maliciousness.
contract ReleaseRegistry {
    address public immutable owner;

    // releaseId => manifest hash. releaseId is keccak256 of a canonical "name@version" string.
    mapping(bytes32 => bytes32) public manifestHashOf;

    event ReleaseAnchored(bytes32 indexed releaseId, bytes32 manifestHash);

    error NotOwner();
    error EmptyHash();
    error AlreadyAnchored(bytes32 releaseId);

    constructor() {
        owner = msg.sender;
    }

    /// @notice Anchor a manifest hash for a release. Records are write-once.
    function anchor(bytes32 releaseId, bytes32 manifestHash) external {
        if (msg.sender != owner) revert NotOwner();
        if (manifestHash == bytes32(0)) revert EmptyHash();
        if (manifestHashOf[releaseId] != bytes32(0)) revert AlreadyAnchored(releaseId);
        manifestHashOf[releaseId] = manifestHash;
        emit ReleaseAnchored(releaseId, manifestHash);
    }

    /// @notice True when a record exists and equals `manifestHash`.
    function matches(bytes32 releaseId, bytes32 manifestHash) external view returns (bool) {
        bytes32 stored = manifestHashOf[releaseId];
        return stored != bytes32(0) && stored == manifestHash;
    }
}
