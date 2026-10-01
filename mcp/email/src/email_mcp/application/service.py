"""Account routing and provider-independent email operations."""

from collections.abc import Mapping
from typing import Any

from ..config import EmailSettings
from ..domain.models import EmailAccountSettings
from ..domain.ports import EmailClient, EmailClientFactory


class EmailService:
    def __init__(
        self,
        settings: EmailSettings,
        clients: Mapping[str, EmailClient] | None = None,
        factory: EmailClientFactory | None = None,
    ) -> None:
        self.settings = settings
        self._clients = dict(clients or {})
        self._factory = factory

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
        *,
        user_confirmed: bool = False,
    ) -> dict[str, Any]:
        account = self.settings.account(account_id)
        if not account.allow_send:
            return self._send_policy_result(
                "disabled",
                account.account_id,
                "Email sending is disabled in the selected account configuration.",
            )
        if not user_confirmed:
            return self._send_policy_result(
                "confirmation_required",
                account.account_id,
                "Explicit user confirmation is required before sending. Create a draft instead.",
            )
        account, client = self._resolve(account.account_id)
        return self._with_account(client.send(to, subject, body, cc), account)

    def reply(
        self,
        message_id: str,
        body: str,
        account_id: str | None = None,
        *,
        user_confirmed: bool = False,
    ) -> dict[str, Any]:
        account = self.settings.account(account_id)
        if not account.allow_send:
            return self._send_policy_result(
                "disabled",
                account.account_id,
                "Email sending is disabled in the selected account configuration.",
            )
        if not user_confirmed:
            return self._send_policy_result(
                "confirmation_required",
                account.account_id,
                "Explicit user confirmation is required before sending the reply.",
            )
        account, client = self._resolve(account.account_id)
        return self._with_account(client.reply(message_id, body), account)

    @staticmethod
    def _send_policy_result(status: str, account_id: str, message: str) -> dict[str, str]:
        return {"status": status, "account_id": account_id, "message": message}

    def _resolve(
        self,
        account_id: str | None,
    ) -> tuple[EmailAccountSettings, EmailClient]:
        account = self.settings.account(account_id)
        client = self._clients.get(account.account_id)
        if client is None:
            if self._factory is None:
                raise RuntimeError("An EmailClientFactory is required to open an account")
            client = self._factory.create(account)
            self._clients[account.account_id] = client
        return account, client

    @staticmethod
    def _with_account(result: dict[str, Any], account: EmailAccountSettings) -> dict[str, Any]:
        return {
            **result,
            "account_id": account.account_id,
            "provider": account.provider,
        }
