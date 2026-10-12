"""Read-only client for the ReleaseRegistry contract over JSON-RPC (no wallet, no writes)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.blockchain.manifest import keccak256

RECORD_OF_SELECTOR = keccak256(b"recordOf(bytes32)")[:10]  # 0xd1c60a3a
ZERO_HASH = "0x" + "00" * 32
LOCAL_CHAIN_IDS = {31337: "hardhat-local"}


class RegistryUnavailable(Exception):
    """The registry cannot be queried: not deployed/configured, or the chain is unreachable."""


@dataclass(frozen=True)
class RegistryInfo:
    network: str
    chain_id: int
    address: str


@dataclass(frozen=True)
class Record:
    manifest_hash: str | None  # None when there is no record
    anchored_at: datetime | None


class ReleaseRegistryReader:
    def __init__(
        self,
        *,
        rpc_url: str,
        deployment_file: str | None = None,
        address: str | None = None,
        timeout_seconds: float = 3.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._rpc_url = rpc_url
        self._deployment_file = deployment_file
        self._address = address
        self._timeout = timeout_seconds
        self._transport = transport

    def _contract_address(self) -> str:
        if self._address:
            return self._address
        if not self._deployment_file:
            raise RegistryUnavailable("No release registry is configured")
        path = Path(self._deployment_file)
        try:
            return json.loads(path.read_text(encoding="utf-8"))["address"]
        except FileNotFoundError:
            raise RegistryUnavailable("Release registry is not deployed (run `npm --prefix contracts run deploy:local`)")
        except (ValueError, KeyError, TypeError):
            raise RegistryUnavailable(f"Deployment file {path.name} is invalid")

    def _rpc(self, client: httpx.Client, method: str, params: list) -> str:
        try:
            r = client.post(self._rpc_url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
            r.raise_for_status()
            body = r.json()
        except (httpx.HTTPError, ValueError):
            raise RegistryUnavailable("Release registry chain is unreachable")
        if not isinstance(body, dict) or "error" in body or not isinstance(body.get("result"), str):
            raise RegistryUnavailable("Release registry call failed")
        return body["result"]

    def lookup(self, release_id: str) -> tuple[RegistryInfo, Record]:
        address = self._contract_address()
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            chain_id = int(self._rpc(client, "eth_chainId", []), 16)
            data = RECORD_OF_SELECTOR + release_id.removeprefix("0x").rjust(64, "0")
            result = self._rpc(client, "eth_call", [{"to": address, "data": data}, "latest"]).removeprefix("0x")
        if len(result) < 128:
            # No contract at this address (e.g. the chain was restarted without redeploying).
            raise RegistryUnavailable("Release registry contract not found on the chain; redeploy it")
        info = RegistryInfo(network=LOCAL_CHAIN_IDS.get(chain_id, f"chain-{chain_id}"), chain_id=chain_id, address=address)
        stored = "0x" + result[:64]
        if stored == ZERO_HASH:
            return info, Record(None, None)
        anchored_at = datetime.fromtimestamp(int(result[64:128], 16), tz=timezone.utc)
        return info, Record(stored, anchored_at)
