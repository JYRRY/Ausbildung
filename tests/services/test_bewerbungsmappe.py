"""Tests for jyry.services.bewerbungsmappe."""

from __future__ import annotations

import io

import pytest
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from jyry.services.bewerbungsmappe import (
    AnschreibenContext,
    Sender,
    build_anrede,
    build_bewerbungsmappe,
    merge_pdfs,
    render_anschreiben,
)


def _ctx(**over) -> AnschreibenContext:
    base = dict(
        sender=Sender("Hadi Saleh", "Musterstr. 12", "80331 München"),
        company="Klinikum Schwabing GmbH",
        date_str="München, 19.07.2026",
        betreff="Bewerbung um einen Ausbildungsplatz als Pflegefachmann (m/w/d)",
        anrede="Sehr geehrte Damen und Herren,",
        body="mit großem Interesse bewerbe ich mich.\n\nZweiter Absatz.",
    )
    base.update(over)
    return AnschreibenContext(**base)


def _one_page_pdf(text: str) -> bytes:
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    c.drawString(100, 700, text)
    c.showPage()
    c.save()
    return b.getvalue()


@pytest.mark.parametrize(
    "contact,expected",
    [
        ("Frau Dr. Anna Meier", "Sehr geehrte Frau Dr. Anna Meier,"),
        ("Herr Klaus Schmidt", "Sehr geehrter Herr Klaus Schmidt,"),
        (None, "Sehr geehrte Damen und Herren,"),
        ("Team Personal", "Sehr geehrte Damen und Herren,"),
    ],
)
def test_build_anrede(contact, expected):
    assert build_anrede(contact) == expected


def test_render_anschreiben_is_single_page_pdf():
    pdf = render_anschreiben(_ctx())
    assert pdf.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) == 1


def test_render_contains_key_text():
    pdf = render_anschreiben(
        _ctx(anrede="Sehr geehrte Frau Meier,", company="Klinikum Schwabing GmbH")
    )
    text = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    assert "Klinikum Schwabing GmbH" in text
    assert "Sehr geehrte Frau Meier," in text
    assert "Pflegefachmann" in text


def test_build_bewerbungsmappe_prepends_letter_to_attachments():
    mappe = build_bewerbungsmappe(_ctx(), [_one_page_pdf("CV"), _one_page_pdf("Zeugnis")])
    reader = PdfReader(io.BytesIO(mappe))
    assert len(reader.pages) == 3  # 1 Anschreiben + 2 attachments


def test_merge_skips_corrupt_pdfs():
    good = _one_page_pdf("ok")
    merged = merge_pdfs([good, b"not a pdf", good])
    assert len(PdfReader(io.BytesIO(merged)).pages) == 2


def test_signature_order_closing_then_typed_then_handwritten():
    ctx = _ctx(closing="Mit freundlichen Grüßen")
    text = PdfReader(io.BytesIO(render_anschreiben(ctx))).pages[0].extract_text()
    assert "Mit freundlichen Grüßen" in text
    # After the closing the name appears twice: typed line + handwritten signature.
    tail = text[text.index("Mit freundlichen Grüßen"):]
    assert tail.count("Hadi Saleh") >= 2


def test_body_is_left_aligned_not_justified():
    from jyry.services import bewerbungsmappe as bm
    # No justified style should be configured anywhere in the module.
    import inspect
    assert "TA_JUSTIFY" not in inspect.getsource(bm)
