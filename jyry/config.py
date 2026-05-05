"""Centralised settings loaded from environment / .env via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    env: Literal["production", "development", "testing"] = Field(
        default="development", alias="JYRY_ENV"
    )
    log_level: str = Field(default="INFO", alias="JYRY_LOG_LEVEL")
    timezone: str = Field(default="Europe/Berlin", alias="JYRY_TIMEZONE")

    # Telegram
    telegram_bot_token: SecretStr = Field(alias="TELEGRAM_BOT_TOKEN")
    telegram_bot_username: str = Field(default="JYRY_AI_bot", alias="TELEGRAM_BOT_USERNAME")
    telegram_admin_ids: list[int] = Field(default_factory=list, alias="TELEGRAM_ADMIN_IDS")

    # Encryption
    fernet_key: SecretStr = Field(alias="FERNET_KEY")

    # Database
    database_url: str = Field(alias="DATABASE_URL")

    # Redis
    redis_url: str = Field(default="redis://127.0.0.1:6379/0", alias="REDIS_URL")

    # Bundesagentur
    ba_api_base: str = Field(
        default="https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs",
        alias="BA_API_BASE",
    )
    ba_api_key: str = Field(default="jobboerse-jobsuche", alias="BA_API_KEY")
    ba_cache_ttl_seconds: int = Field(default=86_400, alias="BA_CACHE_TTL_SECONDS")

    # Sending engine
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_starttls: bool = Field(default=True, alias="SMTP_STARTTLS")
    # Sending begins immediately on subscribe and paces the daily quota
    # across the rest of the day in JYRY_TIMEZONE. The min-interval guards
    # Gmail's spam filter; the jitter makes the cadence look human.
    send_min_interval_seconds: int = Field(default=60, alias="SEND_MIN_INTERVAL_SECONDS")
    send_jitter_seconds: int = Field(default=20, alias="SEND_JITTER_SECONDS")
    send_no_posting_backoff_seconds: int = Field(
        default=1800, alias="SEND_NO_POSTING_BACKOFF_SECONDS"
    )
    send_transient_retry_seconds: tuple[int, ...] = Field(
        default=(300, 1800, 7200), alias="SEND_TRANSIENT_RETRY_SECONDS"
    )

    # Lemon Squeezy
    lemonsqueezy_api_key: SecretStr | None = Field(default=None, alias="LEMONSQUEEZY_API_KEY")
    lemonsqueezy_store_id: str | None = Field(default=None, alias="LEMONSQUEEZY_STORE_ID")
    lemonsqueezy_webhook_secret: SecretStr | None = Field(
        default=None, alias="LEMONSQUEEZY_WEBHOOK_SECRET"
    )
    lemonsqueezy_variant_basic: str | None = Field(default=None, alias="LEMONSQUEEZY_VARIANT_BASIC")
    lemonsqueezy_variant_pro: str | None = Field(default=None, alias="LEMONSQUEEZY_VARIANT_PRO")
    lemonsqueezy_variant_max: str | None = Field(default=None, alias="LEMONSQUEEZY_VARIANT_MAX")

    # Webhook server
    webhook_host: str = Field(default="0.0.0.0", alias="WEBHOOK_HOST")  # noqa: S104
    webhook_port: int = Field(default=8080, alias="WEBHOOK_PORT")
    webhook_public_url: str | None = Field(default=None, alias="WEBHOOK_PUBLIC_URL")

    @field_validator("telegram_admin_ids", mode="before")
    @classmethod
    def _split_admin_ids(cls, value: object) -> list[int]:
        if value in (None, "", []):
            return []
        if isinstance(value, list):
            return [int(v) for v in value]
        return [int(part) for part in str(value).split(",") if part.strip()]

    @field_validator("send_transient_retry_seconds", mode="before")
    @classmethod
    def _split_retry_seconds(cls, value: object) -> tuple[int, ...]:
        if value in (None, "", []):
            return ()
        if isinstance(value, list | tuple):
            return tuple(int(v) for v in value)
        return tuple(int(part) for part in str(value).split(",") if part.strip())

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
