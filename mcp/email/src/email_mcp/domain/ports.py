"""Ports implemented by email infrastructure adapters."""

from typing import Any, Protocol

from .models import EmailAccountSettings


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


class EmailClientFactory(Protocol):
    def create(self, account: EmailAccountSettings) -> EmailClient: ...
