"""Account routing independent from concrete calendar providers."""

from collections.abc import Mapping

from ..config import CalendarAccountSettings, Settings
from ..domain.ports import CalendarClient, CalendarClientFactory
from ..models import CalendarInfo


class CalendarService:
    """Resolve accounts and cache their provider clients for one process."""

    def __init__(
        self,
        settings: Settings,
        clients: Mapping[str, CalendarClient] | None = None,
        factory: CalendarClientFactory | None = None,
    ) -> None:
        self.settings = settings
        self._clients = dict(clients or {})
        self._factory = factory

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
            if self._factory is None:
                raise RuntimeError("Calendar client factory is not configured")
            client = self._factory.build(self.settings, account)
            self._clients[account.account_id] = client
        return account, client

    def list_calendars(
        self,
        account_id: str | None,
    ) -> tuple[CalendarAccountSettings, list[CalendarInfo]]:
        account, client = self.resolve(account_id)
        return account, client.list_calendars()
