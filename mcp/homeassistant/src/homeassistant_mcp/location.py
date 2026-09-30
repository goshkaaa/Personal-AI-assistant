"""Private, short-lived location history for Home Assistant people and trackers."""

from __future__ import annotations

import logging
import math
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .client import HomeAssistantClient
from .config import LocationSettings

LOGGER = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS location_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    ha_last_updated TEXT,
    state TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    gps_accuracy REAL,
    source TEXT
);
CREATE INDEX IF NOT EXISTS idx_location_points_entity_time
ON location_points(entity_id, recorded_at);
"""


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
        "map_url": f"https://www.openstreetmap.org/?mlat={latitude:.6f}&mlon={longitude:.6f}#map=16/{latitude:.6f}/{longitude:.6f}",
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


class LocationRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=30000")
            self._secure_files()
            with connection:
                yield connection
        finally:
            connection.close()
            self._secure_files()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def add(self, location: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO location_points (
                    entity_id, recorded_at, ha_last_updated, state,
                    latitude, longitude, gps_accuracy, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    location["entity_id"],
                    location["recorded_at"],
                    location.get("ha_last_updated"),
                    location["state"],
                    location["latitude"],
                    location["longitude"],
                    location.get("gps_accuracy_m"),
                    location.get("source"),
                ),
            )

    def prune(self, retention_hours: int, *, now: datetime | None = None) -> int:
        cutoff = (now or _utc_now()) - timedelta(hours=retention_hours)
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM location_points WHERE recorded_at < ?",
                (_isoformat(cutoff),),
            )
            return cursor.rowcount

    def history(
        self,
        entity_id: str,
        hours: int,
        limit: int,
        *,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        since = (now or _utc_now()) - timedelta(hours=hours)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT recorded_at, ha_last_updated, state, latitude, longitude,
                       gps_accuracy, source
                FROM (
                    SELECT id, recorded_at, ha_last_updated, state, latitude, longitude,
                           gps_accuracy, source
                    FROM location_points
                    WHERE entity_id = ? AND recorded_at >= ?
                    ORDER BY recorded_at DESC, id DESC
                    LIMIT ?
                )
                ORDER BY recorded_at, id
                """,
                (entity_id, _isoformat(since), limit),
            ).fetchall()
        return [
            {
                "recorded_at": row["recorded_at"],
                "ha_last_updated": row["ha_last_updated"],
                "state": row["state"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "gps_accuracy_m": row["gps_accuracy"],
                "source": row["source"],
            }
            for row in rows
        ]

    def _secure_files(self) -> None:
        for path in (self.path, Path(f"{self.path}-wal"), Path(f"{self.path}-shm")):
            if path.exists():
                with suppress(OSError):
                    path.chmod(0o600)


class LocationService:
    def __init__(
        self,
        client: HomeAssistantClient,
        settings: LocationSettings,
        repository: LocationRepository | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.repository = repository or LocationRepository(settings.database_path)
        self.repository.initialize()

    @classmethod
    def from_env(cls) -> "LocationService":
        return cls(HomeAssistantClient.from_env(), LocationSettings.from_env())

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
        return normalize_location(resolved, self.client.get_state(resolved))

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
