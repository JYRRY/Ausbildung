"""Centralised settings loaded from environment / .env via pydantic-settings."""

from __future__ import annotations

from datetime import time
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_hhmm(value: str) -> time:
    hh, mm = value.split(":", 1)
    return time(hour=int(hh), minute=int(mm))


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
    send_window_start: time = Field(default=time(8, 0), alias="SEND_WINDOW_START")
    send_window_end: time = Field(default=time(22, 0), alias="SEND_WINDOW_END")
    send_jitter_minutes: int = Field(default=15, alias="SEND_JITTER_MINUTES")
    send_batch_global_rps: float = Field(default=2.0, alias="SEND_BATCH_GLOBAL_RPS")

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

    @field_validator("send_window_start", "send_window_end", mode="before")
    @classmethod
    def _coerce_window_time(cls, value: object) -> time:
        if isinstance(value, time):
            return value
        return _parse_hhmm(str(value))

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
