"""Backward-compatible account-service API."""

from collections.abc import Mapping

from .application.accounts import CalendarService as _CalendarService
from .config import Settings, get_settings
from .domain.ports import CalendarClient, CalendarClientFactory
from .infrastructure.client_factory import DefaultCalendarClientFactory


class CalendarService(_CalendarService):
    """Compatibility facade that supplies the default provider factory."""

    def __init__(
        self,
        settings: Settings,
        clients: Mapping[str, CalendarClient] | None = None,
        factory: CalendarClientFactory | None = None,
    ) -> None:
        super().__init__(settings, clients, factory or DefaultCalendarClientFactory())

    @classmethod
    def from_env(cls) -> "CalendarService":
        return cls(get_settings())


__all__ = ["CalendarClient", "CalendarService"]
