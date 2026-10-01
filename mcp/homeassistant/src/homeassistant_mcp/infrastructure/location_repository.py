"""SQLite adapter for private, short-lived location history."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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


class LocationRepository:
    """SQLite implementation that enforces private file permissions."""

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
