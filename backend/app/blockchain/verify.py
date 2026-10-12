from __future__ import annotations

import asyncio

from app.blockchain.manifest import canonical_manifest, manifest_hash, release_id
from app.blockchain.registry import RegistryUnavailable, ReleaseRegistryReader
from app.models.schemas import RegistryLocation, VerificationResult
from app.parsers.npm_registry import NpmRegistryClient


class ReleaseVerifier:
    """Compares a release's current canonical manifest with the hash anchored on-chain.

    match      -> metadata equals the approved record (not a safety verdict)
    mismatch   -> metadata differs from the approved record
    no_record  -> nothing anchored: an evidence gap, never a risk signal
    unavailable-> chain or metadata unreachable; nothing is concluded
    """

    def __init__(self, registry: ReleaseRegistryReader, npm: NpmRegistryClient) -> None:
        self.registry = registry
        self.npm = npm

    async def verify(self, name: str, version: str) -> VerificationResult:
        rid = release_id(name, version)
        result = VerificationResult(package=name, version=version, release_id=rid, status="unavailable")

        # Current manifest (best effort): even with no record it is useful to show what would be anchored.
        meta = (await self.npm.fetch_many([(name, version)]))[(name, version)]
        if meta.status == "available" and meta.dist_integrity:
            result.manifest = canonical_manifest(name, version, meta.dist_integrity)
            result.manifest_hash = manifest_hash(result.manifest)

        try:
            info, record = await asyncio.to_thread(self.registry.lookup, rid)
        except RegistryUnavailable as exc:
            result.detail = str(exc)
            return result

        result.registry = RegistryLocation(network=info.network, chain_id=info.chain_id, address=info.address)
        if record.manifest_hash is None:
            result.status = "no_record"
            return result

        result.anchored_hash = record.manifest_hash
        result.anchored_at = record.anchored_at
        if result.manifest_hash is None:
            result.detail = f"Current npm metadata could not be read ({meta.error or 'no dist.integrity'}), so it cannot be compared"
            return result
        result.status = "match" if result.manifest_hash == record.manifest_hash else "mismatch"
        return result
