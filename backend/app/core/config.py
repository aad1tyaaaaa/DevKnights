from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROVENYX_", env_file=".env", extra="ignore")

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    max_scan_bytes: int = 10 * 1024 * 1024
    database_url: str = "sqlite:///./provenyx.db"
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
    github_callback_url: str = "http://localhost:8000/api/github/auth/callback"
    frontend_url: str = "http://localhost:3000"
    secure_cookies: bool = False
    # Release registry (Phase 6): local Hardhat chain only. Read-only; no keys are needed.
    registry_rpc_url: str = "http://127.0.0.1:8545"
    registry_deployment_file: str = str(_REPO_ROOT / "contracts" / "deployments" / "localhost.json")
    registry_address: str | None = None
    registry_timeout_seconds: float = 3.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def github_auth_configured(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret and self.github_session_secret)


settings = Settings()
