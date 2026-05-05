"""Tests for jyry.services.gmail_sender."""

from __future__ import annotations

import pytest
from aiosmtplib.errors import (
    SMTPAuthenticationError,
    SMTPRecipientsRefused,
    SMTPResponseException,
    SMTPTimeoutError,
)

from jyry.services.gmail_sender import (
    Attachment,
    GmailSender,
    SendOutcome,
    _build_message,
)


@pytest.fixture
def sender(settings):
    return GmailSender(
        settings,
        sender_email="alice@gmail.com",
        app_password="appp asss-word XXXX",
        sender_name="Alice Test",
    )


def test_build_message_has_required_headers_and_plain_body():
    msg = _build_message(
        sender_email="alice@gmail.com",
        sender_name="Alice",
        to_email="hr@firma.de",
        subject="Bewerbung",
        body="Sehr geehrte Damen und Herren, …",
        attachments=[],
    )
    assert msg["From"] == "Alice <alice@gmail.com>"
    assert msg["To"] == "hr@firma.de"
    assert msg["Subject"] == "Bewerbung"
    assert msg["Message-ID"].endswith("@gmail.com>")
    assert msg.get_content_type() == "text/plain"
    assert "Sehr geehrte" in msg.get_content()


def test_build_message_attaches_files_with_correct_mime():
    pdf = Attachment(filename="cv.pdf", content=b"%PDF-1.4 fake", mime_type="application/pdf")
    img = Attachment(filename="photo.jpg", content=b"\xff\xd8jpeg", mime_type="image/jpeg")
    msg = _build_message(
        sender_email="a@gmail.com",
        sender_name=None,
        to_email="b@firma.de",
        subject="x",
        body="y",
        attachments=[pdf, img],
    )
    parts = list(msg.iter_attachments())
    assert len(parts) == 2
    assert parts[0].get_filename() == "cv.pdf"
    assert parts[0].get_content_type() == "application/pdf"
    assert parts[1].get_filename() == "photo.jpg"
    assert parts[1].get_content_type() == "image/jpeg"


@pytest.mark.asyncio
async def test_send_success_returns_sent(sender, mocker):
    spy = mocker.patch("aiosmtplib.send", autospec=True)
    result = await sender.send(
        to_email="hr@firma.de",
        subject="Bewerbung",
        body="hallo",
    )
    assert result.outcome is SendOutcome.SENT
    assert result.smtp_code == 250
    assert result.message_id and result.message_id.endswith("@gmail.com>")
    assert spy.call_count == 1
    kwargs = spy.call_args.kwargs
    assert kwargs["hostname"] == "smtp.gmail.com"
    assert kwargs["port"] == 587
    assert kwargs["start_tls"] is True
    assert kwargs["username"] == "alice@gmail.com"


@pytest.mark.asyncio
async def test_4xx_response_classified_transient(sender, mocker):
    mocker.patch(
        "aiosmtplib.send",
        side_effect=SMTPResponseException(421, "Service not available"),
    )
    result = await sender.send(to_email="x@y.de", subject="s", body="b")
    assert result.outcome is SendOutcome.TRANSIENT
    assert result.smtp_code == 421


@pytest.mark.asyncio
async def test_5xx_response_classified_permanent(sender, mocker):
    mocker.patch(
        "aiosmtplib.send",
        side_effect=SMTPResponseException(550, "User unknown"),
    )
    result = await sender.send(to_email="x@y.de", subject="s", body="b")
    assert result.outcome is SendOutcome.PERMANENT
    assert result.smtp_code == 550


@pytest.mark.asyncio
async def test_auth_error_classified_permanent(sender, mocker):
    mocker.patch(
        "aiosmtplib.send",
        side_effect=SMTPAuthenticationError(535, "Username and Password not accepted"),
    )
    result = await sender.send(to_email="x@y.de", subject="s", body="b")
    assert result.outcome is SendOutcome.PERMANENT
    assert result.smtp_code == 535


@pytest.mark.asyncio
async def test_recipients_refused_classified_permanent(sender, mocker):
    mocker.patch(
        "aiosmtplib.send",
        side_effect=SMTPRecipientsRefused([("x@y.de", 550, b"no such user")]),
    )
    result = await sender.send(to_email="x@y.de", subject="s", body="b")
    assert result.outcome is SendOutcome.PERMANENT


@pytest.mark.asyncio
async def test_timeout_classified_transient(sender, mocker):
    mocker.patch("aiosmtplib.send", side_effect=SMTPTimeoutError("timeout"))
    result = await sender.send(to_email="x@y.de", subject="s", body="b")
    assert result.outcome is SendOutcome.TRANSIENT


@pytest.mark.asyncio
async def test_connection_error_classified_transient(sender, mocker):
    mocker.patch("aiosmtplib.send", side_effect=ConnectionRefusedError("nope"))
    result = await sender.send(to_email="x@y.de", subject="s", body="b")
    assert result.outcome is SendOutcome.TRANSIENT


@pytest.mark.asyncio
async def test_asyncio_timeout_classified_transient(sender, mocker):
    mocker.patch("aiosmtplib.send", side_effect=TimeoutError())
    result = await sender.send(to_email="x@y.de", subject="s", body="b")
    assert result.outcome is SendOutcome.TRANSIENT


@pytest.mark.asyncio
async def test_password_never_logged(sender, mocker, caplog):
    caplog.set_level("DEBUG", logger="jyry.services.gmail_sender")
    mocker.patch(
        "aiosmtplib.send",
        side_effect=SMTPResponseException(421, "Service not available"),
    )
    await sender.send(to_email="x@y.de", subject="s", body="b")
    for rec in caplog.records:
        assert "appp asss-word" not in rec.getMessage()
