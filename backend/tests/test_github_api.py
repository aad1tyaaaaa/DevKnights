import base64
import json
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.routes import get_github_service
from app.core.config import Settings
from app.github import GitHubService
from app.main import app


def github_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/login/oauth/access_token":
        return httpx.Response(200, json={"access_token": "github-token"})
    if request.url.path == "/user":
        return httpx.Response(200, json={"login": "octocat", "avatar_url": "https://avatars.example/octocat"})
    if request.url.path == "/user/repos":
        assert request.headers["authorization"] == "Bearer github-token"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 42,
                    "name": "private-app",
                    "full_name": "octocat/private-app",
                    "private": True,
                    "description": "Private npm application",
                    "default_branch": "main",
                    "html_url": "https://github.com/octocat/private-app",
                    "updated_at": "2026-10-12T10:00:00Z",
                    "owner": {"avatar_url": "https://avatars.example/octocat"},
                }
            ],
        )
    if request.url.path == "/repos/octocat/private-app":
        return httpx.Response(200, json={"default_branch": "main"})
    if request.url.path == "/repos/octocat/private-app/git/trees/main":
        assert request.url.params["recursive"] == "1"
        return httpx.Response(
            200,
            json={
                "tree": [
                    {"path": "package-lock.json", "type": "blob"},
                    {"path": "apps/web/package-lock.json", "type": "blob"},
                    {"path": "node_modules/pkg/package-lock.json", "type": "blob"},
                    {"path": "README.md", "type": "blob"},
                ]
            },
        )
    if request.url.path == "/repos/octocat/private-app/contents/package-lock.json":
        lockfile = {
            "name": "private-app",
            "lockfileVersion": 3,
            "packages": {"": {"name": "private-app"}},
        }
        encoded = base64.b64encode(json.dumps(lockfile).encode()).decode()
        return httpx.Response(200, json={"type": "file", "size": len(encoded), "content": encoded})
    return httpx.Response(404, json={"message": "Not Found"})


def configured_github() -> GitHubService:
    return GitHubService(
        Settings(
            github_client_id="client-id",
            github_client_secret=SecretStr("client-secret"),
            github_session_secret=SecretStr("session-secret"),
            github_api_url="https://api.github.test",
            github_oauth_url="https://github.test/login/oauth",
        ),
        transport=httpx.MockTransport(github_handler),
    )


def test_github_oauth_lists_repositories_and_scans_lockfile() -> None:
    github = configured_github()
    app.dependency_overrides[get_github_service] = lambda: github

    with TestClient(app, follow_redirects=False) as client:
        login = client.get("/api/github/auth/login")
        assert login.status_code == 307
        query = parse_qs(urlparse(login.headers["location"]).query)
        assert query["client_id"] == ["client-id"]
        assert query["scope"] == ["repo read:user"]

        callback = client.get(
            "/api/github/auth/callback",
            params={"code": "oauth-code", "state": query["state"][0]},
        )
        assert callback.status_code == 307
        assert callback.headers["location"] == "http://localhost:3000/github?connected=1"

        auth = client.get("/api/github/auth/status")
        assert auth.json() == {
            "configured": True,
            "connected": True,
            "login": "octocat",
            "avatar_url": "https://avatars.example/octocat",
        }

        repositories = client.get("/api/github/repositories")
        assert repositories.status_code == 200
        assert repositories.json()[0]["full_name"] == "octocat/private-app"
        assert repositories.json()[0]["private"] is True

        lockfiles = client.get("/api/github/repositories/octocat/private-app/lockfiles")
        assert lockfiles.json() == ["apps/web/package-lock.json", "package-lock.json"]

        accepted = client.post(
            "/api/github/scans",
            json={"owner": "octocat", "repository": "private-app"},
        )
        assert accepted.status_code == 202
        scan_id = accepted.json()["scan_id"]
        scan = client.get(f"/api/scans/{scan_id}").json()
        assert scan["status"] == "complete"
        assert scan["project_name"] == "octocat/private-app"

    app.dependency_overrides.pop(get_github_service, None)


def test_github_repositories_require_connection() -> None:
    github = configured_github()
    app.dependency_overrides[get_github_service] = lambda: github
    with TestClient(app) as client:
        response = client.get("/api/github/repositories")
    app.dependency_overrides.pop(get_github_service, None)

    assert response.status_code == 401
    assert response.json()["detail"] == "Connect a GitHub account first"


def test_github_scan_rejects_unsafe_lockfile_path() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/github/scans",
            json={"owner": "octocat", "repository": "private-app", "lockfile_path": "../package-lock.json"},
        )

    assert response.status_code == 422

def test_sign_in_returns_to_the_requested_page_and_reports_failures_there() -> None:
    github = configured_github()
    app.dependency_overrides[get_github_service] = lambda: github

    with TestClient(app, follow_redirects=False) as client:
        login = client.get("/api/github/auth/login", params={"next": "/dashboard"})
        state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
        callback = client.get("/api/github/auth/callback", params={"code": "oauth-code", "state": state})
        assert callback.headers["location"] == "http://localhost:3000/dashboard?connected=1"

        client.get("/api/github/auth/login", params={"next": "//evil.example"})
        denied = client.get("/api/github/auth/callback", params={"error": "access_denied"})
        assert denied.headers["location"] == "http://localhost:3000/github?github_error=access_denied"
    app.dependency_overrides.clear()
