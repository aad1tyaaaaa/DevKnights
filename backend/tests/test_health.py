import json

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)

VALID_LOCKFILE = {
    "name": "demo",
    "version": "1.0.0",
    "lockfileVersion": 3,
    "requires": True,
    "packages": {"": {"name": "demo", "version": "1.0.0"}},
}


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "provenyx-api", "version": "0.1.0"}


def test_scan_accepts_valid_lockfile():
    r = client.post("/api/scans", json={"lockfile": VALID_LOCKFILE, "project_name": "demo"})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "accepted"
    assert len(body["scan_id"]) == 36
    assert "analysis has started" in body["message"]


def test_scan_rejects_invalid_lockfile():
    for bad in [
        {"lockfile": {"name": "x"}},  # missing lockfileVersion
        {"lockfile": {"lockfileVersion": 9, "packages": {}}},  # unsupported version
        {"lockfile": {"lockfileVersion": 3}},  # v3 without packages
        {"lockfile": "not-an-object"},
        {"wrong": {}},
    ]:
        r = client.post("/api/scans", json=bad)
        assert r.status_code == 422, bad


def test_scan_rejects_malformed_json_and_wrong_type():
    r = client.post("/api/scans", content=b"{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    r = client.post("/api/scans", content=b"lockfileVersion=3", headers={"Content-Type": "text/plain"})
    assert r.status_code == 415


def test_scan_rejects_oversized_body():
    filler = "x" * (settings.max_scan_bytes + 1)
    payload = json.dumps({"lockfile": {**VALID_LOCKFILE, "pad": filler}}).encode()
    r = client.post("/api/scans", content=payload, headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_cors_allows_local_dashboard_only():
    ok = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    other = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers
