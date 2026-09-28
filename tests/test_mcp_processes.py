import asyncio
import os
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TOOLS = {
    "calendar": {
        "calendar_commit_event",
        "calendar_find_free_slots",
        "calendar_list_calendars",
        "calendar_list_events",
        "calendar_prepare_event",
        "calendar_status",
    },
    "gmail": {
        "email_create_draft",
        "email_create_reply_draft",
        "email_get_message",
        "email_get_thread",
        "email_list_unread",
        "email_reply",
        "email_search",
        "email_send",
    },
    "homeassistant": {
        "ha_call_service",
        "ha_find_entities",
        "ha_get_state",
        "ha_status",
        "ha_toggle",
        "ha_turn_off",
        "ha_turn_on",
    },
    "obsidian": {
        "obsidian_create_note",
        "obsidian_get_note",
        "obsidian_list_notes",
        "obsidian_send_note",
        "obsidian_update_note",
    },
    "telegram": {
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
    },
}


class MCPProcessIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temporary.name)
        self.vault = self.data_dir / "vault"
        self.database = self.data_dir / "telegram.sqlite3"
        self.env_file = self.data_dir / "integration.env"
        self.env_file.write_text(
            "\n".join(
                (
                    "CALENDAR_TIMEZONE=UTC",
                    f"OBSIDIAN_VAULT_PATH={self.vault}",
                    f"MCP_DB_PATH={self.database}",
                    f"MCP_TOKEN_FILE={self.data_dir / 'telegram-token'}",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        self.env_file.chmod(0o600)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _environment(self) -> dict[str, str]:
        return {
            "HOME": str(self.data_dir),
            "MCP_ENV_FILE": str(self.env_file),
            "PATH": os.environ.get("PATH", ""),
            "PYTHONUNBUFFERED": "1",
        }

    async def _inspect_server(self, service: str, *, create_note: bool = False) -> set[str]:
        command = ROOT / "mcp" / service / ".venv" / "bin" / f"{service}-mcp"
        parameters = StdioServerParameters(
            command=str(command),
            cwd=ROOT,
            env=self._environment(),
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(*streams, read_timeout_seconds=10) as session:
                await session.initialize()
                tools = await session.list_tools()
                if create_note:
                    result = await session.call_tool(
                        "obsidian_create_note",
                        {"title": "Integration", "content": "Created through MCP stdio."},
                    )
                    self.assertFalse(result.is_error)
                return {tool.name for tool in tools.tools}

    def _assert_server(self, service: str, *, create_note: bool = False) -> None:
        tools = asyncio.run(self._inspect_server(service, create_note=create_note))
        self.assertEqual(tools, EXPECTED_TOOLS[service])

    def test_calendar_stdio_handshake(self) -> None:
        self._assert_server("calendar")

    def test_gmail_stdio_handshake(self) -> None:
        self._assert_server("gmail")

    def test_homeassistant_stdio_handshake(self) -> None:
        self._assert_server("homeassistant")

    def test_obsidian_stdio_tool_call(self) -> None:
        self._assert_server("obsidian", create_note=True)
        note = self.vault / "Integration.md"
        self.assertIn("Created through MCP stdio.", note.read_text(encoding="utf-8"))

    def test_telegram_stdio_handshake_and_private_database(self) -> None:
        self._assert_server("telegram")
        self.assertTrue(self.database.is_file())
        if os.name != "nt":
            self.assertEqual(self.database.stat().st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
