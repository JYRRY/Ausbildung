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
    "menu_edit_name": "cb:menu:edit_name",
    "menu_edit_gmail": "cb:menu:edit_gmail",
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
    "plan_plus": "cb:plan:plus",
    "plan_pro": "cb:plan:pro",
    "plan_max": "cb:plan:max",
    "plan_upgrade_confirm_plus": "cb:plan:upconf:plus",
    "plan_upgrade_confirm_pro": "cb:plan:upconf:pro",
    "plan_upgrade_confirm_max": "cb:plan:upconf:max",
    "plan_cancel": "cb:plan:cancel",
    "plan_cancel_proceed": "cb:plan:cancel_proceed",
    "plan_cancel_confirm": "cb:plan:cancel_confirm",
    "specialty_toggle_prefix": "cb:sp:",  # cb:sp:<keyword>
    "state_toggle_prefix": "cb:st:",      # cb:st:<code>
    "attachment_remove_prefix": "cb:rm:",  # cb:rm:<file_id>
    "specialties_done": "cb:specialties_done",
    "states_done": "cb:states_done",
    "channel_check": "cb:channel:check",
    "app_password_skip": "cb:app_password:skip",
    "menu_send_test": "cb:menu:send_test",
    "menu_templates": "cb:menu:templates",
    "template_pick_prefix": "cb:tpl:",       # cb:tpl:<keyword>
    "template_apply_prefix": "cb:tplapply:",  # cb:tplapply:<keyword>
    "forward": "cb:forward",
    "notifications_enable": "cb:notif:enable",
    "notifications_disable": "cb:notif:disable",
    "menu_notifications_toggle": "cb:menu:notif_toggle",
}


def notifications_prompt() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            _row(
                InlineKeyboardButton(
                    messages.NOTIFICATIONS_BUTTON_YES,
                    callback_data=CB["notifications_enable"],
                )
            ),
            _row(
                InlineKeyboardButton(
                    messages.NOTIFICATIONS_BUTTON_NO,
                    callback_data=CB["notifications_disable"],
                )
            ),
        ]
    )


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


def main_menu(
    *,
    is_active: bool,
    show_templates: bool = False,
    notifications_enabled: bool | None = None,
) -> InlineKeyboardMarkup:
    pause_label = messages.MENU_PAUSE if is_active else messages.MENU_RESUME
    pause_cb = CB["menu_pause"] if is_active else CB["menu_resume"]
    notif_label = (
        messages.MENU_NOTIFICATIONS_ON
        if notifications_enabled
        else messages.MENU_NOTIFICATIONS_OFF
    )
    rows: list[list[InlineKeyboardButton]] = [
        _row(InlineKeyboardButton(messages.MENU_STATUS, callback_data=CB["menu_status"])),
        _row(
            InlineKeyboardButton(
                messages.MENU_EDIT_NAME, callback_data=CB["menu_edit_name"]
            )
        ),
        _row(
            InlineKeyboardButton(
                messages.MENU_EDIT_GMAIL, callback_data=CB["menu_edit_gmail"]
            )
        ),
        _row(
            InlineKeyboardButton(
                messages.MENU_EDIT_BODY, callback_data=CB["menu_edit_body"]
            )
        ),
    ]
    if show_templates:
        rows.append(
            _row(
                InlineKeyboardButton(
                    messages.MENU_TEMPLATES, callback_data=CB["menu_templates"]
                )
            )
        )
    rows.extend(
        [
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
                )
            ),
            _row(
                InlineKeyboardButton(
                    messages.MENU_EDIT_STATES,
                    callback_data=CB["menu_edit_states"],
                )
            ),
            _row(InlineKeyboardButton(pause_label, callback_data=pause_cb)),
            _row(
                InlineKeyboardButton(
                    notif_label, callback_data=CB["menu_notifications_toggle"]
                )
            ),
            _row(
                InlineKeyboardButton(
                    messages.MENU_SEND_TEST, callback_data=CB["menu_send_test"]
                )
            ),
            _row(InlineKeyboardButton(messages.MENU_PLAN, callback_data=CB["menu_plan"])),
        ]
    )
    return InlineKeyboardMarkup(rows)


def templates_list_keyboard(keywords: list[str]) -> InlineKeyboardMarkup:
    """Render one button per available template keyword + Menü row."""
    rows: list[list[InlineKeyboardButton]] = [
        _row(
            InlineKeyboardButton(
                kw, callback_data=CB["template_pick_prefix"] + kw
            )
        )
        for kw in keywords
    ]
    rows.append(
        _row(
            InlineKeyboardButton(
                messages.MENU_LABEL, callback_data=CB["menu_back_to_main"]
            )
        )
    )
    return InlineKeyboardMarkup(rows)


def template_preview_keyboard(keyword: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            _row(
                InlineKeyboardButton(
                    messages.TEMPLATE_APPLY_LABEL,
                    callback_data=CB["template_apply_prefix"] + keyword,
                )
            ),
            _row(
                InlineKeyboardButton(
                    messages.TEMPLATE_BACK_TO_LIST,
                    callback_data=CB["menu_templates"],
                )
            ),
            _row(
                InlineKeyboardButton(
                    messages.MENU_LABEL, callback_data=CB["menu_back_to_main"]
                )
            ),
        ]
    )


def back_to_main_only() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [_row(InlineKeyboardButton(messages.MENU_LABEL, callback_data=CB["menu_back_to_main"]))]
    )


def back_only(*, allow_forward: bool = False) -> InlineKeyboardMarkup:
    """Navigation row used inside onboarding/edit conversations.

    Always renders ⬅️ Zurück + 🏠 Menü so the user can bail out at any
    step. ``allow_forward=True`` adds ➡️ Weiter for steps that may keep
    the existing value (text-input fields).
    """
    nav: list[InlineKeyboardButton] = [
        InlineKeyboardButton(messages.BACK_LABEL, callback_data=CB["back"]),
    ]
    if allow_forward:
        nav.append(
            InlineKeyboardButton(messages.FORWARD_LABEL, callback_data=CB["forward"])
        )
    nav.append(
        InlineKeyboardButton(messages.MENU_LABEL, callback_data=CB["menu_back_to_main"])
    )
    return InlineKeyboardMarkup([_row(*nav)])


def app_password_keyboard(*, has_existing: bool) -> InlineKeyboardMarkup:
    """Back/menu plus an optional 'already linked' shortcut."""
    rows: list[list[InlineKeyboardButton]] = []
    if has_existing:
        rows.append(
            _row(
                InlineKeyboardButton(
                    messages.APP_PASSWORD_SKIP_LABEL,
                    callback_data=CB["app_password_skip"],
                )
            )
        )
    rows.append(
        _row(
            InlineKeyboardButton(messages.BACK_LABEL, callback_data=CB["back"]),
            InlineKeyboardButton(
                messages.MENU_LABEL, callback_data=CB["menu_back_to_main"]
            ),
        )
    )
    return InlineKeyboardMarkup(rows)


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
            _row(
                InlineKeyboardButton(
                    messages.MENU_LABEL, callback_data=CB["menu_back_to_main"]
                )
            ),
        ]
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            _row(InlineKeyboardButton(messages.CONFIRM_BUTTON, callback_data=CB["confirm"])),
            _row(
                InlineKeyboardButton(messages.BACK_LABEL, callback_data=CB["back"]),
                InlineKeyboardButton(
                    messages.MENU_LABEL, callback_data=CB["menu_back_to_main"]
                ),
            ),
        ]
    )


_PLAN_RANK: dict[str, int] = {"free": 0, "plus": 1, "pro": 2, "max": 3}

_ALL_PAID_PLANS: tuple[tuple[str, str, str], ...] = (
    ("plus", "Plus", "14,99 €/Monat"),
    ("pro", "Pro", "29,99 € / 3 Monate"),
    ("max", "Max", "99 € / 6 Monate"),
)


def plans_menu(current_plan: str | None = None) -> InlineKeyboardMarkup:
    """Render the Tarife menu.

    - No active paid sub (None / free): show all four plans for purchase.
    - Active paid sub (plus/pro/max): show only higher-tier plans as
      upgrades + an "Abo kündigen" button. No downgrade.
    """
    rows: list[list[InlineKeyboardButton]] = []
    current = (current_plan or "free").lower()
    current_rank = _PLAN_RANK.get(current, 0)

    if current_rank == 0:
        rows.append(_row(InlineKeyboardButton("Free", callback_data=CB["plan_free"])))
        for key, label, price in _ALL_PAID_PLANS:
            rows.append(
                _row(
                    InlineKeyboardButton(
                        f"{label} — {price}", callback_data=CB[f"plan_{key}"]
                    )
                )
            )
    else:
        for key, label, price in _ALL_PAID_PLANS:
            if _PLAN_RANK[key] <= current_rank:
                continue
            rows.append(
                _row(
                    InlineKeyboardButton(
                        f"{messages.PLAN_UPGRADE_PREFIX}{label} — {price}",
                        callback_data=CB[f"plan_{key}"],
                    )
                )
            )
        rows.append(
            _row(
                InlineKeyboardButton(
                    messages.PLAN_CANCEL_LABEL, callback_data=CB["plan_cancel"]
                )
            )
        )

    rows.append(
        _row(
            InlineKeyboardButton(
                messages.BACK_LABEL, callback_data=CB["menu_back_to_main"]
            )
        )
    )
    return InlineKeyboardMarkup(rows)


def upgrade_confirm_keyboard(target_plan: str) -> InlineKeyboardMarkup:
    cb_key = f"plan_upgrade_confirm_{target_plan}"
    return InlineKeyboardMarkup(
        [
            _row(
                InlineKeyboardButton(
                    messages.PLAN_UPGRADE_BUTTON, callback_data=CB[cb_key]
                )
            ),
            _row(
                InlineKeyboardButton(
                    messages.BACK_LABEL, callback_data=CB["menu_plans"]
                ),
                InlineKeyboardButton(
                    messages.MENU_LABEL, callback_data=CB["menu_back_to_main"]
                ),
            ),
        ]
    )


def retention_keyboard(target_plan: str) -> InlineKeyboardMarkup:
    """Two-choice screen shown before the real cancel-confirm: upgrade
    instead, or proceed to the actual cancel flow."""
    cb_upgrade = CB[f"plan_{target_plan}"]
    return InlineKeyboardMarkup(
        [
            _row(
                InlineKeyboardButton(
                    messages.PLAN_RETENTION_UPGRADE_BUTTON.format(
                        target_plan=target_plan.capitalize()
                    ),
                    callback_data=cb_upgrade,
                )
            ),
            _row(
                InlineKeyboardButton(
                    messages.PLAN_RETENTION_PROCEED_BUTTON,
                    callback_data=CB["plan_cancel_proceed"],
                )
            ),
            _row(
                InlineKeyboardButton(
                    messages.BACK_LABEL, callback_data=CB["menu_plans"]
                ),
                InlineKeyboardButton(
                    messages.MENU_LABEL, callback_data=CB["menu_back_to_main"]
                ),
            ),
        ]
    )


def cancel_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            _row(
                InlineKeyboardButton(
                    messages.PLAN_CANCEL_CONFIRM_BUTTON,
                    callback_data=CB["plan_cancel_confirm"],
                )
            ),
            _row(
                InlineKeyboardButton(
                    messages.BACK_LABEL, callback_data=CB["menu_plans"]
                ),
                InlineKeyboardButton(
                    messages.MENU_LABEL, callback_data=CB["menu_back_to_main"]
                ),
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
            InlineKeyboardButton(
                messages.MENU_LABEL, callback_data=CB["menu_back_to_main"]
            ),
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
            InlineKeyboardButton(
                messages.MENU_LABEL, callback_data=CB["menu_back_to_main"]
            ),
        )
    )
    return InlineKeyboardMarkup(rows)


def attachments_keyboard(
    attachments: list[dict[str, Any]],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    # Telegram limits callback_data to 64 bytes, but real Telegram file_ids
    # are 50-80+ chars, so we key the remove-button by the attachment's index
    # in the list instead and look up the file_id on the handler side.
    for idx, meta in enumerate(attachments):
        filename = meta.get("filename") or "?"
        rows.append(
            _row(
                InlineKeyboardButton(
                    f"🗑 {filename}",
                    callback_data=f"{CB['attachment_remove_prefix']}{idx}",
                )
            )
        )
    rows.append(
        _row(
            InlineKeyboardButton(messages.BACK_LABEL, callback_data=CB["back"]),
            InlineKeyboardButton(messages.DONE_LABEL, callback_data=CB["done"]),
            InlineKeyboardButton(
                messages.MENU_LABEL, callback_data=CB["menu_back_to_main"]
            ),
        )
    )
    return InlineKeyboardMarkup(rows)
