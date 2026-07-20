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
    telegram_required_channel: str | None = Field(
        default=None, alias="TELEGRAM_REQUIRED_CHANNEL"
    )

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

    # Employer-website crawl (fallback when a posting carries no email). Bounded
    # and best-effort: a failure never blocks a send.
    crawl_enabled: bool = Field(default=True, alias="CRAWL_ENABLED")
    crawl_max_pages: int = Field(default=5, alias="CRAWL_MAX_PAGES")
    crawl_request_timeout_seconds: float = Field(
        default=8.0, alias="CRAWL_REQUEST_TIMEOUT_SECONDS"
    )
    crawl_total_timeout_seconds: float = Field(
        default=15.0, alias="CRAWL_TOTAL_TIMEOUT_SECONDS"
    )
    crawl_delay_seconds: float = Field(default=0.5, alias="CRAWL_DELAY_SECONDS")
    crawl_max_concurrent: int = Field(default=3, alias="CRAWL_MAX_CONCURRENT")
    crawl_max_html_bytes: int = Field(default=500_000, alias="CRAWL_MAX_HTML_BYTES")
    crawl_max_attempts_per_tick: int = Field(
        default=10, alias="CRAWL_MAX_ATTEMPTS_PER_TICK"
    )
    crawl_accept_generic_localparts: bool = Field(
        default=True, alias="CRAWL_ACCEPT_GENERIC_LOCALPARTS"
    )

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
    # Auto-generate a German Anschreiben (cover-letter) PDF per employer and
    # attach it (first) to every application. Turned off leaves the send path
    # exactly as before (only the user's uploaded attachments go out).
    anschreiben_enabled: bool = Field(default=True, alias="JYRY_ANSCHREIBEN_ENABLED")

    # Testing — when set, all outgoing emails are redirected to this address
    # instead of the actual company. The original recipient is preserved in
    # the Subject prefix: "[TEST → original@company.de] {subject}". Leave
    # empty in production.
    test_redirect_email: str | None = Field(
        default=None, alias="JYRY_TEST_REDIRECT_EMAIL"
    )

    # Web-uploaded attachments (CVs etc.) are stored on the local filesystem
    # under this directory, one sub-folder per user. The bot's dispatch process
    # reads them back at send time. Both jyry-api and jyry-bot run as the same
    # OS user, so a shared path works without extra plumbing.
    upload_dir: str = Field(default="/opt/jyry/uploads", alias="JYRY_UPLOAD_DIR")

    # Paddle (Billing API). Flip PADDLE_API_BASE to https://api.paddle.com for
    # production; the sandbox value is the safe default for local dev.
    paddle_api_base: str = Field(
        default="https://sandbox-api.paddle.com", alias="PADDLE_API_BASE"
    )
    paddle_api_key: SecretStr | None = Field(default=None, alias="PADDLE_API_KEY")
    paddle_webhook_secret: SecretStr | None = Field(
        default=None, alias="PADDLE_WEBHOOK_SECRET"
    )
    paddle_price_plus: str | None = Field(default=None, alias="PADDLE_PRICE_PLUS")
    paddle_price_pro: str | None = Field(default=None, alias="PADDLE_PRICE_PRO")
    paddle_price_max: str | None = Field(default=None, alias="PADDLE_PRICE_MAX")

    # Webhook server
    webhook_host: str = Field(default="0.0.0.0", alias="WEBHOOK_HOST")  # noqa: S104
    webhook_port: int = Field(default=8080, alias="WEBHOOK_PORT")
    webhook_public_url: str | None = Field(default=None, alias="WEBHOOK_PUBLIC_URL")

    # Web dashboard API (FastAPI on /api/*) — separate process from webhook.
    web_api_host: str = Field(default="127.0.0.1", alias="WEB_API_HOST")
    web_api_port: int = Field(default=8001, alias="WEB_API_PORT")
    # Public URL of the dashboard (used to build OAuth redirect URI + cookie domain).
    web_public_url: str = Field(
        default="https://bot.jyrygroup.com", alias="WEB_PUBLIC_URL"
    )
    # HS256 secret for the dashboard session JWT. Rotate to invalidate all
    # sessions. Optional at import time so the bot and alembic don't require
    # it; jyry.webapp.main asserts presence at startup.
    web_jwt_secret: SecretStr | None = Field(default=None, alias="WEB_JWT_SECRET")
    web_session_cookie: str = Field(
        default="jyry_session", alias="WEB_SESSION_COOKIE"
    )
    web_session_days: int = Field(default=7, alias="WEB_SESSION_DAYS")
    # Browser origins allowed to call /api/* with credentials (comma-separated).
    # A cross-origin Framer front-end (e.g. https://jyrygroup.framer.website)
    # must be listed here. Empty falls back to the same-origin + localhost dev
    # defaults. "*" is invalid with credentials — list explicit origins.
    web_cors_origins: list[str] = Field(
        default_factory=list, alias="WEB_CORS_ORIGINS"
    )
    # Session-cookie scope. ".jyrygroup.com" shares the cookie across subdomains
    # (Option A — same-site Framer). None keeps a host-only cookie (default).
    web_cookie_domain: str | None = Field(default=None, alias="WEB_COOKIE_DOMAIN")
    # Session-cookie SameSite: "lax" (same-site front-end) or "none" (cross-site;
    # requires Secure and is subject to third-party-cookie blocking).
    web_cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax", alias="WEB_COOKIE_SAMESITE"
    )
    # Where the OAuth callback lands the signed-in user. Set to the Framer app
    # URL to switch on Bearer-token delivery (the token is appended as a URL
    # fragment: "<web_app_url>#token=<jwt>"). None keeps the same-origin
    # redirect to "<web_public_url>/app" (the Next.js dashboard).
    web_app_url: str | None = Field(default=None, alias="WEB_APP_URL")

    # Google OAuth (used by the web dashboard for sign-in). Scopes are limited
    # to openid + email + profile — no Gmail access, no Google verification
    # needed. Sending still uses the user's App Password via SMTP.
    google_client_id: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: SecretStr | None = Field(
        default=None, alias="GOOGLE_CLIENT_SECRET"
    )

    @field_validator("telegram_admin_ids", mode="before")
    @classmethod
    def _split_admin_ids(cls, value: object) -> list[int]:
        if value in (None, "", []):
            return []
        if isinstance(value, list):
            return [int(v) for v in value]
        return [int(part) for part in str(value).split(",") if part.strip()]

    @field_validator("web_cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> list[str]:
        if value in (None, "", []):
            return []
        if isinstance(value, list):
            return [str(v).strip().rstrip("/") for v in value if str(v).strip()]
        return [
            part.strip().rstrip("/")
            for part in str(value).split(",")
            if part.strip()
        ]

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
