"""Admin-only utilities — plan switcher for testing different tiers."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from jyry.bot import keyboards, messages, repos
from jyry.config import get_settings

logger = logging.getLogger(__name__)

_ADMIN_PLAN_CB = "cb:admin:plan:"  # cb:admin:plan:<free|plus|pro|max>


def _is_admin(tg_id: int) -> bool:
    return tg_id in get_settings().telegram_admin_ids


def _admin_keyboard(current_plan: str) -> InlineKeyboardMarkup:
    plans = ["free", "plus", "pro", "max"]
    rows = []
    for plan in plans:
        label = plan.upper()
        if plan == current_plan:
            label = f"✅ {label} (aktiv)"
        rows.append(
            [InlineKeyboardButton(label, callback_data=_ADMIN_PLAN_CB + plan)]
        )
    rows.append(
        [
            InlineKeyboardButton(
                messages.MENU_LABEL, callback_data=keyboards.CB["menu_back_to_main"]
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user is not None and update.message is not None
    tg_id = update.effective_user.id
    if not _is_admin(tg_id):
        return  # silently ignore for non-admins
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)
    current = repos.plan_value(full) if full else "free"
    await update.message.reply_text(
        f"🛠 *Admin-Panel*\n\nAktueller Tarif: *{current.upper()}*\n\n"
        f"Wähle einen Tarif, um ihn ohne Bezahlung zu aktivieren (nur für Tests):",
        reply_markup=_admin_keyboard(current),
        parse_mode="Markdown",
    )


async def cb_admin_set_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None and query.data is not None and update.effective_user is not None
    tg_id = update.effective_user.id
    if not _is_admin(tg_id):
        await query.answer("Nur für Admins.", show_alert=True)
        return
    await query.answer()
    new_plan = query.data[len(_ADMIN_PLAN_CB):]
    if new_plan not in {"free", "plus", "pro", "max"}:
        return
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        await repos.admin_set_plan(session, user.id, new_plan)
        full = await repos.load_user(session, user.id)
    current = repos.plan_value(full) if full else new_plan
    logger.info("Admin %s switched plan -> %s", tg_id, new_plan)
    await query.edit_message_text(
        f"🛠 *Admin-Panel*\n\nTarif gewechselt zu: *{new_plan.upper()}* ✅\n\n"
        f"Aktueller Tarif: *{current.upper()}*",
        reply_markup=_admin_keyboard(current),
        parse_mode="Markdown",
    )


ADMIN_PLAN_PATTERN = f"^{_ADMIN_PLAN_CB}"
