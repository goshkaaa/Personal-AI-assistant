"""Typed domain models independent from MCP and network transports."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EntityRecord:
    """An entity enriched with registry, device, and area context."""

    entity_id: str
    domain: str
    name: str
    original_name: str | None
    aliases: tuple[str, ...]
    state: Any
    last_changed: str | None
    last_updated: str | None
    attributes: dict[str, Any]
    registry: dict[str, Any]
    device_id: str | None
    device_name: str | None
    area_id: str | None
    area_name: str | None
    device_class: str | None
    search_entity: str = ""
    search_device: str = ""
    search_area: str = ""


@dataclass(slots=True)
class RegistrySnapshot:
    """A consistent in-memory view of live states and HA registries."""

    records: tuple[EntityRecord, ...]
    devices: dict[str, dict[str, Any]] = field(default_factory=dict)
    areas: dict[str, dict[str, Any]] = field(default_factory=dict)
    registry_available: bool = True


@dataclass(frozen=True, slots=True)
class EntityMatch:
    """A ranked entity candidate with explainable scoring."""

    score: int
    record: EntityRecord
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EntityResolution:
    """Resolution result used by read-only application services."""

    record: EntityRecord | None
    matches: tuple[EntityMatch, ...]
    ambiguous: bool
