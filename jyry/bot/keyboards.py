"""Inline-keyboard builders for every UI state.

All callback-data strings are namespaced (``cb:<scope>:<value>``) so the
top-level callback router in :mod:`jyry.bot.handlers.start` can dispatch
without ambiguity. Long German labels are taken from
:mod:`jyry.bot.messages`.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from jyry.bot import messages
from jyry.constants import (
    SPECIALTIES,
    STATE_LABELS_DE,
    STATES,
)

CB = {
    "menu_about": "cb:menu:about",
    "menu_plans": "cb:menu:plans",
    "menu_start": "cb:menu:start",
    "menu_status": "cb:menu:status",
    "menu_edit_body": "cb:menu:edit_body",
    "menu_edit_attachments": "cb:menu:edit_attachments",
    "menu_edit_specialties": "cb:menu:edit_specialties",
    "menu_edit_states": "cb:menu:edit_states",
    "menu_pause": "cb:menu:pause",
    "menu_resume": "cb:menu:resume",
    "menu_plan": "cb:menu:plan",
    "menu_back_to_main": "cb:menu:main",
    "consent_accept": "cb:consent:accept",
    "consent_decline": "cb:consent:decline",
    "back": "cb:back",
    "done": "cb:done",
    "confirm": "cb:confirm",
    "plan_free": "cb:plan:free",
    "plan_basic": "cb:plan:basic",
    "plan_pro": "cb:plan:pro",
    "plan_max": "cb:plan:max",
    "specialty_toggle_prefix": "cb:sp:",  # cb:sp:<keyword>
    "state_toggle_prefix": "cb:st:",      # cb:st:<code>
    "attachment_remove_prefix": "cb:rm:",  # cb:rm:<file_id>
    "specialties_done": "cb:specialties_done",
    "states_done": "cb:states_done",
    "channel_check": "cb:channel:check",
}


def subscribe_gate(channel: str) -> InlineKeyboardMarkup:
    name = channel.lstrip("@")
    url = f"https://t.me/{name}"
    return InlineKeyboardMarkup(
        [
            _row(InlineKeyboardButton(messages.SUBSCRIBE_BUTTON, url=url)),
            _row(
                InlineKeyboardButton(
                    messages.SUBSCRIBE_CHECK_BUTTON, callback_data=CB["channel_check"]
                )
            ),
        ]
    )


def _row(*buttons: InlineKeyboardButton) -> list[InlineKeyboardButton]:
    return list(buttons)


def welcome_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            _row(InlineKeyboardButton(messages.MENU_ABOUT, callback_data=CB["menu_about"])),
            _row(InlineKeyboardButton(messages.MENU_PLANS, callback_data=CB["menu_plans"])),
            _row(InlineKeyboardButton(messages.MENU_START, callback_data=CB["menu_start"])),
        ]
    )


def main_menu(*, is_active: bool) -> InlineKeyboardMarkup:
    pause_label = messages.MENU_PAUSE if is_active else messages.MENU_RESUME
    pause_cb = CB["menu_pause"] if is_active else CB["menu_resume"]
    return InlineKeyboardMarkup(
        [
            _row(InlineKeyboardButton(messages.MENU_STATUS, callback_data=CB["menu_status"])),
            _row(
                InlineKeyboardButton(
                    messages.MENU_EDIT_BODY, callback_data=CB["menu_edit_body"]
                )
            ),
            _row(
                InlineKeyboardButton(
                    messages.MENU_EDIT_ATTACHMENTS,
                    callback_data=CB["menu_edit_attachments"],
                )
            ),
            _row(
                InlineKeyboardButton(
                    messages.MENU_EDIT_SPECIALTIES,
                    callback_data=CB["menu_edit_specialties"],
                ),
                InlineKeyboardButton(
                    messages.MENU_EDIT_STATES,
                    callback_data=CB["menu_edit_states"],
                ),
            ),
            _row(InlineKeyboardButton(pause_label, callback_data=pause_cb)),
            _row(InlineKeyboardButton(messages.MENU_PLAN, callback_data=CB["menu_plan"])),
        ]
    )


def back_to_main_only() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [_row(InlineKeyboardButton(messages.BACK_LABEL, callback_data=CB["menu_back_to_main"]))]
    )


def back_only() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [_row(InlineKeyboardButton(messages.BACK_LABEL, callback_data=CB["back"]))]
    )


def consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            _row(
                InlineKeyboardButton(
                    messages.CONSENT_BUTTON_ACCEPT, callback_data=CB["consent_accept"]
                )
            ),
            _row(
                InlineKeyboardButton(
                    messages.CONSENT_BUTTON_DECLINE, callback_data=CB["consent_decline"]
                )
            ),
        ]
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            _row(InlineKeyboardButton(messages.CONFIRM_BUTTON, callback_data=CB["confirm"])),
            _row(InlineKeyboardButton(messages.BACK_LABEL, callback_data=CB["back"])),
        ]
    )


def plans_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            _row(InlineKeyboardButton("Free", callback_data=CB["plan_free"])),
            _row(InlineKeyboardButton("Basic — 14,99 €", callback_data=CB["plan_basic"])),
            _row(InlineKeyboardButton("Pro — 29,99 €", callback_data=CB["plan_pro"])),
            _row(InlineKeyboardButton("Max — 99 €", callback_data=CB["plan_max"])),
            _row(
                InlineKeyboardButton(
                    messages.BACK_LABEL, callback_data=CB["menu_back_to_main"]
                )
            ),
        ]
    )


def checkout_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            _row(InlineKeyboardButton(messages.CHECKOUT_BUTTON, url=url)),
            _row(
                InlineKeyboardButton(
                    messages.BACK_LABEL, callback_data=CB["menu_plans"]
                )
            ),
        ]
    )


def _toggle_label(checked: bool, label: str) -> str:
    return f"✅ {label}" if checked else f"⬜ {label}"


def specialties_keyboard(picked: Iterable[str]) -> InlineKeyboardMarkup:
    picked_set = set(picked)
    rows: list[list[InlineKeyboardButton]] = []
    for keyword, _ar_label in SPECIALTIES:
        rows.append(
            _row(
                InlineKeyboardButton(
                    _toggle_label(keyword in picked_set, keyword),
                    callback_data=CB["specialty_toggle_prefix"] + keyword,
                )
            )
        )
    rows.append(
        _row(
            InlineKeyboardButton(messages.BACK_LABEL, callback_data=CB["back"]),
            InlineKeyboardButton(messages.DONE_LABEL, callback_data=CB["specialties_done"]),
        )
    )
    return InlineKeyboardMarkup(rows)


def states_keyboard(picked: Iterable[str]) -> InlineKeyboardMarkup:
    picked_set = set(picked)
    rows: list[list[InlineKeyboardButton]] = []
    # Two states per row to keep the keyboard compact.
    pairs: list[tuple[str, str]] = []
    for code, _de, _ar in STATES:
        pairs.append((code, STATE_LABELS_DE[code]))
    for i in range(0, len(pairs), 2):
        chunk = pairs[i : i + 2]
        rows.append(
            [
                InlineKeyboardButton(
                    _toggle_label(code in picked_set, label),
                    callback_data=CB["state_toggle_prefix"] + code,
                )
                for code, label in chunk
            ]
        )
    rows.append(
        _row(
            InlineKeyboardButton(messages.BACK_LABEL, callback_data=CB["back"]),
            InlineKeyboardButton(messages.DONE_LABEL, callback_data=CB["states_done"]),
        )
    )
    return InlineKeyboardMarkup(rows)


def attachments_keyboard(
    attachments: list[dict[str, Any]],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for meta in attachments:
        file_id = meta.get("telegram_file_id") or ""
        filename = meta.get("filename") or "?"
        rows.append(
            _row(
                InlineKeyboardButton(
                    f"🗑 {filename}",
                    callback_data=CB["attachment_remove_prefix"] + file_id,
                )
            )
        )
    rows.append(
        _row(
            InlineKeyboardButton(messages.BACK_LABEL, callback_data=CB["back"]),
            InlineKeyboardButton(messages.DONE_LABEL, callback_data=CB["done"]),
        )
    )
    return InlineKeyboardMarkup(rows)
