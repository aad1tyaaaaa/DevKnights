import asyncio
import json

import httpx
from fastapi.testclient import TestClient

from app.api.routes import get_release_verifier
from app.blockchain.manifest import canonical_manifest, manifest_bytes, manifest_hash, release_id, split_spec
from app.blockchain.registry import RECORD_OF_SELECTOR, ReleaseRegistryReader
from app.blockchain.verify import ReleaseVerifier
from app.main import app
from app.parsers.npm_registry import NpmRegistryClient

# Shared cross-language vectors: contracts/test/ReleaseRegistry.ts asserts the same values with viem.
MS_INTEGRITY = "sha512-6FlzubTLZG3J2a/NVCAleEhjzq5oxgHyaCU9yYXvcLsvoVaHJq/s5xXI6/XXP6tz7R9xAOtHnSO/tXtF3WRTlA=="
MS_RELEASE_ID = "0xa43c9c80df88be1fb6a327509e12f4e480ab9950e12150e7a357cd7f8df03228"
MS_MANIFEST_HASH = "0x7bcaaca2890ef8f5e14508703eb31a1dc5fff3e3e5c8e137c0184b179f550d4d"
ADDRESS = "0x5fbdb2315678afecb367f032d93f642f64180aa3"
ANCHORED_AT = 1_760_000_000


def test_cross_language_vectors():
    assert RECORD_OF_SELECTOR == "0xd1c60a3a"
    assert release_id("ms", "2.1.3") == MS_RELEASE_ID
    manifest = canonical_manifest("ms", "2.1.3", MS_INTEGRITY)
    assert manifest_bytes(manifest) == (
        b'{"integrity":"' + MS_INTEGRITY.encode() + b'","name":"ms","schema_version":1,"version":"2.1.3"}'
    )
    assert manifest_hash(manifest) == MS_MANIFEST_HASH
    assert split_spec("@scope/pkg@1.0.0") == ("@scope/pkg", "1.0.0")


def npm(integrity: str | None = MS_INTEGRITY, status: int = 200) -> NpmRegistryClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"name": "ms", "version": "2.1.3", "dist": {"integrity": integrity} if integrity else {}}
        return httpx.Response(status, json=body)

    return NpmRegistryClient(transport=httpx.MockTransport(handler), retries=0)


def chain(stored_hash: str | None, *, call_result: str | None = None) -> ReleaseRegistryReader:
    """Fake JSON-RPC node holding one record (or none)."""

    def handler(request: httpx.Request) -> httpx.Response:
        req = json.loads(request.content)
        if req["method"] == "eth_chainId":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x7a69"})
        assert req["params"][0]["to"] == ADDRESS
        assert req["params"][0]["data"] == RECORD_OF_SELECTOR + MS_RELEASE_ID[2:]
        if call_result is not None:
            result = call_result
        elif stored_hash is None:
            result = "0x" + "00" * 64
        else:
            result = stored_hash + format(ANCHORED_AT, "064x")
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    return ReleaseRegistryReader(rpc_url="http://chain", address=ADDRESS, transport=httpx.MockTransport(handler))


def verify(registry: ReleaseRegistryReader, npm_client: NpmRegistryClient):
    return asyncio.run(ReleaseVerifier(registry, npm_client).verify("ms", "2.1.3"))


def test_match_is_reported_with_source_details():
    r = verify(chain(MS_MANIFEST_HASH), npm())
    assert r.status == "match"
    assert r.anchored_hash == r.manifest_hash == MS_MANIFEST_HASH
    assert r.anchored_at.timestamp() == ANCHORED_AT
    assert r.registry.network == "hardhat-local" and r.registry.chain_id == 31337 and r.registry.address == ADDRESS
    assert r.manifest == canonical_manifest("ms", "2.1.3", MS_INTEGRITY)


def test_altered_metadata_is_a_mismatch():
    r = verify(chain(MS_MANIFEST_HASH), npm(integrity="sha512-altered"))
    assert r.status == "mismatch"
    assert r.manifest_hash != r.anchored_hash


def test_missing_record_is_no_record_not_mismatch():
    r = verify(chain(None), npm())
    assert r.status == "no_record"
    assert r.anchored_hash is None and r.anchored_at is None
    assert r.manifest_hash == MS_MANIFEST_HASH  # still shown so it can be reviewed and anchored


def test_unreachable_chain_is_unavailable():
    reader = ReleaseRegistryReader(rpc_url="http://127.0.0.1:9", address=ADDRESS, timeout_seconds=1)
    r = verify(reader, npm())
    assert r.status == "unavailable"
    assert "unreachable" in r.detail
    assert r.registry is None


def test_missing_deployment_or_contract_is_unavailable(tmp_path):
    reader = ReleaseRegistryReader(rpc_url="http://chain", deployment_file=str(tmp_path / "missing.json"))
    assert verify(reader, npm()).status == "unavailable"
    r = verify(chain(None, call_result="0x"), npm())  # chain restarted without redeploying
    assert r.status == "unavailable" and "redeploy" in r.detail


def test_record_without_readable_metadata_is_unavailable_not_mismatch():
    r = verify(chain(MS_MANIFEST_HASH), npm(status=404))
    assert r.status == "unavailable"
    assert r.anchored_hash == MS_MANIFEST_HASH
    assert r.manifest_hash is None


def test_verify_endpoint():
    app.dependency_overrides[get_release_verifier] = lambda: ReleaseVerifier(chain(MS_MANIFEST_HASH), npm())
    try:
        client = TestClient(app)
        r = client.post("/api/releases/verify", json={"package": "ms", "version": "2.1.3"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "match" and body["release_id"] == MS_RELEASE_ID
        for bad in [{"package": "ms"}, {"package": "../etc", "version": "1"}, {"package": "ms", "version": "1 2"},
                    {"package": "ms", "version": "1", "extra": True}]:
            assert client.post("/api/releases/verify", json=bad).status_code == 422, bad
    finally:
        app.dependency_overrides.clear()
