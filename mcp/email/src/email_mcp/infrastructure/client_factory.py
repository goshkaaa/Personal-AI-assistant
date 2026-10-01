"""Construct concrete email provider clients."""

from ..domain.models import (
    EmailAccountSettings,
    GmailAccountSettings,
    ImapSmtpAccountSettings,
)
from ..domain.ports import EmailClient
from ..providers.gmail import GmailClient
from ..providers.imap_smtp import ImapSmtpClient


class DefaultEmailClientFactory:
    def create(self, account: EmailAccountSettings) -> EmailClient:
        if isinstance(account, GmailAccountSettings):
            return GmailClient(account)
        if isinstance(account, ImapSmtpAccountSettings):
            return ImapSmtpClient(account)
        raise TypeError(f"Unsupported email account settings: {type(account).__name__}")
