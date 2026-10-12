import asyncio

import httpx

from app.detection.osv import OsvClient


def test_osv_client_queries_exact_npm_release_and_parses_advisories():
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(__import__("json").loads(request.content))
        return httpx.Response(
            200,
            json={
                "vulns": [
                    {
                        "id": "GHSA-test-1234",
                        "aliases": ["CVE-2026-0001"],
                        "summary": "Synthetic advisory",
                        "database_specific": {"severity": "HIGH"},
                    }
                ]
            },
        )

    client = OsvClient(transport=httpx.MockTransport(handler), retries=0)
    result = asyncio.run(client.fetch_many([("minimist", "1.2.5")]))[("minimist", "1.2.5")]

    assert requests == [{"package": {"ecosystem": "npm", "name": "minimist"}, "version": "1.2.5"}]
    assert result is not None
    assert result[0].id == "GHSA-test-1234"
    assert result[0].aliases == ("CVE-2026-0001",)
    assert result[0].severity == "high"


def test_osv_client_distinguishes_no_advisories_from_unavailable():
    empty = OsvClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})), retries=0)
    unavailable = OsvClient(
        transport=httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("offline", request=request))),
        retries=0,
    )

    assert asyncio.run(empty.fetch_many([("safe", "1.0.0")]))[("safe", "1.0.0")] == ()
    assert asyncio.run(unavailable.fetch_many([("unknown", "1.0.0")]))[("unknown", "1.0.0")] is None


def test_osv_client_caches_duplicate_releases():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    async def fetch_twice() -> None:
        client = OsvClient(transport=httpx.MockTransport(handler), retries=0)
        await client.fetch_many([("pkg", "1.0.0"), ("pkg", "1.0.0")])
        await client.fetch_many([("pkg", "1.0.0")])

    asyncio.run(fetch_twice())
    assert calls == 1
