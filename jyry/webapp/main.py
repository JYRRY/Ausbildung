"""FastAPI application for the bot.jyrygroup.com dashboard.

Runs behind nginx on 127.0.0.1:WEB_API_PORT. Static marketing pages
(/, /pricing, ...) are still served by nginx from /var/www/jyry; the
Next.js dashboard lives on /app and talks to this API at /api/*.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jyry.config import get_settings
from jyry.webapp.routes import admin, applications, auth, checkout, me, profile

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.web_jwt_secret is None:
        raise RuntimeError(
            "WEB_JWT_SECRET is required to run the dashboard API. "
            "Generate one with: openssl rand -base64 48"
        )
    app = FastAPI(
        title="JYRY AI Dashboard API",
        docs_url="/api/docs" if settings.env != "production" else None,
        redoc_url=None,
    )

    # Same-origin in prod (nginx proxies /api/* on the same host). In dev the
    # Next.js dev server on :3000 needs explicit allow.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.web_public_url.rstrip("/"),
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(applications.router)
    app.include_router(profile.router)
    app.include_router(checkout.router)
    app.include_router(admin.router)

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True}

    return app


app = create_app()


def main() -> None:
    """Entry point referenced by deploy/systemd/jyry-api.service."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "jyry.webapp.main:app",
        host=settings.web_api_host,
        port=settings.web_api_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
