from __future__ import annotations

import base64
import hashlib
import json
import time
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from Crypto.Cipher import AES

from app.core.config import Settings
from app.models.schemas import GitHubRepository


class GitHubApiError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class EncryptedCookieCodec:
    def __init__(self, secret: str) -> None:
        self._key = hashlib.sha256(secret.encode("utf-8")).digest()

    def encode(self, payload: dict[str, Any], max_age: int) -> str:
        value = {**payload, "exp": int(time.time()) + max_age}
        cipher = AES.new(self._key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(json.dumps(value, separators=(",", ":")).encode("utf-8"))
        return base64.urlsafe_b64encode(cipher.nonce + tag + ciphertext).decode("ascii").rstrip("=")

    def decode(self, value: str | None) -> dict[str, Any] | None:
        if not value:
            return None
        try:
            raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
            cipher = AES.new(self._key, AES.MODE_GCM, nonce=raw[:16])
            payload = json.loads(cipher.decrypt_and_verify(raw[32:], raw[16:32]))
            if not isinstance(payload, dict) or payload.get("exp", 0) < time.time():
                return None
            return payload
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None


class GitHubService:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    @property
    def configured(self) -> bool:
        return self.settings.github_auth_configured

    @property
    def codec(self) -> EncryptedCookieCodec:
        secret = self.settings.github_session_secret
        if secret is None:
            raise RuntimeError("GitHub authentication is not configured")
        return EncryptedCookieCodec(secret.get_secret_value())

    def authorization_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self.settings.github_client_id,
                "redirect_uri": self.settings.github_callback_url,
                "scope": "repo read:user",
                "state": state,
            }
        )
        return f"{self.settings.github_oauth_url}/authorize?{query}"

    async def exchange_code(self, code: str) -> str:
        secret = self.settings.github_client_secret
        if secret is None:
            raise RuntimeError("GitHub authentication is not configured")
        async with self._client() as client:
            response = await client.post(
                f"{self.settings.github_oauth_url}/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": self.settings.github_client_id,
                    "client_secret": secret.get_secret_value(),
                    "code": code,
                    "redirect_uri": self.settings.github_callback_url,
                },
            )
        self._raise_for_status(response)
        token = response.json().get("access_token")
        if not isinstance(token, str) or not token:
            raise GitHubApiError(502, "GitHub did not return an access token")
        return token

    async def get_user(self, token: str) -> dict[str, Any]:
        response = await self._get("/user", token)
        return response.json()

    async def list_repositories(self, token: str) -> list[GitHubRepository]:
        repositories: list[GitHubRepository] = []
        page = 1
        while True:
            response = await self._get(
                "/user/repos",
                token,
                params={
                    "affiliation": "owner,collaborator,organization_member",
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": "100",
                    "page": str(page),
                },
            )
            items = response.json()
            if not isinstance(items, list):
                raise GitHubApiError(502, "GitHub returned an invalid repository list")
            repositories.extend(
                GitHubRepository(
                    id=item["id"],
                    name=item["name"],
                    full_name=item["full_name"],
                    private=item["private"],
                    description=item.get("description"),
                    default_branch=item["default_branch"],
                    html_url=item["html_url"],
                    updated_at=item["updated_at"],
                    owner_avatar_url=item.get("owner", {}).get("avatar_url"),
                )
                for item in items
            )
            if len(items) < 100:
                return repositories
            page += 1

    async def fetch_lockfile(self, token: str, owner: str, repository: str, path: str, max_bytes: int) -> bytes:
        escaped_path = "/".join(quote(part, safe="") for part in path.split("/"))
        prefix = f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}"
        response = await self._get(f"{prefix}/contents/{escaped_path}", token)
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("type") != "file":
            raise GitHubApiError(422, "The selected path is not a file")
        if payload.get("size", 0) > max_bytes:
            raise GitHubApiError(413, f"Lockfile exceeds the {max_bytes} byte limit")
        content = payload.get("content")
        if not isinstance(content, str):
            sha = payload.get("sha")
            if not isinstance(sha, str):
                raise GitHubApiError(502, "GitHub did not return the lockfile contents")
            blob = (await self._get(f"{prefix}/git/blobs/{quote(sha, safe='')}", token)).json()
            content = blob.get("content") if isinstance(blob, dict) else None
        if not isinstance(content, str):
            raise GitHubApiError(502, "GitHub did not return the lockfile contents")
        try:
            decoded = base64.b64decode(content, validate=False)
        except ValueError as exc:
            raise GitHubApiError(502, "GitHub returned invalid lockfile content") from exc
        if len(decoded) > max_bytes:
            raise GitHubApiError(413, f"Lockfile exceeds the {max_bytes} byte limit")
        return decoded

    async def find_lockfiles(self, token: str, owner: str, repository: str) -> list[str]:
        prefix = f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}"
        repository_payload = (await self._get(prefix, token)).json()
        branch = repository_payload.get("default_branch") if isinstance(repository_payload, dict) else None
        if not isinstance(branch, str):
            raise GitHubApiError(502, "GitHub did not return the default branch")
        tree_payload = (
            await self._get(f"{prefix}/git/trees/{quote(branch, safe='')}", token, params={"recursive": "1"})
        ).json()
        tree = tree_payload.get("tree") if isinstance(tree_payload, dict) else None
        if not isinstance(tree, list):
            raise GitHubApiError(502, "GitHub did not return the repository tree")
        return sorted(
            item["path"]
            for item in tree
            if isinstance(item, dict)
            and item.get("type") == "blob"
            and isinstance(item.get("path"), str)
            and (item["path"] == "package-lock.json" or item["path"].endswith("/package-lock.json"))
            and "node_modules/" not in item["path"]
        )

    async def _get(self, path: str, token: str, params: dict[str, str] | None = None) -> httpx.Response:
        async with self._client() as client:
            response = await client.get(
                f"{self.settings.github_api_url}{path}",
                params=params,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        self._raise_for_status(response)
        return response

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=15.0, follow_redirects=False)

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            message = response.json().get("message")
        except (json.JSONDecodeError, AttributeError):
            message = None
        detail = message if isinstance(message, str) else "GitHub request failed"
        raise GitHubApiError(response.status_code, detail)