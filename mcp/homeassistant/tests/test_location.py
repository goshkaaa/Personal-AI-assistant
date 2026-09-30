import os
import stat
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from homeassistant_mcp.config import LocationSettings  # noqa: E402
from homeassistant_mcp.location import (  # noqa: E402
    LocationRepository,
    LocationService,
    normalize_location,
)


class FakeClient:
    def __init__(self, state):
        self.state = state
        self.requested = []

    def get_state(self, entity_id):
        self.requested.append(entity_id)
        return self.state


def location_at(entity_id: str, recorded_at: datetime, latitude: float) -> dict:
    return {
        "entity_id": entity_id,
        "recorded_at": recorded_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "ha_last_updated": recorded_at.isoformat(),
        "state": "not_home",
        "latitude": latitude,
        "longitude": 37.62,
        "gps_accuracy_m": 12.0,
        "source": "device_tracker.phone",
    }


class LocationNormalizationTests(unittest.TestCase):
    def test_normalizes_coordinates_and_adds_map_link(self):
        result = normalize_location(
            "person.example",
            {
                "state": "home",
                "last_updated": datetime.now(UTC).isoformat(),
                "attributes": {
                    "friendly_name": "Example",
                    "latitude": "55.75",
                    "longitude": 37.62,
                    "gps_accuracy": 15,
                    "source": "device_tracker.phone",
                },
            },
        )

        self.assertEqual(result["entity_id"], "person.example")
        self.assertEqual(result["latitude"], 55.75)
        self.assertIn("55.750000", result["map_url"])
        self.assertGreaterEqual(result["position_age_minutes"], 0)

    def test_rejects_missing_coordinates(self):
        with self.assertRaisesRegex(RuntimeError, "latitude"):
            normalize_location("person.example", {"state": "unknown", "attributes": {}})


class LocationRepositoryTests(unittest.TestCase):
    def test_history_is_chronological_and_pruned(self):
        with tempfile.TemporaryDirectory() as tmp:
            repository = LocationRepository(Path(tmp) / "private" / "locations.db")
            repository.initialize()
            now = datetime(2026, 9, 29, 12, tzinfo=UTC)
            repository.add(location_at("person.example", now - timedelta(hours=74), 55.70))
            repository.add(location_at("person.example", now - timedelta(hours=2), 55.71))
            repository.add(location_at("person.example", now - timedelta(hours=1), 55.72))

            self.assertEqual(repository.prune(72, now=now), 1)
            points = repository.history("person.example", 24, 10, now=now)

            self.assertEqual([point["latitude"] for point in points], [55.71, 55.72])
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(repository.path.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(repository.path.parent.stat().st_mode), 0o700)


class LocationServiceTests(unittest.TestCase):
    def test_single_configured_entity_can_be_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = LocationSettings(
                database_path=Path(tmp) / "locations.db",
                entity_ids=("person.example",),
                interval_seconds=600,
                retention_hours=72,
            )
            client = FakeClient(
                {
                    "state": "work",
                    "attributes": {"latitude": 55.75, "longitude": 37.62},
                }
            )
            service = LocationService(client, settings)

            result = service.record()

            self.assertEqual(client.requested, ["person.example"])
            self.assertEqual(result["state"], "work")
            self.assertEqual(service.history()["point_count"], 1)


if __name__ == "__main__":
    unittest.main()
