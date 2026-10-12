from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import submission_limiter
from app.main import app

LOCKFILE = {"lockfileVersion": 3, "packages": {"": {"dependencies": {}}}}


def test_without_a_key_the_api_is_open_for_local_development():
    client = TestClient(app)
    assert client.get("/api/scans").status_code == 200


def test_with_a_key_every_api_route_requires_it(monkeypatch):
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "api_key", SecretStr("demo-secret"))
    client = TestClient(app)

    assert client.get("/api/scans").status_code == 401
    assert client.get("/api/scans/anything/graph").status_code == 401
    assert client.post("/api/scans", json={"lockfile": LOCKFILE}).status_code == 401
    assert client.get("/api/scans", headers={"X-Provenyx-Key": "wrong"}).status_code == 401
    assert client.get("/api/scans", headers={"X-Provenyx-Key": "demo-secret"}).status_code == 200
    assert client.get("/health").status_code == 200  # connectivity checks stay open


def test_rejections_still_carry_cors_headers_so_the_dashboard_can_read_them(monkeypatch):
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "api_key", SecretStr("demo-secret"))
    response = TestClient(app).get("/api/scans", headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_submissions_are_rate_limited_per_client(monkeypatch):
    monkeypatch.setattr(submission_limiter, "limit", 2)
    client = TestClient(app)

    statuses = [client.post("/api/scans", json={"lockfile": LOCKFILE}).status_code for _ in range(3)]

    assert statuses == [202, 202, 429]
    assert client.get("/api/scans").status_code == 200  # reads are not limited


def test_scan_listing_is_paginated():
    client = TestClient(app)
    for _ in range(3):
        client.post("/api/scans", json={"lockfile": LOCKFILE})

    assert len(client.get("/api/scans", params={"limit": 2}).json()) == 2
    assert len(client.get("/api/scans", params={"limit": 2, "offset": 2}).json()) == 1
    assert client.get("/api/scans", params={"limit": 500}).status_code == 422
