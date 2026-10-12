from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import quote

import httpx


@dataclass(frozen=True)
class RegistryMetadata:
    package: str
    version: str
    status: str
    description: str | None = None
    license: str | None = None
    deprecated: str | None = None
    published_at: str | None = None
    dist_integrity: str | None = None
    error: str | None = None


class NpmRegistryClient:
    def __init__(
        self,
        *,
        base_url: str = "https://registry.npmjs.org",
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
        self._cache: dict[tuple[str, str], RegistryMetadata] = {}
        self._release_times_cache: dict[str, dict[str, str] | None] = {}

    async def fetch_many(self, releases: Iterable[tuple[str, str]]) -> dict[tuple[str, str], RegistryMetadata]:
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
            self._cache.update({(result.package, result.version): result for result in results})
        return {release: self._cache[release] for release in unique_releases}

    async def fetch_release_times(self, package: str) -> dict[str, str] | None:
        if package in self._release_times_cache:
            return self._release_times_cache[package]
        endpoint = f"/{quote(package, safe='')}"
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
            follow_redirects=False,
        ) as client:
            for attempt in range(self._retries + 1):
                try:
                    response = await client.get(endpoint)
                    if response.status_code == 404:
                        self._release_times_cache[package] = None
                        return None
                    response.raise_for_status()
                    payload = response.json()
                    times = payload.get("time") if isinstance(payload, dict) else None
                    result = {
                        str(version): timestamp
                        for version, timestamp in times.items()
                        if version not in {"created", "modified"} and isinstance(timestamp, str)
                    } if isinstance(times, dict) else None
                    self._release_times_cache[package] = result
                    return result
                except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
                    if attempt == self._retries:
                        self._release_times_cache[package] = None
                        return None
                except httpx.HTTPStatusError as exc:
                    if attempt == self._retries or exc.response.status_code < 500:
                        self._release_times_cache[package] = None
                        return None
                except (ValueError, TypeError):
                    self._release_times_cache[package] = None
                    return None
                await asyncio.sleep(0.1 * (attempt + 1))
        self._release_times_cache[package] = None
        return None

    async def fetch_release_times_many(self, packages: Iterable[str]) -> dict[str, dict[str, str] | None]:
        unique_packages = tuple(dict.fromkeys(packages))
        semaphore = asyncio.Semaphore(self._concurrency)

        async def fetch_bounded(package: str) -> tuple[str, dict[str, str] | None]:
            async with semaphore:
                return package, await self.fetch_release_times(package)

        results = await asyncio.gather(*(fetch_bounded(package) for package in unique_packages))
        return dict(results)

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        package: str,
        version: str,
    ) -> RegistryMetadata:
        endpoint = f"/{quote(package, safe='')}/{quote(version, safe='')}"
        async with semaphore:
            for attempt in range(self._retries + 1):
                try:
                    response = await client.get(endpoint)
                    if response.status_code == 404:
                        return _unavailable(package, version, "Release metadata was not found in the npm registry")
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        return _unavailable(package, version, "npm registry returned an invalid response")
                    return _metadata_from_payload(package, version, payload)
                except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                    if attempt == self._retries:
                        return _unavailable(package, version, f"npm registry request failed: {type(exc).__name__}")
                except httpx.HTTPStatusError as exc:
                    if attempt == self._retries or exc.response.status_code < 500:
                        return _unavailable(
                            package,
                            version,
                            f"npm registry returned HTTP {exc.response.status_code}",
                        )
                except (ValueError, TypeError):
                    return _unavailable(package, version, "npm registry returned invalid JSON")
                await asyncio.sleep(0.1 * (attempt + 1))
        return _unavailable(package, version, "npm registry request failed")


def _metadata_from_payload(package: str, version: str, payload: dict[str, Any]) -> RegistryMetadata:
    dist = payload.get("dist")
    dist_data = dist if isinstance(dist, dict) else {}
    return RegistryMetadata(
        package=package,
        version=version,
        status="available",
        description=_optional_string(payload.get("description")),
        license=_license_string(payload.get("license")),
        deprecated=_optional_string(payload.get("deprecated")),
        published_at=None,
        dist_integrity=_optional_string(dist_data.get("integrity")),
    )


def _unavailable(package: str, version: str, error: str) -> RegistryMetadata:
    return RegistryMetadata(package=package, version=version, status="unavailable", error=error)


def _license_string(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        return _optional_string(value.get("type"))
    return None


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None