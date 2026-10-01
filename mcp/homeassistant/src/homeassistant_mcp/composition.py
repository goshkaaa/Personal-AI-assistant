"""Composition root for wiring application services to infrastructure."""

from functools import cached_property

from .application.location_service import LocationService
from .application.read_service import HomeAssistantReadService
from .config import HomeAssistantSettings, LocationSettings
from .infrastructure.home_assistant import HomeAssistantClient
from .infrastructure.location_repository import LocationRepository


class HomeAssistantContainer:
    """Creates one dependency graph per MCP process and reuses it across tools."""

    @cached_property
    def settings(self) -> HomeAssistantSettings:
        return HomeAssistantSettings.from_env()

    @cached_property
    def location_settings(self) -> LocationSettings:
        return LocationSettings.from_env()

    @cached_property
    def gateway(self) -> HomeAssistantClient:
        return HomeAssistantClient(self.settings)

    @cached_property
    def read_service(self) -> HomeAssistantReadService:
        return HomeAssistantReadService(self.gateway)

    @cached_property
    def location_service(self) -> LocationService:
        repository = LocationRepository(self.location_settings.database_path)
        return LocationService(self.gateway, self.location_settings, repository)
