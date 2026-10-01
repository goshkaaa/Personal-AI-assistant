"""Backward-compatible import for the layered read application service."""

from dataclasses import asdict
from typing import Any

from .application.read_service import HomeAssistantReadService as _ReadService
from .client import HomeAssistantClient


class HomeAssistantReadService(_ReadService):
    """Compatibility facade; new code should use ``application.read_service``."""

    def snapshot(self) -> dict[str, Any]:
        snapshot = super().snapshot()
        records = []
        for record in snapshot.records:
            serialized = asdict(record)
            serialized["aliases"] = list(record.aliases)
            records.append(serialized)
        return {
            "records": records,
            "devices": snapshot.devices,
            "areas": snapshot.areas,
            "registry_available": snapshot.registry_available,
        }

    @classmethod
    def from_env(cls) -> "HomeAssistantReadService":
        return cls(HomeAssistantClient.from_env())


__all__ = ["HomeAssistantReadService"]
