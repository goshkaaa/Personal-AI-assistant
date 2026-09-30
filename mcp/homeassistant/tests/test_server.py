import os
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from homeassistant_mcp.client import HomeAssistantClient  # noqa: E402
from homeassistant_mcp.config import HomeAssistantSettings  # noqa: E402
from homeassistant_mcp.server import create_server  # noqa: E402


class SettingsTests(unittest.TestCase):
    def test_private_token_file_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / "token"
            token_file.write_text("synthetic-token", encoding="utf-8")
            token_file.chmod(0o600)
            settings = HomeAssistantSettings(
                url="http://homeassistant.test",
                token_file=token_file,
                token_from_environment="",
                allow_write=False,
                timeout_seconds=15,
            )

            self.assertEqual(settings.read_token(), "synthetic-token")

    def test_permissive_token_file_is_rejected(self):
        if os.name == "nt":
            self.skipTest("POSIX file modes are required for this assertion")
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / "token"
            token_file.write_text("synthetic-token", encoding="utf-8")
            token_file.chmod(0o644)
            settings = HomeAssistantSettings(
                url="http://homeassistant.test",
                token_file=token_file,
                token_from_environment="",
                allow_write=False,
                timeout_seconds=15,
            )

            with self.assertRaisesRegex(RuntimeError, "too permissive"):
                settings.read_token()


class WritePolicyTests(unittest.TestCase):
    def settings(self, *, allow_write: bool) -> HomeAssistantSettings:
        return HomeAssistantSettings(
            url="http://homeassistant.test",
            token_file=Path("unused"),
            token_from_environment="synthetic-token",
            allow_write=allow_write,
            timeout_seconds=15,
        )

    def test_writes_fail_closed(self):
        client = HomeAssistantClient(self.settings(allow_write=False))
        with self.assertRaisesRegex(RuntimeError, "writes are disabled"):
            client.call_service("light", "turn_on", "light.desk")

    def test_administrative_service_remains_blocked(self):
        client = HomeAssistantClient(self.settings(allow_write=True))
        with self.assertRaisesRegex(ValueError, "blocked"):
            client.call_service("light", "restart", "light.desk")


class ReverseGeocodingTests(unittest.TestCase):
    @patch("homeassistant_mcp.client.urllib.request.urlopen")
    def test_reverse_geocoder_never_receives_home_assistant_token(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = b'{"display_name":"Example","address":{"city":"Moscow"}}'
        settings = HomeAssistantSettings(
            url="http://homeassistant.test",
            token_file=Path("unused"),
            token_from_environment="highly-secret-token",
            allow_write=False,
            timeout_seconds=15,
            reverse_geocoding_url="https://geocoder.example/reverse",
        )

        result = HomeAssistantClient(settings).reverse_geocode(55.75, 37.62)

        request = urlopen.call_args.args[0]
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(request.full_url).query))
        self.assertNotIn("Authorization", request.headers)
        self.assertNotIn("highly-secret-token", request.full_url)
        self.assertEqual(query["layer"], "address")
        self.assertEqual(query["zoom"], "18")
        self.assertEqual(result["display_name"], "Example")
        self.assertEqual(result["attribution"], "OpenStreetMap contributors")


class ServerTests(unittest.TestCase):
    def test_public_tool_contract(self):
        server = create_server()
        self.assertEqual(
            set(server._tool_manager._tools),
            {
                "ha_call_service",
                "ha_find_entities",
                "ha_get_location",
                "ha_get_location_history",
                "ha_get_state",
                "ha_record_location",
                "ha_status",
                "ha_toggle",
                "ha_turn_off",
                "ha_turn_on",
                "find_entities",
                "get_device",
                "get_entity_history",
                "get_entity_state",
                "get_person_location",
                "list_entities",
            },
        )

    def test_read_and_write_annotations_are_separate(self):
        tools = create_server()._tool_manager._tools
        for name in (
            "find_entities",
            "get_device",
            "get_entity_history",
            "get_entity_state",
            "get_person_location",
            "list_entities",
        ):
            self.assertTrue(tools[name].annotations.read_only_hint, name)
            self.assertFalse(tools[name].annotations.destructive_hint, name)

        for name in ("ha_call_service", "ha_toggle", "ha_turn_off", "ha_turn_on"):
            self.assertFalse(tools[name].annotations.read_only_hint, name)
            self.assertTrue(tools[name].annotations.destructive_hint, name)


if __name__ == "__main__":
    unittest.main()
