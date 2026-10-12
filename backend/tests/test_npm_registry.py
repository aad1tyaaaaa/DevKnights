import asyncio

import httpx

from app.parsers.npm_registry import NpmRegistryClient


def test_registry_client_selects_real_metadata_and_encodes_scoped_names():
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.raw_path.decode())
        return httpx.Response(
            200,
            json={
                "name": "@scope/pkg",
                "version": "1.2.3",
                "description": "Scoped package",
                "license": "MIT",
                "_npmUser": {"name": "release-publisher", "email": "private@example.test"},
                "dist": {"integrity": "sha512-registry"},
            },
        )

    registry = NpmRegistryClient(transport=httpx.MockTransport(handler), retries=0)
    result = asyncio.run(registry.fetch_many([("@scope/pkg", "1.2.3")]))[("@scope/pkg", "1.2.3")]

    assert result.status == "available"
    assert result.publisher == "release-publisher"
    assert result.description == "Scoped package"
    assert result.dist_integrity == "sha512-registry"
    assert seen_paths == ["/%40scope%2Fpkg/1.2.3"]


def test_registry_client_caches_release_results():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"name": "pkg", "version": "1.0.0"})

    async def fetch_twice() -> None:
        registry = NpmRegistryClient(transport=httpx.MockTransport(handler), retries=0)
        await registry.fetch_many([("pkg", "1.0.0"), ("pkg", "1.0.0")])
        await registry.fetch_many([("pkg", "1.0.0")])

    asyncio.run(fetch_twice())
    assert calls == 1


def test_registry_client_retries_server_errors_then_succeeds():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"name": "pkg", "version": "1.0.0"})

    registry = NpmRegistryClient(transport=httpx.MockTransport(handler), retries=1)
    result = asyncio.run(registry.fetch_many([("pkg", "1.0.0")]))[("pkg", "1.0.0")]

    assert calls == 2
    assert result.status == "available"


def test_registry_client_marks_network_failure_and_missing_release_unavailable():
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    timeout_registry = NpmRegistryClient(transport=httpx.MockTransport(timeout_handler), retries=0)
    timeout_result = asyncio.run(timeout_registry.fetch_many([("pkg", "1.0.0")]))[("pkg", "1.0.0")]
    assert timeout_result.status == "unavailable"
    assert timeout_result.error == "npm registry request failed: ReadTimeout"

    missing_registry = NpmRegistryClient(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    missing_result = asyncio.run(missing_registry.fetch_many([("missing", "1.0.0")]))[("missing", "1.0.0")]
    assert missing_result.status == "unavailable"
    assert "not found" in (missing_result.error or "")


def test_registry_client_fetches_and_caches_release_history():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "time": {
                    "created": "2026-01-01T00:00:00Z",
                    "modified": "2026-01-02T00:00:00Z",
                    "1.0.0": "2026-01-01T10:00:00Z",
                    "1.1.0": "2026-01-01T10:30:00Z",
                }
            },
        )

    async def fetch_twice():
        registry = NpmRegistryClient(transport=httpx.MockTransport(handler), retries=0)
        first = await registry.fetch_release_times("@scope/pkg")
        second = await registry.fetch_release_times("@scope/pkg")
        return first, second

    first, second = asyncio.run(fetch_twice())

    assert first == second == {
        "1.0.0": "2026-01-01T10:00:00Z",
        "1.1.0": "2026-01-01T10:30:00Z",
    }
    assert calls == 1


def test_registry_history_batch_deduplicates_packages():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"time": {"1.0.0": "2026-01-01T10:00:00Z"}})

    registry = NpmRegistryClient(transport=httpx.MockTransport(handler), retries=0, concurrency=2)
    result = asyncio.run(registry.fetch_release_times_many(["a", "b", "a"]))

    assert set(result) == {"a", "b"}
    assert result["a"] == {"1.0.0": "2026-01-01T10:00:00Z"}