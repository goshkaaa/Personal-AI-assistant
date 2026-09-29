import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from telegram_mcp import app  # noqa: E402
from telegram_mcp.client import TelegramSettings  # noqa: E402
from telegram_mcp.service import TelegramService  # noqa: E402
from telegram_mcp.tasks.database import database  # noqa: E402

EXPECTED_TOOLS = {
    "task_attach_chat",
    "task_cancel",
    "task_create",
    "task_list",
    "task_status",
    "telegram_get_logged_messages",
    "telegram_get_managed_chats",
    "telegram_get_messages",
    "telegram_reply",
    "telegram_resolve_chat",
    "telegram_resolve_phone",
    "telegram_search_chats",
    "telegram_send_message",
}


class ArchitectureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        temporary_path = Path(self.temporary.name)
        database.path = temporary_path / "conversations.db"
        self.previous_token_file = os.environ.get("MCP_TOKEN_FILE")
        os.environ["MCP_TOKEN_FILE"] = str(temporary_path / "mcp-token")

    def tearDown(self) -> None:
        if self.previous_token_file is None:
            os.environ.pop("MCP_TOKEN_FILE", None)
        else:
            os.environ["MCP_TOKEN_FILE"] = self.previous_token_file
        self.temporary.cleanup()

    def test_composition_root_registers_the_public_tool_contract(self) -> None:
        server = app.create_server()
        self.assertEqual(set(server._tool_manager._tools), EXPECTED_TOOLS)

    def test_client_settings_are_loaded_lazily(self) -> None:
        original_api_id = os.environ.pop("TG_API_ID", None)
        try:
            with self.assertRaisesRegex(RuntimeError, "TG_API_ID"):
                TelegramSettings.from_env()
        finally:
            if original_api_id is not None:
                os.environ["TG_API_ID"] = original_api_id

    def test_phone_resolution_removes_temporary_contact_on_same_client(self) -> None:
        client_context = MagicMock()
        client = client_context.__enter__.return_value
        client.import_contacts.return_value = [
            SimpleNamespace(
                id=42,
                first_name="Ada",
                last_name="Lovelace",
                username="ada",
                is_bot=False,
            )
        ]
        client_factory = MagicMock(return_value=client_context)

        result = TelegramService(client_factory).resolve_phone("+44 1234 567890")

        self.assertTrue(result["found"])
        client_factory.assert_called_once_with()
        client.delete_contacts.assert_called_once_with(42)


if __name__ == "__main__":
    unittest.main()
