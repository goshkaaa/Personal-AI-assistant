"""Build a registry-enriched snapshot from Home Assistant data."""

from __future__ import annotations

from typing import Any

from ..domain.models import EntityRecord, RegistrySnapshot
from ..domain.ports import HomeAssistantGateway
from .text_search import TextSearch


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


class EntityCatalog:
    """Loads and joins state, entity, device, and area registries."""

    def __init__(
        self,
        gateway: HomeAssistantGateway,
        text: TextSearch | None = None,
    ) -> None:
        self.gateway = gateway
        self.text = text or TextSearch()

    def snapshot(self) -> RegistrySnapshot:
        states = self.gateway.list_states()
        registry_available = True
        try:
            registries = self.gateway.get_registries()
        except RuntimeError:
            registries = {"entities": [], "devices": [], "areas": []}
            registry_available = False
        return self.build(states, registries, registry_available=registry_available)

    def build(
        self,
        states: list[dict[str, Any]],
        registries: dict[str, list[dict[str, Any]]],
        *,
        registry_available: bool,
    ) -> RegistrySnapshot:
        state_by_id = self._index(states, "entity_id")
        entity_registry = self._index(registries.get("entities", []), "entity_id")
        devices = self._index(registries.get("devices", []), "id")
        areas = self._index_areas(registries.get("areas", []))

        records = tuple(
            self._record(
                entity_id,
                state_by_id.get(entity_id, {}),
                entity_registry.get(entity_id, {}),
                devices,
                areas,
            )
            for entity_id in sorted(set(state_by_id) | set(entity_registry))
        )
        return RegistrySnapshot(records, devices, areas, registry_available)

    @staticmethod
    def _index(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
        return {
            str(item[key]): item
            for item in _as_list(items)
            if isinstance(item, dict) and item.get(key)
        }

    @staticmethod
    def _index_areas(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}
        for item in _as_list(items):
            if not isinstance(item, dict):
                continue
            area_id = item.get("area_id") or item.get("id")
            if area_id:
                indexed[str(area_id)] = item
        return indexed

    def _record(
        self,
        entity_id: str,
        state: dict[str, Any],
        registry: dict[str, Any],
        devices: dict[str, dict[str, Any]],
        areas: dict[str, dict[str, Any]],
    ) -> EntityRecord:
        attributes = state.get("attributes") or {}
        device_id = registry.get("device_id") or attributes.get("device_id")
        device = devices.get(str(device_id)) if device_id else None
        area_id = registry.get("area_id") or (device or {}).get("area_id")
        area = areas.get(str(area_id)) if area_id else None
        name = (
            registry.get("name")
            or attributes.get("friendly_name")
            or registry.get("original_name")
            or entity_id
        )
        device_name = (device or {}).get("name_by_user") or (device or {}).get("name")
        area_name = (area or {}).get("name")
        aliases = tuple(
            dict.fromkeys(
                [
                    *[str(value) for value in _as_list(registry.get("aliases"))],
                    *[str(value) for value in _as_list((device or {}).get("aliases"))],
                    *[str(value) for value in _as_list((area or {}).get("aliases"))],
                ]
            )
        )
        record = EntityRecord(
            entity_id=entity_id,
            domain=entity_id.partition(".")[0],
            name=str(name),
            original_name=registry.get("original_name"),
            aliases=aliases,
            state=state.get("state"),
            last_changed=state.get("last_changed"),
            last_updated=state.get("last_updated"),
            attributes=attributes,
            registry=registry,
            device_id=str(device_id) if device_id else None,
            device_name=str(device_name) if device_name else None,
            area_id=str(area_id) if area_id else None,
            area_name=str(area_name) if area_name else None,
            device_class=attributes.get("device_class") or registry.get("device_class"),
        )
        record.search_entity = self.text.searchable(
            entity_id,
            name,
            registry.get("original_name"),
            *aliases,
        )
        record.search_device = self.text.searchable(device_name)
        record.search_area = self.text.searchable(
            area_name,
            *[str(value) for value in _as_list((area or {}).get("aliases"))],
        )
        return record
