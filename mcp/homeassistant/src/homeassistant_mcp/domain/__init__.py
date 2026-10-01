"""Domain objects and ports for the Home Assistant MCP."""

from .models import EntityMatch, EntityRecord, EntityResolution, RegistrySnapshot
from .ports import HomeAssistantGateway, LocationRepositoryPort

__all__ = [
    "EntityMatch",
    "EntityRecord",
    "EntityResolution",
    "HomeAssistantGateway",
    "LocationRepositoryPort",
    "RegistrySnapshot",
]
