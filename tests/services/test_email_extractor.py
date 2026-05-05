"""Tests for jyry.services.email_extractor."""

from __future__ import annotations

import pytest

from jyry.services.bundesagentur import JobDetail, _parse_detail
from jyry.services.email_extractor import (
    EMAIL_RE,
    GENERIC_DOMAINS,
    GENERIC_LOCALPARTS,
    extract_email,
)
from tests.conftest import load_fixture


def _detail(payload: dict) -> JobDetail:
    return _parse_detail(payload)


def test_regex_matches_simple_addresses():
    text = "schreiben Sie an bewerbung@konditorei-mueller.de bitte!"
    match = EMAIL_RE.search(text)
    assert match is not None
    assert match.group("addr") == "bewerbung@konditorei-mueller.de"


def test_regex_rejects_trailing_punctuation():
    match = EMAIL_RE.search("Mail: foo@bar.de.")
    assert match is not None
    assert match.group("addr") == "foo@bar.de"


def test_extract_picks_specific_over_generic():
    detail = _detail(load_fixture("ba_detail_with_email.json"))
    assert extract_email(detail) == "bewerbung@konditorei-mueller.de"


def test_extract_returns_none_when_no_email():
    detail = _detail(load_fixture("ba_detail_no_email.json"))
    assert extract_email(detail) is None


def test_extract_drops_only_generic_addresses():
    detail = _detail(load_fixture("ba_detail_generic_email.json"))
    # info@arbeitsagentur.de + no-reply@example.com → both blocked
    assert extract_email(detail) is None


def test_extract_picks_up_structured_field():
    detail = _detail(
        {
            "hashId": "X",
            "stellenangebotsBeschreibung": "ohne email",
            "bewerbungEmail": "Karriere@beispiel-firma.de",
            "arbeitgeber": "Beispiel Firma",
        }
    )
    assert extract_email(detail) == "karriere@beispiel-firma.de"


def test_extract_picks_up_mailto_link():
    body = (
        "<p>Bewerbungen an <a href='mailto:ausbildung@meta-werke.de?subject=Hi'>"
        "ausbildung@meta-werke.de</a></p>"
    )
    detail = _detail({"hashId": "Y", "stellenangebotsBeschreibung": body})
    assert extract_email(detail) == "ausbildung@meta-werke.de"


def test_extract_prefers_bewerbung_over_random_local_part():
    body = (
        "Allgemein: jens.mueller@firma.de — für Bewerbungen bitte ausschließlich "
        "an bewerbung@firma.de senden."
    )
    detail = _detail({"hashId": "Z", "stellenangebotsBeschreibung": body})
    assert extract_email(detail) == "bewerbung@firma.de"


def test_extract_skips_email_in_subdomain_of_generic_host():
    body = "Kontakt: hr@mail.arbeitsagentur.de"
    detail = _detail({"hashId": "Q", "stellenangebotsBeschreibung": body})
    assert extract_email(detail) is None


@pytest.mark.parametrize("local", sorted(GENERIC_LOCALPARTS))
def test_generic_local_parts_are_blocked(local):
    body = f"Kontakt: {local}@firma-x.de"
    detail = _detail({"hashId": "L", "stellenangebotsBeschreibung": body})
    assert extract_email(detail) is None


@pytest.mark.parametrize("domain", sorted(GENERIC_DOMAINS))
def test_generic_domains_are_blocked(domain):
    body = f"Kontakt: jens@{domain}"
    detail = _detail({"hashId": "D", "stellenangebotsBeschreibung": body})
    assert extract_email(detail) is None
