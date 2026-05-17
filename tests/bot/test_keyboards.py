"""Tests for jyry.bot.keyboards — labels and callback-data shape."""

from __future__ import annotations

from jyry.bot import keyboards, messages
from jyry.bot.keyboards import CB
from jyry.constants import SPECIALTIES, STATE_CODES


def _flat(markup):
    return [btn for row in markup.inline_keyboard for btn in row]


def test_welcome_menu_has_about_plans_start():
    btns = _flat(keyboards.welcome_menu())
    callbacks = {b.callback_data for b in btns}
    assert {CB["menu_about"], CB["menu_plans"], CB["menu_start"]} <= callbacks


def test_main_menu_pause_state_swaps_label_and_callback():
    active_btns = _flat(keyboards.main_menu(is_active=True))
    paused_btns = _flat(keyboards.main_menu(is_active=False))
    active_pause = next(
        b for b in active_btns if b.callback_data in (CB["menu_pause"], CB["menu_resume"])
    )
    paused_pause = next(
        b for b in paused_btns if b.callback_data in (CB["menu_pause"], CB["menu_resume"])
    )
    assert active_pause.callback_data == CB["menu_pause"]
    assert active_pause.text == messages.MENU_PAUSE
    assert paused_pause.callback_data == CB["menu_resume"]
    assert paused_pause.text == messages.MENU_RESUME


def test_consent_keyboard_has_accept_and_decline():
    btns = _flat(keyboards.consent_keyboard())
    cbs = {b.callback_data for b in btns}
    assert cbs == {
        CB["consent_accept"],
        CB["consent_decline"],
        CB["menu_back_to_main"],
    }


def test_specialties_keyboard_renders_all_13_plus_back_done():
    btns = _flat(keyboards.specialties_keyboard(picked=set()))
    toggle_buttons = [b for b in btns if b.callback_data.startswith(CB["specialty_toggle_prefix"])]
    assert len(toggle_buttons) == len(SPECIALTIES) == 13
    cbs = {b.callback_data for b in btns}
    assert CB["back"] in cbs
    assert CB["specialties_done"] in cbs


def test_specialties_keyboard_shows_check_for_picked():
    picked = {"Mechatroniker", "Bäcker"}
    btns = _flat(keyboards.specialties_keyboard(picked=picked))
    for b in btns:
        if not b.callback_data.startswith(CB["specialty_toggle_prefix"]):
            continue
        keyword = b.callback_data.removeprefix(CB["specialty_toggle_prefix"])
        if keyword in picked:
            assert b.text.startswith("✅")
        else:
            assert b.text.startswith("⬜")


def test_states_keyboard_renders_all_16():
    btns = _flat(keyboards.states_keyboard(picked=set()))
    toggle_buttons = [b for b in btns if b.callback_data.startswith(CB["state_toggle_prefix"])]
    assert len(toggle_buttons) == len(STATE_CODES) == 16


def test_attachments_keyboard_lists_each_file_with_remove_callback():
    metas = [
        {"telegram_file_id": "F1", "filename": "cv.pdf"},
        {"telegram_file_id": "F2", "filename": "zeugnis.pdf"},
    ]
    btns = _flat(keyboards.attachments_keyboard(metas))
    remove_cbs = [
        b.callback_data for b in btns if b.callback_data.startswith(CB["attachment_remove_prefix"])
    ]
    # Buttons are keyed by index, not file_id, so we stay under Telegram's
    # 64-byte callback_data ceiling even when file_ids are 70+ chars.
    assert remove_cbs == [
        CB["attachment_remove_prefix"] + "0",
        CB["attachment_remove_prefix"] + "1",
    ]


def test_attachments_keyboard_callback_data_under_telegram_limit():
    # Real Telegram document file_ids run to 70-80 chars — they used to be
    # interpolated into callback_data and blow past the 64-byte limit.
    long_file_id = (
        "BQACAgQAAxkBAAN8agebAuBCGNAsB20qlh2"
        "pY5S0mB4AAsMcAAJYOUFQh77nYW2TKCU7BA"
    )
    metas = [{"telegram_file_id": long_file_id, "filename": "long.pdf"}]
    btns = _flat(keyboards.attachments_keyboard(metas))
    for b in btns:
        assert len(b.callback_data.encode("utf-8")) <= 64


def test_plans_menu_has_four_plans_plus_back():
    btns = _flat(keyboards.plans_menu())
    plan_cbs = {b.callback_data for b in btns if b.callback_data.startswith("cb:plan:")}
    assert plan_cbs == {CB["plan_free"], CB["plan_plus"], CB["plan_pro"], CB["plan_max"]}


def test_plans_menu_for_plus_user_shows_pro_max_upgrade_and_cancel():
    btns = _flat(keyboards.plans_menu(current_plan="plus"))
    cbs = {b.callback_data for b in btns}
    # Free and Plus are gone (no downgrade, no re-purchase of current plan)
    assert CB["plan_free"] not in cbs
    assert CB["plan_plus"] not in cbs
    # Only Pro + Max remain as upgrade targets
    assert CB["plan_pro"] in cbs
    assert CB["plan_max"] in cbs
    # Cancel button present
    assert CB["plan_cancel"] in cbs
    # Upgrade labels reflect upgrade intent
    upgrade_btns = [b for b in btns if b.callback_data in {CB["plan_pro"], CB["plan_max"]}]
    assert all(b.text.startswith(messages.PLAN_UPGRADE_PREFIX) for b in upgrade_btns)


def test_plans_menu_for_pro_user_shows_only_max_upgrade():
    btns = _flat(keyboards.plans_menu(current_plan="pro"))
    cbs = {b.callback_data for b in btns}
    assert CB["plan_plus"] not in cbs
    assert CB["plan_pro"] not in cbs
    assert CB["plan_max"] in cbs
    assert CB["plan_cancel"] in cbs


def test_plans_menu_for_max_user_shows_no_upgrades_only_cancel():
    btns = _flat(keyboards.plans_menu(current_plan="max"))
    cbs = {b.callback_data for b in btns}
    assert not (cbs & {CB["plan_plus"], CB["plan_pro"], CB["plan_max"]})
    assert CB["plan_cancel"] in cbs


def test_plans_title_advertises_max_as_six_months_not_yearly():
    assert "6 Monate" in messages.PLANS_TITLE
    assert "/Jahr" not in messages.PLANS_TITLE


def test_upgrade_confirm_keyboard_has_confirm_button():
    btns = _flat(keyboards.upgrade_confirm_keyboard("pro"))
    cbs = {b.callback_data for b in btns}
    assert CB["plan_upgrade_confirm_pro"] in cbs


def test_cancel_confirm_keyboard_has_confirm_button():
    btns = _flat(keyboards.cancel_confirm_keyboard())
    cbs = {b.callback_data for b in btns}
    assert CB["plan_cancel_confirm"] in cbs
