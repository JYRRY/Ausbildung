"""Render a German Anschreiben (cover letter) as PDF, with a handwritten-style
signature, and optionally merge it with the applicant's documents.

Layout (mirrors the applicant's own template):
- top RIGHT: applicant block (name, street, city, phone, email) — the fields
  the user fills in on the web form;
- top LEFT: employer address block (company, street, PLZ + city);
- date, right-aligned, = the day the letter is generated;
- Betreff, salutation (per-employer, via :func:`build_anrede`), body;
- closing, a handwritten-style signature of the name, then the typed name.

Pure and deterministic: the caller passes a preformatted ``date_str`` so the
output is reproducible and unit-testable.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Frame, Paragraph, Spacer

_PAGE_W, _PAGE_H = A4
_LEFT = 2.5 * cm
_RIGHT = 2.0 * cm

# Handwriting font for the signature (Sacramento, SIL OFL, bundled under
# jyry/assets/fonts).
_SIGNATURE_FONT = "Signature"
_FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Sacramento-Regular.ttf"
try:
    pdfmetrics.registerFont(TTFont(_SIGNATURE_FONT, str(_FONT_PATH)))
    _HAS_SIGNATURE_FONT = True
except Exception:  # pragma: no cover - missing font falls back to italic
    _HAS_SIGNATURE_FONT = False


@dataclass(frozen=True, slots=True)
class Sender:
    name: str
    street: str = ""
    plz_city: str = ""
    phone: str = ""
    email: str = ""


@dataclass(frozen=True, slots=True)
class AnschreibenContext:
    sender: Sender
    company: str
    date_str: str  # e.g. "19.07.2026" — the day the applicant generates it
    betreff: str
    anrede: str
    body: str  # rendered cover-letter text; blank lines separate paragraphs
    company_street: str | None = None
    company_plz_city: str | None = None
    closing: str = "Mit freundlichen Grüßen"


def build_anrede(contact_person: str | None) -> str:
    """Per-employer salutation from a 'Frau/Herr <Name>' contact, or the
    neutral default when no named contact is known."""
    if contact_person:
        cp = contact_person.strip()
        low = cp.lower()
        if low.startswith("herr "):
            return f"Sehr geehrter {cp},"
        if low.startswith("frau "):
            return f"Sehr geehrte {cp},"
    return "Sehr geehrte Damen und Herren,"


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_esc(text) or "&nbsp;", style)


def _split_paragraphs(text: str) -> list[str]:
    blocks = [b.strip() for b in (text or "").replace("\r\n", "\n").split("\n\n")]
    paras = [b.replace("\n", " ") for b in blocks if b]
    return paras or [""]


def _draw_header(canvas, ctx: AnschreibenContext) -> None:
    """Applicant block (right), employer block (left), date (right)."""
    right_x = _PAGE_W - _RIGHT
    top_y = _PAGE_H - 2.2 * cm

    # Applicant — right-aligned.
    s = ctx.sender
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawRightString(right_x, top_y, s.name)
    canvas.setFont("Helvetica", 9.5)
    y = top_y - 15
    for line in (s.street, s.plz_city, s.phone, s.email):
        if line:
            canvas.drawRightString(right_x, y, line)
            y -= 12.5

    # Employer — left aligned.
    canvas.setFont("Helvetica", 10.5)
    ey = top_y
    for line in (ctx.company, ctx.company_street, ctx.company_plz_city):
        if line:
            canvas.drawString(_LEFT, ey, line)
            ey -= 13

    # Date — right-aligned, below the applicant block.
    canvas.setFont("Helvetica", 10.5)
    canvas.drawRightString(right_x, min(y, ey) - 10, ctx.date_str)


def _signature_flowables(ctx: AnschreibenContext) -> list:
    """Order: closing → typed name → handwritten signature."""
    base = ParagraphStyle("body", fontName="Helvetica", fontSize=10.5, leading=14)
    if _HAS_SIGNATURE_FONT:
        sig_style = ParagraphStyle(
            "sig", fontName=_SIGNATURE_FONT, fontSize=30, leading=32
        )
    else:  # graceful fallback
        sig_style = ParagraphStyle(
            "sig", fontName="Helvetica-Oblique", fontSize=15, leading=20
        )
    return [
        _p(ctx.closing, base),
        Spacer(1, 0.15 * cm),
        _p(ctx.sender.name, base),
        Spacer(1, 0.2 * cm),
        _p(ctx.sender.name, sig_style),
    ]


def render_anschreiben(ctx: AnschreibenContext) -> bytes:
    """Render the cover letter to a single-page PDF and return its bytes."""
    buf = io.BytesIO()
    from reportlab.pdfgen.canvas import Canvas

    canvas = Canvas(buf, pagesize=A4)
    canvas.setTitle(ctx.betreff)
    _draw_header(canvas, ctx)

    # Left-aligned (not justified): keeps natural word spacing.
    base = ParagraphStyle("body", fontName="Helvetica", fontSize=10.5, leading=14)
    betreff_style = ParagraphStyle("betreff", parent=base, fontName="Helvetica-Bold")

    story: list = [
        _p(ctx.betreff, betreff_style),
        Spacer(1, 0.5 * cm),
        _p(ctx.anrede, base),
        Spacer(1, 0.3 * cm),
    ]
    for para in _split_paragraphs(ctx.body):
        story.append(_p(para, base))
        story.append(Spacer(1, 0.25 * cm))
    story.append(Spacer(1, 0.4 * cm))
    story.extend(_signature_flowables(ctx))

    # Body frame sits below the header block.
    frame = Frame(
        _LEFT,
        2.0 * cm,
        _PAGE_W - _LEFT - _RIGHT,
        _PAGE_H - 2.0 * cm - 6.0 * cm,  # top reserved for the header
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    frame.addFromList(story, canvas)
    canvas.showPage()
    canvas.save()
    return buf.getvalue()


def merge_pdfs(pdfs: list[bytes]) -> bytes:
    """Concatenate PDFs (skipping any that fail to parse) into one document."""
    writer = PdfWriter()
    for pdf in pdfs:
        try:
            reader = PdfReader(io.BytesIO(pdf))
        except Exception:
            continue
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def build_bewerbungsmappe(ctx: AnschreibenContext, attachments: list[bytes]) -> bytes:
    """Anschreiben (page 1) + the applicant's PDF attachments, as one file.

    Note: the product may instead send the Anschreiben and the CV as *separate*
    attachments; this helper is kept for the merged-file option.
    """
    return merge_pdfs([render_anschreiben(ctx), *attachments])
