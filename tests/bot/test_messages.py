"""Tests for jyry.bot.messages — every key is present, non-empty, and German."""

from __future__ import annotations

from jyry.bot import messages


def test_every_key_in_all_keys_resolves():
    for name in messages.ALL_KEYS:
        value = getattr(messages, name)
        assert value, f"messages.{name} is empty"
        assert isinstance(value, str), f"messages.{name} is not str"


def test_no_arabic_letters_leak_into_user_strings():
    """German-only UI: no Arabic letters in user-visible messages."""
    arabic_block = range(0x0600, 0x06FF + 1)
    for name in messages.ALL_KEYS:
        value = getattr(messages, name)
        assert not any(ord(ch) in arabic_block for ch in value), (
            f"messages.{name} contains Arabic letters"
        )


def test_format_placeholders_resolve_for_known_templates():
    rendered = messages.STATUS_TEMPLATE.format(
        plan="pro",
        sent_today=3,
        daily_quota=100,
        remaining=97,
        total_sent=42,
        state=messages.STATUS_STATE_ACTIVE,
    )
    assert "pro" in rendered
    assert "3" in rendered
    assert "97" in rendered
    assert messages.STATUS_STATE_ACTIVE in rendered


def test_specialties_cap_template_renders():
    assert "5" in messages.ASK_SPECIALTIES.format(cap=5)
