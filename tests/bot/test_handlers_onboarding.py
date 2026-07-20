"""Tests for jyry.bot.handlers.onboarding — happy path + back steps."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from telegram.ext import ConversationHandler

from jyry.bot import messages, repos
from jyry.bot.handlers import onboarding as ob
from jyry.bot.states import OnboardingState
from jyry.db.models import User, UserSpecialty, UserState

# --- Helpers ---

def _make_callback_update(tg_id: int = 1, data: str = "") -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = tg_id
    update.callback_query = MagicMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.edit_message_reply_markup = AsyncMock()
    update.callback_query.data = data
    return update


def _make_message_update(tg_id: int = 1, text: str = "") -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = tg_id
    update.message = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.delete = AsyncMock()
    update.message.document = None
    return update


def _make_doc_update(
    tg_id: int = 1,
    filename: str = "cv.pdf",
    file_id: str = "F1",
    mime: str = "application/pdf",
    size: int = 10000,
) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = tg_id
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    doc = MagicMock()
    doc.file_name = filename
    doc.file_id = file_id
    doc.mime_type = mime
    doc.file_size = size
    update.message.document = doc
    return update


def _make_context(session, user_data: dict | None = None) -> MagicMock:
    @asynccontextmanager
    async def _scope():
        yield session

    ctx = MagicMock()
    ctx.bot_data = {"session_scope": _scope, "scheduler": None}
    ctx.user_data = user_data if user_data is not None else {}
    return ctx


async def _create_user(session, tg_id: int) -> User:
    user = await repos.get_or_create_user(session, telegram_id=tg_id)
    await session.flush()
    return user


# --- enter_onboarding ---

@pytest.mark.asyncio
async def test_enter_onboarding_shows_ask_name_and_returns_state(db_session):
    update = _make_callback_update(tg_id=100)
    ctx = _make_context(db_session)

    result = await ob.enter_onboarding(update, ctx)

    assert result == OnboardingState.ASK_NAME
    update.callback_query.edit_message_text.assert_awaited_once()
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.ASK_NAME
    assert "user_id" in ctx.user_data


# --- handle_name ---

@pytest.mark.asyncio
async def test_forward_from_name_alerts_when_field_empty(db_session):
    user = await _create_user(db_session, 901)
    # Fresh user: full_name is None — Weiter must NOT advance.
    update = _make_callback_update(tg_id=901)
    ctx = _make_context(db_session, {"user_id": user.id})

    result = await ob.forward_from_name(update, ctx)

    assert result == OnboardingState.ASK_NAME
    update.callback_query.answer.assert_awaited_once()
    args, kwargs = update.callback_query.answer.call_args
    assert args[0] == messages.FORWARD_FIELD_EMPTY
    assert kwargs.get("show_alert") is True
    update.callback_query.edit_message_text.assert_not_called()


async def test_forward_from_name_skips_when_field_set(db_session):
    user = await _create_user(db_session, 902)
    user.full_name = "Hadi Saleh"
    await db_session.flush()

    update = _make_callback_update(tg_id=902)
    ctx = _make_context(db_session, {"user_id": user.id})

    result = await ob.forward_from_name(update, ctx)

    assert result == OnboardingState.ASK_GMAIL_CONSENT
    update.callback_query.edit_message_text.assert_awaited_once()


async def test_handle_name_saves_and_shows_consent(db_session):
    user = await _create_user(db_session, 101)
    update = _make_message_update(tg_id=101, text="  Max Müller  ")
    ctx = _make_context(db_session, {"user_id": user.id})

    result = await ob.handle_name(update, ctx)

    assert result == OnboardingState.ASK_GMAIL_CONSENT
    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args[0][0]
    assert text == messages.CONSENT_WARNING

    refreshed = (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refreshed.full_name == "Max Müller"


# --- back_from_name ---

@pytest.mark.asyncio
async def test_back_from_name_returns_end(db_session):
    update = _make_callback_update(tg_id=102)
    ctx = _make_context(db_session)

    result = await ob.back_from_name(update, ctx)

    assert result == ConversationHandler.END
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.WELCOME


# --- consent accept / decline ---

@pytest.mark.asyncio
async def test_handle_consent_accept_shows_gmail_prompt(db_session):
    update = _make_callback_update(tg_id=103)
    ctx = _make_context(db_session)

    result = await ob.handle_consent_accept(update, ctx)

    assert result == OnboardingState.ASK_GMAIL_ADDRESS
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.ASK_GMAIL_ADDRESS


@pytest.mark.asyncio
async def test_handle_consent_decline_returns_end(db_session):
    update = _make_callback_update(tg_id=104)
    ctx = _make_context(db_session)

    result = await ob.handle_consent_decline(update, ctx)

    assert result == ConversationHandler.END
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.WELCOME


@pytest.mark.asyncio
async def test_back_from_consent_shows_ask_name(db_session):
    update = _make_callback_update(tg_id=105)
    ctx = _make_context(db_session)

    result = await ob.back_from_consent(update, ctx)

    assert result == OnboardingState.ASK_NAME
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.ASK_NAME


# --- handle_gmail_address ---

@pytest.mark.asyncio
async def test_handle_gmail_address_valid_advances(db_session):
    update = _make_message_update(tg_id=110, text="user@gmail.com")
    ctx = _make_context(db_session)

    result = await ob.handle_gmail_address(update, ctx)

    assert result == OnboardingState.ASK_APP_PASSWORD
    assert ctx.user_data["pending_gmail"] == "user@gmail.com"
    text = update.message.reply_text.call_args[0][0]
    assert text == messages.APP_PASSWORD_INSTRUCTIONS


@pytest.mark.asyncio
async def test_handle_gmail_address_invalid_stays(db_session):
    update = _make_message_update(tg_id=111, text="notanemail")
    ctx = _make_context(db_session)

    result = await ob.handle_gmail_address(update, ctx)

    assert result == OnboardingState.ASK_GMAIL_ADDRESS
    text = update.message.reply_text.call_args[0][0]
    assert text == messages.INVALID_EMAIL


# --- handle_app_password ---

@pytest.mark.asyncio
async def test_handle_app_password_valid_saves_and_advances(db_session):
    user = await _create_user(db_session, 120)
    update = _make_message_update(tg_id=120, text="abcd efgh ijkl mnop")
    ctx = _make_context(db_session, {
        "user_id": user.id,
        "pending_gmail": "user@gmail.com",
    })

    result = await ob.handle_app_password(update, ctx)

    assert result == OnboardingState.ASK_SPECIALTIES
    update.message.delete.assert_awaited_once()
    text = update.message.reply_text.call_args[0][0]
    assert messages.APP_PASSWORD_SAVED in text

    refreshed = (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refreshed.gmail_address == "user@gmail.com"
    assert refreshed.gmail_app_password_enc is not None


@pytest.mark.asyncio
async def test_handle_app_password_too_short_rejected(db_session):
    user = await _create_user(db_session, 121)
    update = _make_message_update(tg_id=121, text="short")
    ctx = _make_context(db_session, {"user_id": user.id, "pending_gmail": "x@y.com"})

    result = await ob.handle_app_password(update, ctx)

    assert result == OnboardingState.ASK_APP_PASSWORD
    update.message.delete.assert_awaited_once()
    text = update.message.reply_text.call_args[0][0]
    assert text == messages.APP_PASSWORD_INVALID_LENGTH


@pytest.mark.asyncio
async def test_handle_app_password_too_long_rejected(db_session):
    user = await _create_user(db_session, 122)
    update = _make_message_update(
        tg_id=122, text="abcdefghijklmnopqrstuvwxyz"  # 26 chars
    )
    ctx = _make_context(
        db_session, {"user_id": user.id, "pending_gmail": "x@y.com"}
    )

    result = await ob.handle_app_password(update, ctx)

    assert result == OnboardingState.ASK_APP_PASSWORD
    update.message.delete.assert_awaited_once()
    text = update.message.reply_text.call_args[0][0]
    assert text == messages.APP_PASSWORD_INVALID_LENGTH


@pytest.mark.asyncio
async def test_handle_app_password_accepts_16_with_spaces(db_session):
    user = await _create_user(db_session, 123)
    # Google sometimes displays the 16-char password chunked as
    # "abcd efgh ijkl mnop" — spaces must be stripped before length check.
    update = _make_message_update(tg_id=123, text="abcd efgh ijkl mnop")
    ctx = _make_context(
        db_session, {"user_id": user.id, "pending_gmail": "x@y.com"}
    )

    result = await ob.handle_app_password(update, ctx)

    assert result == OnboardingState.ASK_SPECIALTIES


# --- specialty toggles ---

@pytest.mark.asyncio
async def test_handle_specialty_toggle_adds_and_removes(db_session):
    update = _make_callback_update(tg_id=130, data="cb:sp:Bäcker")
    ctx = _make_context(db_session, {"user_id": 1, "pending_specialties": set()})

    result = await ob.handle_specialty_toggle(update, ctx)

    assert result == OnboardingState.ASK_SPECIALTIES
    assert "Bäcker" in ctx.user_data["pending_specialties"]

    # Toggle again → remove
    result2 = await ob.handle_specialty_toggle(update, ctx)
    assert result2 == OnboardingState.ASK_SPECIALTIES
    assert "Bäcker" not in ctx.user_data["pending_specialties"]


@pytest.mark.asyncio
async def test_handle_specialties_done_saves_and_advances(db_session):
    user = await _create_user(db_session, 131)
    update = _make_callback_update(tg_id=131)
    ctx = _make_context(db_session, {
        "user_id": user.id,
        "pending_specialties": {"Bäcker", "Koch"},
    })

    result = await ob.handle_specialties_done(update, ctx)

    assert result == OnboardingState.ASK_STATES
    rows = (
        await db_session.execute(
            select(UserSpecialty.specialty_keyword).where(UserSpecialty.user_id == user.id)
        )
    ).scalars().all()
    assert set(rows) == {"Bäcker", "Koch"}


@pytest.mark.asyncio
async def test_handle_specialties_done_empty_stays(db_session):
    update = _make_callback_update(tg_id=132)
    ctx = _make_context(db_session, {"user_id": 1, "pending_specialties": set()})

    result = await ob.handle_specialties_done(update, ctx)

    assert result == OnboardingState.ASK_SPECIALTIES
    # Answer was called with alert
    assert update.callback_query.answer.call_args[1].get("show_alert") is True


# --- state toggles ---

@pytest.mark.asyncio
async def test_handle_states_done_saves_and_advances(db_session):
    user = await _create_user(db_session, 140)
    update = _make_callback_update(tg_id=140)
    ctx = _make_context(db_session, {
        "user_id": user.id,
        "pending_states": {"BY", "NW"},
    })

    result = await ob.handle_states_done(update, ctx)

    assert result == OnboardingState.ASK_EMAIL_SUBJECT
    rows = (
        await db_session.execute(
            select(UserState.state_code).where(UserState.user_id == user.id)
        )
    ).scalars().all()
    assert set(rows) == {"BY", "NW"}


# --- email subject ---

@pytest.mark.asyncio
async def test_handle_email_subject_saves_and_advances(db_session):
    from jyry.db.models import EmailDraft

    user = await _create_user(db_session, 145)
    update = _make_message_update(
        tg_id=145, text="Bewerbung um eine Ausbildung bei {company}"
    )
    ctx = _make_context(db_session, {"user_id": user.id})

    result = await ob.handle_email_subject(update, ctx)

    assert result == OnboardingState.ASK_EMAIL_BODY
    draft = (
        await db_session.execute(
            select(EmailDraft).where(EmailDraft.user_id == user.id)
        )
    ).scalar_one()
    assert draft.subject_template == "Bewerbung um eine Ausbildung bei {company}"
    text = update.message.reply_text.call_args[0][0]
    assert text == messages.ASK_EMAIL_BODY


# --- email body ---

@pytest.mark.asyncio
async def test_handle_email_body_saves_and_shows_attachments(db_session):
    user = await _create_user(db_session, 150)
    update = _make_message_update(tg_id=150, text="Sehr geehrte Damen und Herren…")
    ctx = _make_context(db_session, {"user_id": user.id})

    result = await ob.handle_email_body(update, ctx)

    assert result == OnboardingState.ASK_ATTACHMENTS
    text = update.message.reply_text.call_args[0][0]
    assert text == messages.ASK_ATTACHMENTS


# --- attachments ---

@pytest.mark.asyncio
async def test_handle_attachment_saves_pdf(db_session):
    user = await _create_user(db_session, 160)
    update = _make_doc_update(tg_id=160, filename="cv.pdf", file_id="F1", size=5000)
    ctx = _make_context(db_session, {"user_id": user.id})

    result = await ob.handle_attachment(update, ctx)

    assert result == OnboardingState.ASK_ATTACHMENTS
    text = update.message.reply_text.call_args[0][0]
    assert "cv.pdf" in text


@pytest.mark.asyncio
async def test_handle_attachment_rejects_non_pdf(db_session):
    user = await _create_user(db_session, 161)
    update = _make_doc_update(tg_id=161, mime="image/jpeg")
    ctx = _make_context(db_session, {"user_id": user.id})

    result = await ob.handle_attachment(update, ctx)

    assert result == OnboardingState.ASK_ATTACHMENTS
    text = update.message.reply_text.call_args[0][0]
    assert text == messages.ATTACHMENT_REJECTED_TYPE


@pytest.mark.asyncio
async def test_handle_attachments_done_no_attachments_stays(db_session):
    user = await _create_user(db_session, 162)
    update = _make_callback_update(tg_id=162)
    ctx = _make_context(db_session, {"user_id": user.id})

    result = await ob.handle_attachments_done(update, ctx)

    assert result == OnboardingState.ASK_ATTACHMENTS
    assert update.callback_query.answer.call_args[1].get("show_alert") is True


@pytest.mark.asyncio
async def test_handle_attachments_done_with_attachment_advances(db_session):
    user = await _create_user(db_session, 163)
    await repos.append_attachment(
        db_session, user.id,
        filename="cv.pdf", file_id="F1", mime="application/pdf", size=1000
    )
    update = _make_callback_update(tg_id=163)
    ctx = _make_context(db_session, {"user_id": user.id})

    result = await ob.handle_attachments_done(update, ctx)

    assert result == OnboardingState.ASK_CONTACT_DETAILS
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.ASK_CONTACT_DETAILS


# --- confirm ---

@pytest.mark.asyncio
async def test_handle_confirm_marks_onboarded_and_returns_end(db_session):
    user = await _create_user(db_session, 170)
    update = _make_callback_update(tg_id=170)
    ctx = _make_context(db_session, {"user_id": user.id})

    result = await ob.handle_confirm(update, ctx)

    assert result == ConversationHandler.END
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.ONBOARDING_DONE

    refreshed = (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refreshed.onboarding_complete is True


@pytest.mark.asyncio
async def test_handle_confirm_calls_scheduler_activate(db_session):
    user = await _create_user(db_session, 171)
    update = _make_callback_update(tg_id=171)

    scheduler = MagicMock()
    scheduler.activate_user = AsyncMock()

    @asynccontextmanager
    async def _scope():
        yield db_session

    ctx = MagicMock()
    ctx.bot_data = {"session_scope": _scope, "scheduler": scheduler}
    ctx.user_data = {"user_id": user.id}

    await ob.handle_confirm(update, ctx)

    scheduler.activate_user.assert_awaited_once_with(user.id)


# --- back navigation ---

@pytest.mark.asyncio
async def test_back_from_app_password_shows_gmail_address(db_session):
    update = _make_callback_update(tg_id=180)
    ctx = _make_context(db_session)

    result = await ob.back_from_app_password(update, ctx)

    assert result == OnboardingState.ASK_GMAIL_ADDRESS
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.ASK_GMAIL_ADDRESS


@pytest.mark.asyncio
async def test_back_from_specialties_shows_app_password_instructions(db_session):
    update = _make_callback_update(tg_id=181)
    ctx = _make_context(db_session)

    result = await ob.back_from_specialties(update, ctx)

    assert result == OnboardingState.ASK_APP_PASSWORD
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.APP_PASSWORD_INSTRUCTIONS


@pytest.mark.asyncio
async def test_back_from_states_shows_specialties_keyboard(db_session):
    update = _make_callback_update(tg_id=182)
    ctx = _make_context(db_session, {"pending_specialties": {"Bäcker"}})

    result = await ob.back_from_states(update, ctx)

    assert result == OnboardingState.ASK_SPECIALTIES


@pytest.mark.asyncio
async def test_back_from_confirm_shows_contact_details(db_session):
    update = _make_callback_update(tg_id=183)
    ctx = _make_context(db_session, {"user_id": 1})

    result = await ob.back_from_confirm(update, ctx)

    assert result == OnboardingState.ASK_CONTACT_DETAILS
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.ASK_CONTACT_DETAILS


# --- contact details (optional Anschreiben letterhead) ---


@pytest.mark.asyncio
async def test_handle_contact_details_saves_and_advances(db_session):
    user = await _create_user(db_session, 190)
    update = _make_message_update(
        tg_id=190, text="Musterstraße 12\n80331 München\n+49 151 23456789"
    )
    ctx = _make_context(db_session, {"user_id": user.id})

    result = await ob.handle_contact_details(update, ctx)

    assert result == OnboardingState.CONFIRM
    text = update.message.reply_text.call_args[0][0]
    assert messages.CONFIRM_PROMPT in text

    refreshed = (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refreshed.postal_street == "Musterstraße 12"
    assert refreshed.postal_plz_city == "80331 München"
    assert refreshed.phone == "+49 151 23456789"


@pytest.mark.asyncio
async def test_handle_contact_details_partial_input(db_session):
    user = await _create_user(db_session, 191)
    update = _make_message_update(tg_id=191, text="Musterstraße 12")
    ctx = _make_context(db_session, {"user_id": user.id})

    result = await ob.handle_contact_details(update, ctx)

    assert result == OnboardingState.CONFIRM
    refreshed = (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refreshed.postal_street == "Musterstraße 12"
    assert refreshed.postal_plz_city is None
    assert refreshed.phone is None


@pytest.mark.asyncio
async def test_handle_contact_skip_advances_without_saving(db_session):
    user = await _create_user(db_session, 192)
    update = _make_callback_update(tg_id=192)
    ctx = _make_context(db_session, {"user_id": user.id})

    result = await ob.handle_contact_skip(update, ctx)

    assert result == OnboardingState.CONFIRM
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.CONFIRM_PROMPT

    refreshed = (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refreshed.postal_street is None


@pytest.mark.asyncio
async def test_back_from_contact_shows_attachments(db_session):
    user = await _create_user(db_session, 193)
    await repos.append_attachment(
        db_session, user.id,
        filename="cv.pdf", file_id="F1", mime="application/pdf", size=1000
    )
    update = _make_callback_update(tg_id=193)
    ctx = _make_context(db_session, {"user_id": user.id})

    result = await ob.back_from_contact(update, ctx)

    assert result == OnboardingState.ASK_ATTACHMENTS
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.ASK_ATTACHMENTS
