"""Account routing and provider-independent email operations."""

from collections.abc import Mapping
from typing import Any, Protocol

from .config import (
    EmailAccountSettings,
    EmailSettings,
    GmailAccountSettings,
    ImapSmtpAccountSettings,
)
from .providers.gmail import GmailClient
from .providers.imap_smtp import ImapSmtpClient


class EmailClient(Protocol):
    def search(self, query: str = "", max_results: int = 20) -> list[dict[str, Any]]: ...

    def unread(self, max_results: int = 20) -> list[dict[str, Any]]: ...

    def get_message(self, message_id: str) -> dict[str, Any]: ...

    def get_thread(self, thread_id: str) -> list[dict[str, Any]]: ...

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
    ) -> dict[str, str]: ...

    def create_reply_draft(self, message_id: str, body: str) -> dict[str, str]: ...

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
    ) -> dict[str, str]: ...

    def reply(self, message_id: str, body: str) -> dict[str, str]: ...


class EmailService:
    def __init__(
        self,
        settings: EmailSettings,
        clients: Mapping[str, EmailClient] | None = None,
    ) -> None:
        self.settings = settings
        self._clients = dict(clients or {})

    @classmethod
    def from_env(cls) -> "EmailService":
        return cls(EmailSettings.from_env())

    def list_accounts(self) -> list[dict[str, Any]]:
        return [
            {
                "account_id": account.account_id,
                "label": account.label,
                "address": account.address,
                "provider": account.provider,
                "is_default": account.account_id == self.settings.default_account_id,
                "sending_enabled": account.allow_send,
            }
            for account in self.settings.accounts
        ]

    def search(
        self,
        query: str = "",
        max_results: int = 20,
        account_id: str | None = None,
    ) -> list[dict[str, Any]]:
        account, client = self._resolve(account_id)
        return [self._with_account(item, account) for item in client.search(query, max_results)]

    def unread(
        self,
        max_results: int = 20,
        account_id: str | None = None,
    ) -> list[dict[str, Any]]:
        account, client = self._resolve(account_id)
        return [self._with_account(item, account) for item in client.unread(max_results)]

    def get_message(self, message_id: str, account_id: str | None = None) -> dict[str, Any]:
        account, client = self._resolve(account_id)
        return self._with_account(client.get_message(message_id), account)

    def get_thread(
        self,
        thread_id: str,
        account_id: str | None = None,
    ) -> list[dict[str, Any]]:
        account, client = self._resolve(account_id)
        return [self._with_account(item, account) for item in client.get_thread(thread_id)]

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        account, client = self._resolve(account_id)
        return self._with_account(client.create_draft(to, subject, body, cc), account)

    def create_reply_draft(
        self,
        message_id: str,
        body: str,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        account, client = self._resolve(account_id)
        return self._with_account(client.create_reply_draft(message_id, body), account)

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        account, client = self._resolve(account_id)
        return self._with_account(client.send(to, subject, body, cc), account)

    def reply(
        self,
        message_id: str,
        body: str,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        account, client = self._resolve(account_id)
        return self._with_account(client.reply(message_id, body), account)

    def _resolve(
        self,
        account_id: str | None,
    ) -> tuple[EmailAccountSettings, EmailClient]:
        account = self.settings.account(account_id)
        client = self._clients.get(account.account_id)
        if client is None:
            client = self._build_client(account)
            self._clients[account.account_id] = client
        return account, client

    @staticmethod
    def _build_client(account: EmailAccountSettings) -> EmailClient:
        if isinstance(account, GmailAccountSettings):
            return GmailClient(account)
        if isinstance(account, ImapSmtpAccountSettings):
            return ImapSmtpClient(account)
        raise TypeError(f"Unsupported email account settings: {type(account).__name__}")

    @staticmethod
    def _with_account(result: dict[str, Any], account: EmailAccountSettings) -> dict[str, Any]:
        return {
            **result,
            "account_id": account.account_id,
            "provider": account.provider,
        }
