"""Reviewed defaults for common standards-based email providers."""

from dataclasses import dataclass
from typing import Literal

TransportSecurity = Literal["ssl", "starttls"]


@dataclass(frozen=True)
class ImapSmtpPreset:
    imap_host: str
    imap_port: int
    imap_security: TransportSecurity
    smtp_host: str
    smtp_port: int
    smtp_security: TransportSecurity
    drafts_mailbox: str = "Drafts"
    sent_mailbox: str | None = None


IMAP_SMTP_PRESETS: dict[str, ImapSmtpPreset] = {
    "yandex": ImapSmtpPreset(
        imap_host="imap.yandex.ru",
        imap_port=993,
        imap_security="ssl",
        smtp_host="smtp.yandex.ru",
        smtp_port=465,
        smtp_security="ssl",
    ),
    "mailru": ImapSmtpPreset(
        imap_host="imap.mail.ru",
        imap_port=993,
        imap_security="ssl",
        smtp_host="smtp.mail.ru",
        smtp_port=465,
        smtp_security="ssl",
    ),
    "icloud": ImapSmtpPreset(
        imap_host="imap.mail.me.com",
        imap_port=993,
        imap_security="ssl",
        smtp_host="smtp.mail.me.com",
        smtp_port=587,
        smtp_security="starttls",
    ),
}
