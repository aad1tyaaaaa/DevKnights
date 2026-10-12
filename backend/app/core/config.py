from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROVENYX_", env_file=".env", extra="ignore")

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    max_scan_bytes: int = 10 * 1024 * 1024
    database_url: str = "sqlite:///./provenyx.db"
    npm_registry_url: str = "https://registry.npmjs.org"
    npm_registry_concurrency: int = 10
    npm_registry_timeout_seconds: float = 5.0
    npm_registry_retries: int = 2

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
