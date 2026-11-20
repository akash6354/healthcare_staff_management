"""Application settings, loaded from environment variables (never from code)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "development"
    app_base_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"

    database_url: str
    migrations_database_url: str
    platform_database_url: str
    test_database_name: str = "oglos_test"
    redis_url: str = "redis://localhost:6379/0"

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

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
