from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DATABASE_URL = f"sqlite:///{_BACKEND_ROOT / 'provenyx.db'}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROVENYX_",
        env_file=_BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Shared access key (X-Provenyx-Key header). Unset = no check: only for a trusted local machine.
    api_key: SecretStr | None = None
    # Scan and trust-gate submissions per client address per minute; 0 disables the limit.
    submission_rate_limit_per_minute: int = 30
    max_scan_bytes: int = 10 * 1024 * 1024
    database_url: str = _DEFAULT_DATABASE_URL
    npm_registry_url: str = "https://registry.npmjs.org"
    npm_registry_concurrency: int = 10
    npm_registry_timeout_seconds: float = 5.0
    npm_registry_retries: int = 2
    osv_api_url: str = "https://api.osv.dev"
    osv_concurrency: int = 10
    osv_timeout_seconds: float = 5.0
    osv_retries: int = 2
    ai_ranking_enabled: bool = False
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com"
    gemini_timeout_seconds: float = 10.0
    github_client_id: str | None = None
    github_client_secret: SecretStr | None = None
    github_session_secret: SecretStr | None = None
    github_api_url: str = "https://api.github.com"
    github_oauth_url: str = "https://github.com/login/oauth"
    # Where GitHub sign-in returns to. Setting only this is enough in production: the callback URL,
    # CORS origin and secure cookies below follow from it unless set explicitly.
    frontend_url: str = "http://localhost:3000"
    github_callback_url: str | None = None
    secure_cookies: bool | None = None
    # Release registry (Phase 6): local Hardhat chain only. Read-only; no keys are needed.
    registry_rpc_url: str = "http://127.0.0.1:8545"
    registry_deployment_file: str = str(_REPO_ROOT / "contracts" / "deployments" / "localhost.json")
    registry_address: str | None = None
    registry_timeout_seconds: float = 3.0

    @field_validator("database_url", mode="before")
    @classmethod
    def resolve_relative_sqlite_url(cls, value: object) -> object:
        prefix = "sqlite:///./"
        if isinstance(value, str) and value.startswith(prefix):
            return f"sqlite:///{(_BACKEND_ROOT / value.removeprefix(prefix)).resolve()}"
        return value

    @field_validator("registry_deployment_file", mode="before")
    @classmethod
    def resolve_registry_deployment_file(cls, value: object) -> object:
        if isinstance(value, str) and value and not Path(value).is_absolute():
            return str((_BACKEND_ROOT / value).resolve())
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        frontend = self.frontend_url.rstrip("/")
        return origins if frontend in origins else [*origins, frontend]

    @property
    def deployed(self) -> bool:
        """An HTTPS dashboard means a real deployment, which proxies the API through its own origin."""
        return self.frontend_url.startswith("https://")

    @property
    def github_callback(self) -> str:
        if self.github_callback_url:
            return self.github_callback_url
        # Deployed, the callback goes through the dashboard's /api proxy so the session cookie is first-party.
        if self.deployed:
            return f"{self.frontend_url.rstrip('/')}/api/github/auth/callback"
        return "http://localhost:8000/api/github/auth/callback"

    @property
    def cookies_secure(self) -> bool:
        return self.deployed if self.secure_cookies is None else self.secure_cookies

    @property
    def github_auth_configured(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret and self.github_session_secret)


settings = Settings()
