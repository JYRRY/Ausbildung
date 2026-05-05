"""Per-user Gmail SMTP sender (aiosmtplib + STARTTLS + multipart MIME).

The bot never owns SMTP credentials: each user supplies their own Gmail
address and an App Password (16-char Google-issued credential). The
ciphertext is decrypted on demand via :mod:`jyry.services.crypto`, used for
one ``smtp.send`` call, and never logged.

Errors are classified into transient vs permanent so the dispatcher knows
whether a queue retry is worthwhile:

* ``SendOutcome.SENT`` — server accepted the message (250 OK).
* ``SendOutcome.TRANSIENT`` — 4xx response, ``ConnectionError``, or
  ``TimeoutError``: retry later.
* ``SendOutcome.PERMANENT`` — 5xx response, auth failure, malformed
  recipient: mark the application failed.
"""

from __future__ import annotations

import asyncio
import enum
import logging
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Final

import aiosmtplib
from aiosmtplib.errors import (
    SMTPAuthenticationError,
    SMTPException,
    SMTPRecipientsRefused,
    SMTPResponseException,
    SMTPSenderRefused,
    SMTPTimeoutError,
)

from jyry.config import Settings

logger = logging.getLogger(__name__)

_SMTP_TIMEOUT: Final[float] = 30.0


class SendOutcome(enum.Enum):
    SENT = "sent"
    TRANSIENT = "transient"
    PERMANENT = "permanent"


@dataclass(frozen=True, slots=True)
class Attachment:
    filename: str
    content: bytes
    mime_type: str = "application/octet-stream"


@dataclass(frozen=True, slots=True)
class SendResult:
    outcome: SendOutcome
    smtp_code: int | None = None
    detail: str | None = None
    message_id: str | None = None


def _build_message(
    *,
    sender_email: str,
    sender_name: str | None,
    to_email: str,
    subject: str,
    body: str,
    attachments: list[Attachment],
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((sender_name, sender_email)) if sender_name else sender_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=sender_email.partition("@")[2] or "gmail.com")
    msg.set_content(body, subtype="plain", charset="utf-8")
    for att in attachments:
        maintype, _, subtype = att.mime_type.partition("/")
        msg.add_attachment(
            att.content,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=att.filename,
        )
    return msg


def _classify(exc: BaseException) -> SendResult:
    if isinstance(exc, SMTPAuthenticationError):
        return SendResult(SendOutcome.PERMANENT, exc.code, str(exc))
    if isinstance(exc, SMTPRecipientsRefused | SMTPSenderRefused):
        code = getattr(exc, "code", None)
        return SendResult(SendOutcome.PERMANENT, code, str(exc))
    if isinstance(exc, SMTPResponseException):
        code = exc.code
        if 400 <= code < 500:
            return SendResult(SendOutcome.TRANSIENT, code, str(exc))
        return SendResult(SendOutcome.PERMANENT, code, str(exc))
    if isinstance(exc, SMTPTimeoutError | TimeoutError | asyncio.TimeoutError | ConnectionError):
        return SendResult(SendOutcome.TRANSIENT, None, str(exc))
    if isinstance(exc, SMTPException):
        return SendResult(SendOutcome.TRANSIENT, None, str(exc))
    raise exc  # let truly unexpected errors propagate


class GmailSender:
    """One instance per (user, send-attempt). Stateless across calls."""

    def __init__(
        self,
        settings: Settings,
        *,
        sender_email: str,
        app_password: str,
        sender_name: str | None = None,
        timeout: float = _SMTP_TIMEOUT,
    ) -> None:
        self._settings = settings
        self._sender_email = sender_email
        self._app_password = app_password
        self._sender_name = sender_name
        self._timeout = timeout

    async def send(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        attachments: list[Attachment] | None = None,
    ) -> SendResult:
        msg = _build_message(
            sender_email=self._sender_email,
            sender_name=self._sender_name,
            to_email=to_email,
            subject=subject,
            body=body,
            attachments=attachments or [],
        )
        message_id = msg["Message-ID"]
        try:
            await aiosmtplib.send(
                msg,
                hostname=self._settings.smtp_host,
                port=self._settings.smtp_port,
                start_tls=self._settings.smtp_starttls,
                username=self._sender_email,
                password=self._app_password,
                timeout=self._timeout,
            )
        except Exception as exc:
            result = _classify(exc)
            logger.warning(
                "smtp send failed for user=%s outcome=%s code=%s",
                self._sender_email,
                result.outcome.value,
                result.smtp_code,
            )
            return result
        return SendResult(SendOutcome.SENT, smtp_code=250, message_id=message_id)
