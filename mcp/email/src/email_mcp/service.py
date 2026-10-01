"""Backward-compatible import path for the application email service."""

from .application.service import EmailService as _EmailService
from .config import EmailSettings
from .domain.models import EmailAccountSettings, GmailAccountSettings, ImapSmtpAccountSettings
from .domain.ports import EmailClient
from .infrastructure.client_factory import DefaultEmailClientFactory


class EmailService(_EmailService):
    @classmethod
    def from_env(cls) -> "EmailService":
        return cls(EmailSettings.from_env(), factory=DefaultEmailClientFactory())


__all__ = [
    "EmailAccountSettings",
    "EmailClient",
    "EmailSettings",
    "EmailService",
    "GmailAccountSettings",
    "ImapSmtpAccountSettings",
]
