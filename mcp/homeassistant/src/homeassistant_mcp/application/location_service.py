"""Location tracking use cases independent of storage and transport details."""

import logging
import math
from datetime import UTC, datetime
from typing import Any

from ..config import LocationSettings
from ..domain.ports import HomeAssistantGateway, LocationRepositoryPort

LOGGER = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _isoformat(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _coordinate(value: Any, name: str, minimum: float, maximum: float) -> float:
    try:
        coordinate = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Home Assistant entity has no valid {name}") from exc
    if not math.isfinite(coordinate) or not minimum <= coordinate <= maximum:
        raise RuntimeError(f"Home Assistant entity has no valid {name}")
    return coordinate


def normalize_location(entity_id: str, state: dict[str, Any]) -> dict[str, Any]:
    """Return a stable, bot-friendly location record from a HA state object."""
    attributes = state.get("attributes") or {}
    latitude = _coordinate(attributes.get("latitude"), "latitude", -90, 90)
    longitude = _coordinate(attributes.get("longitude"), "longitude", -180, 180)
    gps_accuracy = attributes.get("gps_accuracy")
    try:
        gps_accuracy = float(gps_accuracy) if gps_accuracy is not None else None
    except (TypeError, ValueError):
        gps_accuracy = None

    recorded_at = _utc_now()
    last_updated = state.get("last_updated") or state.get("last_changed")
    result = {
        "entity_id": entity_id,
        "name": attributes.get("friendly_name") or entity_id,
        "state": str(state.get("state") or "unknown"),
        "latitude": latitude,
        "longitude": longitude,
        "gps_accuracy_m": gps_accuracy,
        "source": attributes.get("source"),
        "ha_last_updated": last_updated,
        "recorded_at": _isoformat(recorded_at),
        "map_url": (
            "https://www.openstreetmap.org/"
            f"?mlat={latitude:.6f}&mlon={longitude:.6f}"
            f"#map=16/{latitude:.6f}/{longitude:.6f}"
        ),
    }
    if last_updated:
        try:
            parsed = datetime.fromisoformat(str(last_updated).replace("Z", "+00:00"))
            result["position_age_minutes"] = max(
                0,
                round((recorded_at - parsed.astimezone(UTC)).total_seconds() / 60, 1),
            )
        except ValueError:
            pass
    return result


class LocationService:
    """Coordinates current location reads with bounded location persistence."""

    def __init__(
        self,
        gateway: HomeAssistantGateway,
        settings: LocationSettings,
        repository: LocationRepositoryPort,
    ) -> None:
        self.gateway = gateway
        self.settings = settings
        self.repository = repository
        self.repository.initialize()

    def resolve_entity(self, entity_id: str = "") -> str:
        entity_id = entity_id.strip()
        if entity_id:
            return entity_id
        if len(self.settings.entity_ids) == 1:
            return self.settings.entity_ids[0]
        if not self.settings.entity_ids:
            raise RuntimeError("No tracked location entity is configured")
        raise RuntimeError("entity_id is required when multiple location entities are configured")

    def current(self, entity_id: str = "") -> dict[str, Any]:
        resolved = self.resolve_entity(entity_id)
        return normalize_location(resolved, self.gateway.get_state(resolved))

    def record(self, entity_id: str = "") -> dict[str, Any]:
        location = self.current(entity_id)
        self.repository.add(location)
        self.repository.prune(self.settings.retention_hours)
        return location

    def record_all(self) -> list[dict[str, Any]]:
        if not self.settings.entity_ids:
            raise RuntimeError("HOME_ASSISTANT_LOCATION_ENTITIES is empty")
        recorded = []
        for entity_id in self.settings.entity_ids:
            try:
                recorded.append(self.record(entity_id))
            except Exception:
                LOGGER.exception("Could not record location for %s", entity_id)
        if not recorded:
            raise RuntimeError("No configured Home Assistant location could be recorded")
        return recorded

    def history(self, entity_id: str = "", hours: int = 24, limit: int = 432) -> dict[str, Any]:
        resolved = self.resolve_entity(entity_id)
        hours = max(1, min(hours, self.settings.retention_hours))
        limit = max(1, min(limit, 1000))
        points = self.repository.history(resolved, hours, limit)
        return {
            "entity_id": resolved,
            "hours": hours,
            "retention_hours": self.settings.retention_hours,
            "point_count": len(points),
            "points": points,
        }
