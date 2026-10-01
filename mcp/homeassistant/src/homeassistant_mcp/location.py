"""Compatibility API and executable entry point for location recording."""

from __future__ import annotations

import logging
import os
import time

from .application.location_service import LocationService as _LocationService
from .application.location_service import normalize_location
from .client import HomeAssistantClient
from .config import LocationSettings
from .domain.ports import HomeAssistantGateway, LocationRepositoryPort
from .infrastructure.location_repository import LocationRepository

LOGGER = logging.getLogger(__name__)


class LocationService(_LocationService):
    """Backward-compatible constructor around the layered application service."""

    def __init__(
        self,
        gateway: HomeAssistantGateway,
        settings: LocationSettings,
        repository: LocationRepositoryPort | None = None,
    ) -> None:
        super().__init__(
            gateway,
            settings,
            repository or LocationRepository(settings.database_path),
        )

    @classmethod
    def from_env(cls) -> "LocationService":
        return cls(HomeAssistantClient.from_env(), LocationSettings.from_env())


def recorder_main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    service = LocationService.from_env()
    if not service.settings.entity_ids:
        raise SystemExit("HOME_ASSISTANT_LOCATION_ENTITIES is empty")

    LOGGER.info(
        "Recording %s every %s seconds; retention is %s hours",
        ", ".join(service.settings.entity_ids),
        service.settings.interval_seconds,
        service.settings.retention_hours,
    )
    while True:
        started = time.monotonic()
        try:
            service.record_all()
        except Exception:
            LOGGER.exception("Location recording cycle failed")
        elapsed = time.monotonic() - started
        time.sleep(max(1, service.settings.interval_seconds - elapsed))


__all__ = ["LocationRepository", "LocationService", "normalize_location", "recorder_main"]
