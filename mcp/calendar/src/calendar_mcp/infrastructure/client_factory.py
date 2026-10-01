"""Factory for concrete Google Calendar and CalDAV clients."""

from __future__ import annotations

from ..config import (
    CalDavAccountSettings,
    CalendarAccountSettings,
    GoogleAccountSettings,
    Settings,
)
from ..domain.ports import CalendarClient
from ..providers.caldav import CalDavCalendarService
from ..providers.google import GoogleCalendarService


class DefaultCalendarClientFactory:
    def build(
        self,
        settings: Settings,
        account: CalendarAccountSettings,
    ) -> CalendarClient:
        if isinstance(account, CalDavAccountSettings):
            return CalDavCalendarService(settings, account)
        if isinstance(account, GoogleAccountSettings):
            return GoogleCalendarService(settings, account)
        raise TypeError(f"Unsupported calendar account settings: {type(account).__name__}")
