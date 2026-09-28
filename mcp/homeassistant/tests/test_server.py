import os
import sys
import tempfile
import unittest
from pathlib import Path

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


class ServerTests(unittest.TestCase):
    def test_public_tool_contract(self):
        server = create_server()
        self.assertEqual(
            set(server._tool_manager._tools),
            {
                "ha_call_service",
                "ha_find_entities",
                "ha_get_state",
                "ha_status",
                "ha_toggle",
                "ha_turn_off",
                "ha_turn_on",
            },
        )


if __name__ == "__main__":
    unittest.main()
