"""Application-facing ports implemented by infrastructure adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class HomeAssistantGateway(Protocol):
    """Operations required by Home Assistant application services."""

    def status(self) -> dict[str, Any]: ...

    def get_state(self, entity_id: str) -> dict[str, Any]: ...

    def list_states(self) -> list[dict[str, Any]]: ...

    def get_registries(self) -> dict[str, list[dict[str, Any]]]: ...

    def get_history(
        self,
        entity_id: str,
        start: datetime,
        end: datetime,
        *,
        minimal_response: bool = True,
    ) -> list[dict[str, Any]]: ...

    def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any] | None: ...

    def find_entities(
        self,
        query: str = "",
        domain: str = "",
        limit: int = 30,
    ) -> list[dict[str, Any]]: ...

    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: str = "",
        data_json: str = "{}",
    ) -> dict[str, Any]: ...


class LocationRepositoryPort(Protocol):
    """Persistence boundary for the bounded location history."""

    def initialize(self) -> None: ...

    def add(self, location: dict[str, Any]) -> None: ...

    def prune(self, retention_hours: int, *, now: datetime | None = None) -> int: ...

    def history(
        self,
        entity_id: str,
        hours: int,
        limit: int,
        *,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]: ...
