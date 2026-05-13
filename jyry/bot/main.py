"""Telegram bot entry point — wires all handlers into a PTB Application.

Called via the ``jyry-bot`` console script defined in pyproject.toml.
"""
from __future__ import annotations

import asyncio
import logging

import redis.asyncio as redis_asyncio
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from jyry.bot import channel_gate
from jyry.bot.handlers import control, edit, onboarding, plans, start
from jyry.bot.keyboards import CB
from jyry.bot.states import OnboardingState
from jyry.config import get_settings
from jyry.db.session import async_session_factory, dispose_engine, session_scope
from jyry.jobs.dispatch_tick import TickDeps
from jyry.jobs.renewal_reminder import run_renewal_reminder
from jyry.services.bundesagentur import BundesagenturClient
from jyry.services.rate_limiter import DailyQuotaLimiter
from jyry.services.scheduler import JyryScheduler

logger = logging.getLogger(__name__)

S = OnboardingState


def _build_conversation_handler() -> ConversationHandler:  # type: ignore[type-arg]
    """Return the ConversationHandler covering onboarding + edit re-entry."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start.cb_loslegen, pattern=f"^{CB['menu_start']}$"),
            CallbackQueryHandler(plans.cb_plan_free, pattern=f"^{CB['plan_free']}$"),
            CallbackQueryHandler(edit.cb_edit_body, pattern=f"^{CB['menu_edit_body']}$"),
            CallbackQueryHandler(
                edit.cb_edit_attachments, pattern=f"^{CB['menu_edit_attachments']}$"
            ),
            CallbackQueryHandler(
                edit.cb_edit_specialties, pattern=f"^{CB['menu_edit_specialties']}$"
            ),
            CallbackQueryHandler(
                edit.cb_edit_states, pattern=f"^{CB['menu_edit_states']}$"
            ),
        ],
        states={
            S.ASK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding.handle_name),
                CallbackQueryHandler(onboarding.back_from_name, pattern=f"^{CB['back']}$"),
            ],
            S.ASK_GMAIL_CONSENT: [
                CallbackQueryHandler(
                    onboarding.handle_consent_accept, pattern=f"^{CB['consent_accept']}$"
                ),
                CallbackQueryHandler(
                    onboarding.handle_consent_decline, pattern=f"^{CB['consent_decline']}$"
                ),
                CallbackQueryHandler(
                    onboarding.back_from_consent, pattern=f"^{CB['back']}$"
                ),
            ],
            S.ASK_GMAIL_ADDRESS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, onboarding.handle_gmail_address
                ),
                CallbackQueryHandler(
                    onboarding.back_from_gmail_address, pattern=f"^{CB['back']}$"
                ),
            ],
            S.ASK_APP_PASSWORD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, onboarding.handle_app_password
                ),
                CallbackQueryHandler(
                    onboarding.back_from_app_password, pattern=f"^{CB['back']}$"
                ),
            ],
            S.ASK_SPECIALTIES: [
                CallbackQueryHandler(
                    onboarding.handle_specialty_toggle,
                    pattern=f"^{CB['specialty_toggle_prefix']}",
                ),
                CallbackQueryHandler(
                    onboarding.handle_specialties_done, pattern=f"^{CB['specialties_done']}$"
                ),
                CallbackQueryHandler(
                    onboarding.back_from_specialties, pattern=f"^{CB['back']}$"
                ),
            ],
            S.ASK_STATES: [
                CallbackQueryHandler(
                    onboarding.handle_state_toggle, pattern=f"^{CB['state_toggle_prefix']}"
                ),
                CallbackQueryHandler(
                    onboarding.handle_states_done, pattern=f"^{CB['states_done']}$"
                ),
                CallbackQueryHandler(onboarding.back_from_states, pattern=f"^{CB['back']}$"),
            ],
            S.ASK_EMAIL_BODY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, onboarding.handle_email_body
                ),
                CallbackQueryHandler(
                    onboarding.back_from_email_body, pattern=f"^{CB['back']}$"
                ),
            ],
            S.ASK_ATTACHMENTS: [
                MessageHandler(filters.Document.PDF, onboarding.handle_attachment),
                CallbackQueryHandler(
                    onboarding.handle_attachment_remove,
                    pattern=f"^{CB['attachment_remove_prefix']}",
                ),
                CallbackQueryHandler(
                    onboarding.handle_attachments_done, pattern=f"^{CB['done']}$"
                ),
                CallbackQueryHandler(
                    onboarding.back_from_attachments, pattern=f"^{CB['back']}$"
                ),
            ],
            S.CONFIRM: [
                CallbackQueryHandler(
                    onboarding.handle_confirm, pattern=f"^{CB['confirm']}$"
                ),
                CallbackQueryHandler(
                    onboarding.back_from_confirm, pattern=f"^{CB['back']}$"
                ),
            ],
        },
        fallbacks=[
            CommandHandler("start", start.cmd_start),
        ],
        per_user=True,
        per_chat=True,
    )


def _register_handlers(app: Application) -> None:  # type: ignore[type-arg]
    # Channel-subscription gate runs before everything else (group=-1).
    app.add_handler(TypeHandler(Update, channel_gate.gate), group=-1)
    app.add_handler(
        CallbackQueryHandler(
            channel_gate.cb_channel_check, pattern=f"^{CB['channel_check']}$"
        )
    )

    conv = _build_conversation_handler()
    app.add_handler(conv)

    app.add_handler(CommandHandler("start", start.cmd_start))
    app.add_handler(CallbackQueryHandler(start.cb_about, pattern=f"^{CB['menu_about']}$"))
    app.add_handler(CallbackQueryHandler(start.cb_plans, pattern=f"^{CB['menu_plans']}$"))
    app.add_handler(
        CallbackQueryHandler(start.cb_back_to_main, pattern=f"^{CB['menu_back_to_main']}$")
    )
    app.add_handler(
        CallbackQueryHandler(plans.cb_plan_paid, pattern=f"^{CB['plan_plus']}$")
    )
    app.add_handler(
        CallbackQueryHandler(plans.cb_plan_paid, pattern=f"^{CB['plan_pro']}$")
    )
    app.add_handler(
        CallbackQueryHandler(plans.cb_plan_paid, pattern=f"^{CB['plan_max']}$")
    )
    app.add_handler(CallbackQueryHandler(control.cb_status, pattern=f"^{CB['menu_status']}$"))
    app.add_handler(CallbackQueryHandler(control.cb_pause, pattern=f"^{CB['menu_pause']}$"))
    app.add_handler(CallbackQueryHandler(control.cb_resume, pattern=f"^{CB['menu_resume']}$"))
    app.add_handler(
        CallbackQueryHandler(start.cb_plans, pattern=f"^{CB['menu_plan']}$")
    )


def main() -> None:
    import asyncio
    asyncio.run(run())


async def run() -> None:
    logging.basicConfig(
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        level=logging.INFO,
    )
    settings = get_settings()
    redis = redis_asyncio.from_url(settings.redis_url, decode_responses=True)
    limiter = DailyQuotaLimiter(redis, settings)
    ba_client = BundesagenturClient(settings)
    factory = async_session_factory()

    app: Application = (  # type: ignore[type-arg]
        ApplicationBuilder().token(settings.telegram_bot_token.get_secret_value()).build()
    )

    from jyry.bot.attachment_fetcher import TelegramAttachmentFetcher

    fetcher = TelegramAttachmentFetcher(app.bot)

    scheduler: JyryScheduler | None = None

    def _deps_factory() -> TickDeps:
        assert scheduler is not None
        return TickDeps(
            settings=settings,
            ba_client=ba_client,
            limiter=limiter,
            fetcher=fetcher,
            session_factory=factory,
            schedule_at=scheduler.schedule_at,
            redis=redis,
        )

    scheduler = JyryScheduler(settings, _deps_factory)
    await scheduler.start()

    scheduler.add_daily_cron(
        job_id="renewal_reminder",
        func=run_renewal_reminder,
        hour=9,
        minute=0,
        kwargs={
            "token": settings.telegram_bot_token.get_secret_value(),
            "session_scope": session_scope,
        },
    )

    async with session_scope() as s:
        await scheduler.sweep_active_users(s)

    app.bot_data["session_scope"] = session_scope
    app.bot_data["limiter"] = limiter
    app.bot_data["scheduler"] = scheduler
    app.bot_data["required_channel"] = settings.telegram_required_channel

    _register_handlers(app)

    try:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)  # type: ignore[union-attr]
        logger.info("JYRY AI bot running — Ctrl-C to stop")
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()  # type: ignore[union-attr]
        await app.stop()
        await app.shutdown()
        await scheduler.stop()
        await redis.close()
        await dispose_engine()
