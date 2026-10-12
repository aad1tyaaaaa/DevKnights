from fastapi.testclient import TestClient
from pydantic import SecretStr
from starlette.requests import Request

from app.core.config import settings
from app.core.security import api_key_rejection, submission_limiter
from app.main import app

LOCKFILE = {"lockfileVersion": 3, "packages": {"": {"dependencies": {}}}}


def test_without_a_key_the_api_is_open_for_local_development():
    client = TestClient(app)
    assert client.get("/api/scans").status_code == 200


def test_with_a_key_every_api_route_requires_it(monkeypatch):
    monkeypatch.setattr(settings, "api_key", SecretStr("demo-secret"))
    client = TestClient(app)

    assert client.get("/api/scans").status_code == 401
    assert client.get("/api/scans/anything/graph").status_code == 401
    assert client.post("/api/scans", json={"lockfile": LOCKFILE}).status_code == 401
    assert client.get("/api/scans", headers={"X-Provenyx-Key": "wrong"}).status_code == 401
    assert client.get("/api/scans", headers={"X-Provenyx-Key": "demo-secret"}).status_code == 200
    assert client.get("/health").status_code == 200  # connectivity checks stay open


def test_configured_github_bearer_reaches_only_authenticated_extension_routes(monkeypatch):
    monkeypatch.setattr(settings, "api_key", SecretStr("demo-secret"))
    monkeypatch.setattr(settings, "github_client_id", "client-id")
    monkeypatch.setattr(settings, "github_client_secret", SecretStr("client-secret"))
    monkeypatch.setattr(settings, "github_session_secret", SecretStr("session-secret"))

    def request(path: str, authorization: str = "Bearer github-token") -> Request:
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": path,
                "headers": [(b"authorization", authorization.encode())],
                "query_string": b"",
                "server": ("testserver", 80),
                "client": ("testclient", 50000),
                "scheme": "http",
            }
        )

    assert api_key_rejection(request("/api/github/auth/extension")) is None
    assert api_key_rejection(request("/api/scans")) is None
    assert api_key_rejection(request("/api/scans/scan-id/findings")) is None
    assert api_key_rejection(request("/api/gate")) is not None
    assert api_key_rejection(request("/api/scans", "Basic credentials")) is not None


def test_github_bearer_cannot_bypass_api_key_when_oauth_is_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "api_key", SecretStr("demo-secret"))
    monkeypatch.setattr(settings, "github_client_id", None)

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/scans",
            "headers": [(b"authorization", b"Bearer github-token")],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        }
    )

    assert api_key_rejection(request) is not None


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


def test_sign_in_return_path_cannot_be_used_as_an_open_redirect():
    from app.api.routes import safe_next_path

    assert safe_next_path("/dashboard") == "/dashboard"
    assert safe_next_path("/scans/123?tab=graph") == "/scans/123?tab=graph"
    for hostile in (None, "", "dashboard", "//evil.example", r"/\evil.example", "https://evil.example", r"/x\y"):
        assert safe_next_path(hostile) == "/github"


def test_hosted_postgres_urls_select_the_psycopg_driver():
    from app.models.database import normalize_database_url

    assert normalize_database_url("postgres://u:p@host/db?sslmode=require") == "postgresql+psycopg://u:p@host/db?sslmode=require"
    assert normalize_database_url("postgresql://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert normalize_database_url("sqlite:///./provenyx.db") == "sqlite:///./provenyx.db"


def test_session_cookie_is_sealed_tamper_evident_and_expires(monkeypatch):
    import time

    from app.github import EncryptedCookieCodec

    codec = EncryptedCookieCodec("session-secret")
    sealed = codec.encode({"token": "gho_secret"}, max_age=60)

    assert "gho_secret" not in sealed
    assert codec.decode(sealed)["token"] == "gho_secret"
    assert EncryptedCookieCodec("other-secret").decode(sealed) is None
    tampered = sealed[:-2] + ("A" if sealed[-2] != "A" else "B") + sealed[-1]
    assert codec.decode(tampered) is None
    assert codec.decode("not-a-cookie") is None
    monkeypatch.setattr(time, "time", lambda: 10**12)
    assert codec.decode(sealed) is None


def test_production_settings_follow_from_the_dashboard_url():
    from app.core.config import Settings

    local = Settings(_env_file=None)
    assert local.github_callback == "http://localhost:8000/api/github/auth/callback"
    assert local.cookies_secure is False

    deployed = Settings(_env_file=None, frontend_url="https://provenyx.vercel.app/")
    assert deployed.github_callback == "https://provenyx.vercel.app/api/github/auth/callback"
    assert deployed.cookies_secure is True
    assert "https://provenyx.vercel.app" in deployed.cors_origin_list

    explicit = Settings(
        _env_file=None, frontend_url="https://x.vercel.app", github_callback_url="https://api.example/cb", secure_cookies=False
    )
    assert (explicit.github_callback, explicit.cookies_secure) == ("https://api.example/cb", False)
