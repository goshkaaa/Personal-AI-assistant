"""Infrastructure adapters for Home Assistant and local persistence."""

from .home_assistant import HomeAssistantClient
from .location_repository import LocationRepository

__all__ = ["HomeAssistantClient", "LocationRepository"]
