// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/// @title Provenyx release registry
/// @notice Stores hashes of approved release manifests. It never stores dependency graphs or package source.
/// A recorded hash proves only that this exact manifest was anchored by the registry owner;
/// it is not a statement that the package is safe. A missing record is not evidence of maliciousness.
contract ReleaseRegistry {
    struct Record {
        bytes32 manifestHash;
        uint64 anchoredAt;
    }

    address public immutable owner;

    // releaseId = keccak256(utf8("<name>@<version>")).
    mapping(bytes32 => Record) private records;

    event ReleaseAnchored(bytes32 indexed releaseId, bytes32 manifestHash, uint64 anchoredAt);

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
        if (records[releaseId].manifestHash != bytes32(0)) revert AlreadyAnchored(releaseId);
        uint64 anchoredAt = uint64(block.timestamp);
        records[releaseId] = Record(manifestHash, anchoredAt);
        emit ReleaseAnchored(releaseId, manifestHash, anchoredAt);
    }

    /// @notice The anchored record; manifestHash is zero when no record exists.
    function recordOf(bytes32 releaseId) external view returns (bytes32 manifestHash, uint64 anchoredAt) {
        Record memory r = records[releaseId];
        return (r.manifestHash, r.anchoredAt);
    }

    /// @notice True when a record exists and equals `manifestHash`.
    function matches(bytes32 releaseId, bytes32 manifestHash) external view returns (bool) {
        bytes32 stored = records[releaseId].manifestHash;
        return stored != bytes32(0) && stored == manifestHash;
    }
}
