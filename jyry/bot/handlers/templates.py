"""Pro/Max-gated template browser — pick a prepared Bewerbungstext."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from jyry.bewerbung_templates import TEMPLATES, template_for
from jyry.bot import keyboards, messages, repos


async def cb_browse_templates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the list of prepared templates filtered by the user's specialties."""
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)

    if not full or not repos.can_use_templates(full):
        await query.edit_message_text(
            messages.TEMPLATES_NEED_PRO,
            reply_markup=keyboards.back_to_main_only(),
            parse_mode="Markdown",
        )
        return

    picked = [s.specialty_keyword for s in full.specialties]
    available = [kw for kw in picked if kw in TEMPLATES] or list(TEMPLATES.keys())

    if not picked:
        # No specialties yet — still let them browse the full catalogue.
        available = list(TEMPLATES.keys())

    await query.edit_message_text(
        messages.TEMPLATES_TITLE,
        reply_markup=keyboards.templates_list_keyboard(available),
        parse_mode="Markdown",
    )


async def cb_template_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Render the chosen template body with Übernehmen / zurück buttons."""
    query = update.callback_query
    assert query is not None and query.data is not None
    await query.answer()
    prefix = keyboards.CB["template_pick_prefix"]
    keyword = query.data[len(prefix):]
    body = template_for(keyword)
    if body is None:
        await query.edit_message_text(
            messages.TEMPLATES_TITLE,
            reply_markup=keyboards.templates_list_keyboard(list(TEMPLATES.keys())),
            parse_mode="Markdown",
        )
        return
    await query.edit_message_text(
        messages.TEMPLATE_PREVIEW.format(keyword=keyword, body=body),
        reply_markup=keyboards.template_preview_keyboard(keyword),
        parse_mode="Markdown",
    )


async def cb_template_apply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Persist the template as the user's body_template."""
    query = update.callback_query
    assert query is not None and query.data is not None and update.effective_user is not None
    await query.answer()
    prefix = keyboards.CB["template_apply_prefix"]
    keyword = query.data[len(prefix):]
    body = template_for(keyword)
    if body is None:
        await query.edit_message_text(
            messages.TEMPLATES_TITLE,
            reply_markup=keyboards.templates_list_keyboard(list(TEMPLATES.keys())),
            parse_mode="Markdown",
        )
        return
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        # Re-check plan gating — a sub may have downgraded since the menu render.
        full = await repos.load_user(session, user.id)
        if not full or not repos.can_use_templates(full):
            await query.edit_message_text(
                messages.TEMPLATES_NEED_PRO,
                reply_markup=keyboards.back_to_main_only(),
                parse_mode="Markdown",
            )
            return
        await repos.upsert_draft(session, user.id, body_template=body)
    await query.edit_message_text(
        messages.TEMPLATE_APPLIED,
        reply_markup=keyboards.back_to_main_only(),
        parse_mode="Markdown",
    )
