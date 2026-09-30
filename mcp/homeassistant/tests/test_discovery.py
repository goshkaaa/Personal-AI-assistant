import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from homeassistant_mcp.discovery import HomeAssistantReadService  # noqa: E402


class FakeClient:
    def __init__(self) -> None:
        self.history_entity = ""

    def list_states(self) -> list[dict[str, Any]]:
        now = "2026-09-30T09:00:00+00:00"
        return [
            {
                "entity_id": "person.ivan",
                "state": "not_home",
                "attributes": {
                    "friendly_name": "Иван",
                    "latitude": 55.75,
                    "longitude": 37.62,
                    "gps_accuracy": 15,
                },
                "last_changed": now,
                "last_updated": now,
            },
            {
                "entity_id": "device_tracker.ivan_phone",
                "state": "home",
                "attributes": {"friendly_name": "Телефон Ивана"},
                "last_changed": now,
                "last_updated": now,
            },
            {
                "entity_id": "sensor.ivan_phone_battery",
                "state": "73",
                "attributes": {
                    "friendly_name": "Заряд телефона Ивана",
                    "device_class": "battery",
                    "unit_of_measurement": "%",
                },
                "last_changed": now,
                "last_updated": now,
            },
            {
                "entity_id": "light.bathroom",
                "state": "off",
                "attributes": {"friendly_name": "Свет"},
                "last_changed": now,
                "last_updated": now,
            },
            {
                "entity_id": "light.bedroom",
                "state": "on",
                "attributes": {"friendly_name": "Свет"},
                "last_changed": now,
                "last_updated": now,
            },
            {
                "entity_id": "sensor.home_temperature",
                "state": "22.4",
                "attributes": {
                    "friendly_name": "Температура дома",
                    "device_class": "temperature",
                    "unit_of_measurement": "°C",
                },
                "last_changed": now,
                "last_updated": now,
            },
            {
                "entity_id": "switch.offline",
                "state": "unavailable",
                "attributes": {"friendly_name": "Offline plug"},
                "last_changed": now,
                "last_updated": now,
            },
        ]

    def get_registries(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "areas": [
                {"area_id": "bathroom", "name": "Ванная"},
                {"area_id": "bedroom", "name": "Спальня"},
            ],
            "devices": [
                {"id": "phone-1", "name": "Телефон Ивана", "manufacturer": "Example"},
                {"id": "light-1", "name": "Bathroom relay", "area_id": "bathroom"},
                {"id": "light-2", "name": "Bedroom relay", "area_id": "bedroom"},
            ],
            "entities": [
                {"entity_id": "person.ivan", "original_name": "Ivan"},
                {"entity_id": "device_tracker.ivan_phone", "device_id": "phone-1"},
                {"entity_id": "sensor.ivan_phone_battery", "device_id": "phone-1"},
                {"entity_id": "light.bathroom", "device_id": "light-1"},
                {"entity_id": "light.bedroom", "device_id": "light-2"},
                {"entity_id": "sensor.home_temperature"},
                {"entity_id": "switch.offline"},
            ],
        }

    def reverse_geocode(self, latitude: float, longitude: float) -> dict[str, Any]:
        return {
            "display_name": "Example address",
            "address": {"city": "Moscow"},
        }

    def get_history(
        self,
        entity_id: str,
        start: datetime,
        end: datetime,
        *,
        minimal_response: bool,
    ) -> list[dict[str, Any]]:
        self.history_entity = entity_id
        return [{"state": "21.9", "last_updated": start.astimezone(UTC).isoformat()}]


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.service = HomeAssistantReadService(self.client)  # type: ignore[arg-type]

    def test_resolves_cyrillic_person_name_without_hardcoded_entity(self):
        result = self.service.get_person_location("Иван")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["entity_id"], "person.ivan")
        self.assertEqual(result["latitude"], 55.75)
        self.assertEqual(result["state"], "not_home")
        self.assertIsNone(result["zone"])
        self.assertTrue(result["outside_configured_home_zone"])
        self.assertIn("does not describe", result["state_interpretation"])
        self.assertIn("Do not mention", result["state_interpretation"])
        self.assertEqual(result["address"], "Example address")
        self.assertEqual(result["address_details"], {"city": "Moscow"})
        self.assertIn("openstreetmap.org", result["map_url"])

    def test_finds_battery_sensor_through_device_relationship(self):
        result = self.service.find_entities("какой заряд телефона Ивана")

        self.assertEqual(result["matches"][0]["entity_id"], "sensor.ivan_phone_battery")

    def test_area_context_disambiguates_light(self):
        result = self.service.find_entities("включен ли свет в ванной")

        self.assertEqual(result["matches"][0]["entity_id"], "light.bathroom")
        self.assertFalse(result["ambiguous"])

    def test_lists_unavailable_and_unknown_states(self):
        result = self.service.list_entities(state="unavailable,unknown")

        self.assertEqual(result["match_count"], 1)
        self.assertEqual(result["entities"][0]["entity_id"], "switch.offline")

    def test_reads_state_with_registry_context(self):
        result = self.service.get_entity_state("light.bathroom")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["state"], "off")
        self.assertEqual(result["area"]["name"], "Ванная")

    def test_reads_bounded_history(self):
        result = self.service.get_entity_history(
            "sensor.home_temperature",
            start="2026-09-29T00:00:00Z",
            end="2026-09-30T00:00:00Z",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["point_count"], 1)
        self.assertEqual(self.client.history_entity, "sensor.home_temperature")


if __name__ == "__main__":
    unittest.main()
