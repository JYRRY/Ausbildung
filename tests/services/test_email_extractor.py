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


# ── website-crawl path (HTML multi-strategy harvesting) ───────────────────────

from jyry.services.email_extractor import (  # noqa: E402
    employer_website,
    extract_contact_person_from_text,
    extract_emails_from_html,
    extract_result,
    get_contact_page_urls,
    normalize_website,
)


def test_html_extracts_mailto_with_percent_encoding():
    page = "<a href='mailto:bewerbung%40firma-x.de?subject=Hi'>Bewerbung</a>"
    assert "bewerbung@firma-x.de" in extract_emails_from_html(page)


def test_html_extracts_json_ld_email():
    page = '<script type="application/ld+json">{"email":"karriere@firma-x.de"}</script>'
    assert "karriere@firma-x.de" in extract_emails_from_html(page)


def test_html_extracts_meta_and_vcard():
    page = (
        '<meta name="reply-to" content="jobs@firma-x.de">'
        '<span class="email">personal@firma-x.de</span>'
    )
    emails = extract_emails_from_html(page)
    assert "jobs@firma-x.de" in emails
    assert "personal@firma-x.de" in emails


def test_html_deobfuscates_at_and_punkt():
    page = "<p>Schreiben Sie an ausbildung [at] firma-x [punkt] de</p>"
    assert "ausbildung@firma-x.de" in extract_emails_from_html(page)


def test_html_accepts_generic_on_own_website_but_ranks_it_last():
    page = "<p>bewerbung@firma-x.de</p><p>info@firma-x.de</p>"
    emails = extract_emails_from_html(page, accept_generic=True)
    assert emails[0] == "bewerbung@firma-x.de"
    assert "info@firma-x.de" in emails


def test_html_rejects_generic_when_not_accepted():
    page = "<p>info@firma-x.de</p>"
    assert extract_emails_from_html(page, accept_generic=False) == []


def test_html_rejects_file_extension_tld_and_placeholder_and_portal():
    page = (
        "<p>logo@sprite.png</p>"
        "<p>max.mustermann@firma-x.de</p>"
        "<p>info@stepstone.de</p>"
        "<p>noreply@firma-x.de</p>"
    )
    assert extract_emails_from_html(page, accept_generic=True) == []


def test_contact_person_frau_herr_with_title():
    assert (
        extract_contact_person_from_text("Ihre Ansprechpartnerin: Frau Dr. Anna Schmidt")
        == "Frau Dr. Anna Schmidt"
    )
    assert extract_contact_person_from_text("kein Name hier") is None


def test_normalize_website_adds_scheme():
    assert normalize_website("firma-x.de/") == "https://firma-x.de"
    assert normalize_website("http://firma-x.de") == "http://firma-x.de"


def test_get_contact_page_urls_builds_candidates():
    urls = get_contact_page_urls("https://firma-x.de", ["impressum", "kontakt"])
    assert urls[0] == "https://firma-x.de"
    assert "https://firma-x.de/impressum" in urls
    assert "https://firma-x.de/kontakt" in urls


def test_employer_website_prefers_darstellung_and_rejects_portals():
    d = _detail(
        {"hashId": "W", "arbeitgeberdarstellungUrl": "firma-x.de", "externeUrl": "x.de"}
    )
    assert employer_website(d) == "https://firma-x.de"

    portal = _detail({"hashId": "P", "externeUrl": "https://jobs.softgarden.io/apply"})
    assert employer_website(portal) is None

    none = _detail({"hashId": "N", "stellenangebotsBeschreibung": "kein link"})
    assert employer_website(none) is None


def test_extract_result_bundles_email_and_website():
    d = _detail(load_fixture("ba_detail_with_email.json"))
    result = extract_result(d)
    assert result.email == "bewerbung@konditorei-mueller.de"
    assert "bewerbung@konditorei-mueller.de" in result.all_emails
