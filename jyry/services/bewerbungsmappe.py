"""Render a German Anschreiben (cover letter) as PDF and merge it with the
applicant's uploaded documents into one Bewerbungsmappe per employer.

The applicant writes the letter *body* once during onboarding
(``EmailDraft.body_template``); here we wrap it in a proper DIN-5008-style
business letter — sender block, recipient address, date, Betreff and a
per-employer salutation (using the contact person the website crawler found,
e.g. "Sehr geehrte Frau Meier,") — then prepend it to their CV/certificate
PDFs with pypdf.

Pure and deterministic: callers pass a preformatted date string (no wall-clock
here) so the output is reproducible and unit-testable.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from pypdf import PdfReader, PdfWriter
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


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
    date_str: str  # e.g. "München, 19.07.2026" — preformatted by the caller
    betreff: str
    anrede: str
    body: str  # rendered cover-letter text; blank lines separate paragraphs
    company_street: str | None = None
    company_plz_city: str | None = None
    anlagen: list[str] = field(default_factory=list)
    closing: str = "Mit freundlichen Grüßen"


def build_anrede(contact_person: str | None) -> str:
    """Per-employer salutation from a 'Frau/Herr <Name>' contact, or the
    neutral default when no named contact is known."""
    if contact_person:
        cp = contact_person.strip()
        low = cp.lower()
        if low.startswith("frau ") or low.startswith("herr "):
            return f"Sehr geehrte{'r' if low.startswith('herr') else ''} {cp},"
    return "Sehr geehrte Damen und Herren,"


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    # reportlab paragraphs are mini-HTML; escape the few chars that matter.
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe or "&nbsp;", style)


def render_anschreiben(ctx: AnschreibenContext) -> bytes:
    """Render the cover letter to a single-page PDF and return its bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
        title=ctx.betreff,
    )
    base = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        alignment=TA_JUSTIFY,
    )
    small = ParagraphStyle("small", parent=base, fontSize=8, leading=11)
    bold = ParagraphStyle("bold", parent=base, fontName="Helvetica-Bold")

    story: list = []

    # Sender line (small, above the recipient block).
    sender = ctx.sender
    sender_bits = [b for b in (sender.name, sender.street, sender.plz_city) if b]
    story.append(_p(" · ".join(sender_bits), small))
    story.append(Spacer(1, 0.8 * cm))

    # Recipient block.
    story.append(_p(ctx.company, base))
    if ctx.company_street:
        story.append(_p(ctx.company_street, base))
    if ctx.company_plz_city:
        story.append(_p(ctx.company_plz_city, base))
    story.append(Spacer(1, 0.8 * cm))

    # Date, right-aligned.
    story.append(_p(ctx.date_str, ParagraphStyle("date", parent=base, alignment=2)))
    story.append(Spacer(1, 0.7 * cm))

    # Betreff.
    story.append(_p(ctx.betreff, bold))
    story.append(Spacer(1, 0.5 * cm))

    # Salutation.
    story.append(_p(ctx.anrede, base))
    story.append(Spacer(1, 0.3 * cm))

    # Body paragraphs (blank line = new paragraph).
    for para in _split_paragraphs(ctx.body):
        story.append(_p(para, base))
        story.append(Spacer(1, 0.25 * cm))

    # Closing + name.
    story.append(Spacer(1, 0.4 * cm))
    story.append(_p(ctx.closing, base))
    story.append(Spacer(1, 0.4 * cm))
    story.append(_p(sender.name, base))

    # Anlagen.
    if ctx.anlagen:
        story.append(Spacer(1, 0.6 * cm))
        story.append(_p("Anlagen", bold))
        story.append(_p(", ".join(ctx.anlagen), small))

    doc.build(story)
    return buf.getvalue()


def _split_paragraphs(text: str) -> list[str]:
    blocks = [b.strip() for b in (text or "").replace("\r\n", "\n").split("\n\n")]
    paras = [b.replace("\n", " ") for b in blocks if b]
    return paras or [""]


def _pdf_page_count(pdf: bytes) -> int:
    try:
        return len(PdfReader(io.BytesIO(pdf)).pages)
    except Exception:
        return 0


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


def build_bewerbungsmappe(
    ctx: AnschreibenContext, attachments: list[bytes]
) -> bytes:
    """Anschreiben (page 1) + the applicant's PDF attachments, as one file."""
    anschreiben = render_anschreiben(ctx)
    return merge_pdfs([anschreiben, *attachments])
