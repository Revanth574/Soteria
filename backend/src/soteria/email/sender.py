from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Protocol
from urllib import error, request

from soteria.email.config import EmailConfig
from soteria.extraction.errors import ConfigurationError, ExtractionAdapterError

_LOGGER = logging.getLogger(__name__)
_RESEND_API_URL = "https://api.resend.com/emails"


class EmailSender(Protocol):
    def send_magic_link(self, *, to_email: str, magic_link_url: str) -> None:
        """Deliver a signup magic link."""


@dataclass(frozen=True, slots=True)
class EmailMessage:
    subject: str
    text: str
    html: str


class LoggingEmailSender:
    def send_magic_link(self, *, to_email: str, magic_link_url: str) -> None:
        _LOGGER.info(
            "DEV-ONLY signup magic link generated; to_email=%s magic_link_url=%s",
            to_email,
            magic_link_url,
        )


class ResendEmailSender:
    def __init__(self, *, api_key: str, from_address: str) -> None:
        if not api_key:
            raise ConfigurationError("RESEND_API_KEY is required for ResendEmailSender.")
        if not from_address:
            raise ConfigurationError("EMAIL_FROM_ADDRESS is required for ResendEmailSender.")
        self.api_key = api_key
        self.from_address = from_address

    def send_magic_link(self, *, to_email: str, magic_link_url: str) -> None:
        email = build_magic_link_email(magic_link_url=magic_link_url, expires_minutes=30)
        payload = {
            "from": self.from_address,
            "to": [to_email],
            "subject": email.subject,
            "text": email.text,
            "html": email.html,
        }
        body = json.dumps(payload).encode("utf-8")
        resend_request = request.Request(
            _RESEND_API_URL,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(resend_request, timeout=10) as response:
                if response.status >= 400:
                    raise ExtractionAdapterError("Resend email delivery failed.")
        except error.URLError as exc:
            raise ExtractionAdapterError("Resend email delivery failed.") from exc


def create_email_sender(config: EmailConfig) -> EmailSender:
    if config.resend_api_key:
        return ResendEmailSender(
            api_key=config.resend_api_key,
            from_address=config.from_address or "",
        )
    return LoggingEmailSender()


def build_magic_link_email(*, magic_link_url: str, expires_minutes: int) -> EmailMessage:
    subject = "Your Soteria analysis link"
    text = (
        "Use this secure link to keep your Soteria analysis.\n\n"
        f"{magic_link_url}\n\n"
        f"This link expires in {expires_minutes} minutes.\n"
        "If you did not request this, you can ignore this email."
    )
    html = (
        "<p>Use this secure link to keep your Soteria analysis.</p>"
        f'<p><a href="{magic_link_url}">{magic_link_url}</a></p>'
        f"<p>This link expires in {expires_minutes} minutes.</p>"
        "<p>If you did not request this, you can ignore this email.</p>"
    )
    return EmailMessage(subject=subject, text=text, html=html)
