import json

import httpx


def osv_transport(
    records_by_release: dict[tuple[str, str], list[dict]] | None = None,
    calls: list[str] | None = None,
) -> httpx.MockTransport:
    """Fake OSV: /v1/querybatch answers by position with matched ids; /v1/vulns/{id} returns the full record."""
    records_by_release = records_by_release or {}
    records = {record["id"]: record for matched in records_by_release.values() for record in matched}

    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.path)
        if request.url.path == "/v1/querybatch":
            queries = json.loads(request.content)["queries"]
            results = [
                {"vulns": [{"id": record["id"]} for record in records_by_release.get((q["package"]["name"], q["version"]), [])]}
                for q in queries
            ]
            return httpx.Response(200, json={"results": results})
        vuln_id = request.url.path.removeprefix("/v1/vulns/")
        return httpx.Response(200, json=records[vuln_id]) if vuln_id in records else httpx.Response(404)

    return httpx.MockTransport(handler)
