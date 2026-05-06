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
    assert cbs == {CB["consent_accept"], CB["consent_decline"]}


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
    assert remove_cbs == [
        CB["attachment_remove_prefix"] + "F1",
        CB["attachment_remove_prefix"] + "F2",
    ]


def test_plans_menu_has_four_plans_plus_back():
    btns = _flat(keyboards.plans_menu())
    plan_cbs = {b.callback_data for b in btns if b.callback_data.startswith("cb:plan:")}
    assert plan_cbs == {CB["plan_free"], CB["plan_basic"], CB["plan_pro"], CB["plan_max"]}
