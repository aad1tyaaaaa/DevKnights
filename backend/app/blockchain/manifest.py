"""Canonical release manifests and their hashes.

The same rules are implemented in contracts/scripts/manifest.ts; both sides are pinned to shared test vectors.

    manifest = {"schema_version": 1, "name": <name>, "version": <version>, "integrity": <npm dist.integrity>}
    bytes    = UTF-8 JSON, keys sorted, no whitespace
    hash     = keccak256(bytes)
    release  = keccak256(utf8("<name>@<version>"))

Usage (prints entries ready for contracts/anchors.json; fetches public npm metadata):
    python -m app.blockchain.manifest ms@2.1.3 left-pad@1.3.0
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from Crypto.Hash import keccak

SCHEMA_VERSION = 1


def keccak256(data: bytes) -> str:
    return "0x" + keccak.new(digest_bits=256, data=data).hexdigest()


def release_id(name: str, version: str) -> str:
    return keccak256(f"{name}@{version}".encode("utf-8"))


def canonical_manifest(name: str, version: str, integrity: str) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "name": name, "version": version, "integrity": integrity}


def manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def manifest_hash(manifest: dict[str, Any]) -> str:
    return keccak256(manifest_bytes(manifest))


def split_spec(spec: str) -> tuple[str, str]:
    """'name@version' or '@scope/name@version' -> (name, version)."""
    at = spec.rfind("@")
    if at <= 0:
        raise ValueError(f"expected name@version, got {spec!r}")
    return spec[:at], spec[at + 1 :]


async def _anchor_entries(specs: list[str]) -> list[dict[str, str]]:
    from app.core.config import settings
    from app.parsers.npm_registry import NpmRegistryClient

    releases = [split_spec(s) for s in specs]
    client = NpmRegistryClient(base_url=settings.npm_registry_url, timeout_seconds=settings.npm_registry_timeout_seconds)
    metadata = await client.fetch_many(releases)
    entries = []
    for name, version in releases:
        meta = metadata[(name, version)]
        if meta.status != "available" or not meta.dist_integrity:
            raise SystemExit(f"{name}@{version}: npm metadata unavailable ({meta.error or 'no dist.integrity'}); refusing to anchor")
        entries.append(
            {"package": name, "version": version, "manifestHash": manifest_hash(canonical_manifest(name, version, meta.dist_integrity))}
        )
    return entries


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    print(json.dumps(asyncio.run(_anchor_entries(sys.argv[1:])), indent=2))
