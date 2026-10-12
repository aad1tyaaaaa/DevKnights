from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Iterable

import httpx


@dataclass(frozen=True)
class OsvAdvisory:
    id: str
    aliases: tuple[str, ...]
    summary: str | None
    severity: str | None


class OsvClient:
    def __init__(
        self,
        *,
        base_url: str = "https://api.osv.dev",
        concurrency: int = 10,
        timeout_seconds: float = 5.0,
        retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._concurrency = max(1, concurrency)
        self._timeout = timeout_seconds
        self._retries = max(0, retries)
        self._transport = transport
        self._cache: dict[tuple[str, str], tuple[OsvAdvisory, ...] | None] = {}

    async def fetch_many(
        self, releases: Iterable[tuple[str, str]]
    ) -> dict[tuple[str, str], tuple[OsvAdvisory, ...] | None]:
        unique_releases = tuple(dict.fromkeys(releases))
        missing = [release for release in unique_releases if release not in self._cache]
        if missing:
            semaphore = asyncio.Semaphore(self._concurrency)
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                results = await asyncio.gather(
                    *(self._fetch_one(client, semaphore, package, version) for package, version in missing)
                )
            self._cache.update(dict(zip(missing, results, strict=True)))
        return {release: self._cache[release] for release in unique_releases}

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        package: str,
        version: str,
    ) -> tuple[OsvAdvisory, ...] | None:
        async with semaphore:
            for attempt in range(self._retries + 1):
                try:
                    response = await client.post(
                        "/v1/query",
                        json={"package": {"ecosystem": "npm", "name": package}, "version": version},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    return _advisories_from_payload(payload)
                except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
                    if attempt == self._retries:
                        return None
                except httpx.HTTPStatusError as exc:
                    if attempt == self._retries or exc.response.status_code < 500:
                        return None
                except (ValueError, TypeError):
                    return None
                await asyncio.sleep(0.1 * (attempt + 1))
        return None


def _advisories_from_payload(payload: Any) -> tuple[OsvAdvisory, ...]:
    if not isinstance(payload, dict):
        raise ValueError("OSV returned an invalid response")
    vulnerabilities = payload.get("vulns", [])
    if not isinstance(vulnerabilities, list):
        raise ValueError("OSV returned an invalid vulnerability list")

    advisories = []
    for vulnerability in vulnerabilities:
        if not isinstance(vulnerability, dict) or not isinstance(vulnerability.get("id"), str):
            continue
        database_specific = vulnerability.get("database_specific")
        severity = database_specific.get("severity") if isinstance(database_specific, dict) else None
        aliases = vulnerability.get("aliases")
        advisories.append(
            OsvAdvisory(
                id=vulnerability["id"],
                aliases=tuple(alias for alias in aliases if isinstance(alias, str)) if isinstance(aliases, list) else (),
                summary=vulnerability.get("summary") if isinstance(vulnerability.get("summary"), str) else None,
                severity=severity.lower() if isinstance(severity, str) else None,
            )
        )
    return tuple(sorted(advisories, key=lambda advisory: advisory.id))
