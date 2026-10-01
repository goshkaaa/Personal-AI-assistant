"""Core account settings shared by email application and provider adapters."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeAlias


@dataclass(frozen=True)
class GmailAccountSettings:
    account_id: str
    label: str
    address: str
    credentials_file: Path
    token_file: Path
    allow_send: bool = False
    provider: Literal["gmail"] = field(default="gmail", init=False)


@dataclass(frozen=True)
class ImapSmtpAccountSettings:
    account_id: str
    label: str
    address: str
    username: str
    password_file: Path
    imap_host: str
    smtp_host: str
    provider: Literal["imap_smtp", "yandex", "mailru", "icloud"] = "imap_smtp"
    imap_port: int = 993
    smtp_port: int = 465
    imap_security: Literal["ssl", "starttls"] = "ssl"
    smtp_security: Literal["ssl", "starttls"] = "ssl"
    inbox_mailbox: str = "INBOX"
    drafts_mailbox: str = "Drafts"
    sent_mailbox: str | None = None
    allow_send: bool = False


EmailAccountSettings: TypeAlias = GmailAccountSettings | ImapSmtpAccountSettings
