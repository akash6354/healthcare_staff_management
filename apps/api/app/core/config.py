"""Application settings, loaded from environment variables (never from code)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    """The repo's .env in local development; containers get real environment variables instead."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(), env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "development"
    app_base_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"
    # Set to ".oglos.site" when the apps and the API are on different subdomains (Render), so the
    # refresh and CSRF cookies are shared across app./ops./api. Leave empty for same-origin setups.
    cookie_domain: str | None = None

    database_url: str
    migrations_database_url: str
    platform_database_url: str
    test_database_name: str = "oglos_test"
    redis_url: str = "redis://localhost:6379/0"

    storage_backend: str = "s3"  # "s3" | "db" (free-tier prototype only)
    web_dist_dir: str | None = (
        None  # serve the built web apps from the API (single-service deploys)
    )
    s3_endpoint_url: str | None = None
    s3_bucket: str = "oglos-evidence"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "ap-south-1"

    jwt_signing_key: str = Field(min_length=16)
    access_token_minutes: int = Field(default=15, le=15)
    refresh_token_days: int = 30
    refresh_token_absolute_days: int = 90

    field_encryption_keys: str  # "v1:<b64>,v2:<b64>"
    field_encryption_active_key: str = "v1"
    hmac_lookup_key: str = Field(min_length=16)
    qr_signing_keys: str
    otp_hmac_key: str = Field(min_length=16)

    email_provider: str = "console"
    email_from: str = "OGLOS <no-reply@oglos.site>"
    aws_ses_region: str = "ap-south-1"
    breached_password_check: str = "off"  # noqa: S105 - a mode flag, not a secret

    @field_validator("database_url", "migrations_database_url", "platform_database_url")
    @classmethod
    def _asyncpg_url(cls, v: str) -> str:
        """Accept provider URLs (postgres://...?sslmode=require) and convert them for asyncpg."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                v = "postgresql+asyncpg://" + v[len(prefix) :]
        if "sslmode=" in v:
            base, _, query = v.partition("?")
            params = [p for p in query.split("&") if p and not p.startswith("sslmode=")]
            ssl = "require" in query or "verify" in query
            params += ["ssl=require"] if ssl else []
            v = base + ("?" + "&".join(params) if params else "")
        return v

    @field_validator("cookie_domain")
    @classmethod
    def _empty_none(cls, v: str | None) -> str | None:
        return v or None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
