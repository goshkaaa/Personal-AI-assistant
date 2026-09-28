"""Provider-independent calendar account routing."""

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol

from .config import (
    CalDavAccountSettings,
    CalendarAccountSettings,
    GoogleAccountSettings,
    Settings,
    get_settings,
)
from .models import CalendarInfo, EventRecord
from .providers.caldav import CalDavCalendarService
from .providers.google import GoogleCalendarService


class CalendarClient(Protocol):
    def list_calendars(self) -> list[CalendarInfo]: ...

    def search_events(
        self,
        start: datetime,
        end: datetime,
        *,
        calendar_id: str = "",
        query: str = "",
        include_notes: bool = False,
        limit: int,
    ) -> tuple[list[EventRecord], bool]: ...

    def create_event(
        self,
        payload: dict[str, object],
        *,
        uid: str,
    ) -> tuple[str, bool]: ...

    def require_calendar(self, calendar_id: str) -> CalendarInfo: ...


class CalendarService:
    def __init__(
        self,
        settings: Settings,
        clients: Mapping[str, CalendarClient] | None = None,
    ) -> None:
        self.settings = settings
        self._clients = dict(clients or {})

    @classmethod
    def from_env(cls) -> "CalendarService":
        return cls(get_settings())

    def list_accounts(self) -> list[dict[str, object]]:
        return [
            {
                "account_id": account.account_id,
                "label": account.label,
                "provider": account.provider,
                "timezone": account.timezone_name,
                "is_default": account.account_id == self.settings.default_account_id,
                "write_enabled": account.write_enabled,
                "write_calendar_configured": bool(account.write_calendar_id),
                "credentials": account.credential_status(),
            }
            for account in self.settings.accounts
        ]

    def resolve(
        self,
        account_id: str | None,
    ) -> tuple[CalendarAccountSettings, CalendarClient]:
        account = self.settings.account(account_id)
        client = self._clients.get(account.account_id)
        if client is None:
            client = self._build_client(account)
            self._clients[account.account_id] = client
        return account, client

    def list_calendars(
        self,
        account_id: str | None,
    ) -> tuple[CalendarAccountSettings, list[CalendarInfo]]:
        account, client = self.resolve(account_id)
        return account, client.list_calendars()

    def search_events(
        self,
        start: datetime,
        end: datetime,
        *,
        account_id: str | None,
        calendar_id: str,
        query: str = "",
        include_notes: bool = False,
        limit: int,
    ) -> tuple[CalendarAccountSettings, list[EventRecord], bool]:
        account, client = self.resolve(account_id)
        records, truncated = client.search_events(
            start,
            end,
            calendar_id=calendar_id,
            query=query,
            include_notes=include_notes,
            limit=limit,
        )
        return account, records, truncated

    @staticmethod
    def account_result(
        result: dict[str, object],
        account: CalendarAccountSettings,
    ) -> dict[str, object]:
        return {
            **result,
            "account_id": account.account_id,
            "provider": account.provider,
        }

    def _build_client(self, account: CalendarAccountSettings) -> CalendarClient:
        if isinstance(account, CalDavAccountSettings):
            return CalDavCalendarService(self.settings, account)
        if isinstance(account, GoogleAccountSettings):
            return GoogleCalendarService(self.settings, account)
        raise TypeError(f"Unsupported calendar account settings: {type(account).__name__}")
