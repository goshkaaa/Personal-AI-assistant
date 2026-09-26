"""Telegram MCP tool registration."""

from mcp.server.mcpserver import MCPServer

from .service import TelegramService


def register_telegram_tools(server: MCPServer) -> None:
    @server.tool()
    def telegram_search_chats(query: str, limit: int = 20) -> list[dict]:
        """Search existing dialogs by name, title, or username."""
        return TelegramService().search_chats(query, limit)

    @server.tool()
    def telegram_resolve_chat(chat_id: str) -> dict:
        """Resolve @username, numeric ID, or Telegram peer into chat data."""
        return TelegramService().resolve_chat(chat_id)

    @server.tool()
    def telegram_get_messages(chat_id: str, limit: int = 20) -> list[dict]:
        """Read recent messages from a numeric chat ID or @username."""
        return TelegramService().get_messages(chat_id, limit)

    @server.tool()
    def telegram_send_message(chat_id: str, text: str) -> dict:
        """Send one message and track the chat for incoming replies."""
        return TelegramService().send_message(chat_id, text)

    @server.tool()
    def telegram_reply(chat_id: str, message_id: int, text: str) -> dict:
        """Reply to a specific message and keep tracking the chat."""
        return TelegramService().reply(chat_id, message_id, text)

    @server.tool()
    def telegram_resolve_phone(phone: str) -> dict:
        """Resolve a public number using a temporary Telegram contact."""
        return TelegramService().resolve_phone(phone)

    @server.tool()
    def telegram_get_managed_chats() -> list[dict]:
        """List conversations currently tracked by the owner."""
        return TelegramService.managed_chats()

    @server.tool()
    def telegram_get_logged_messages(chat_id: int, limit: int = 50) -> list[dict]:
        """Read the persistent local log for a tracked chat."""
        return TelegramService.logged_messages(chat_id, limit)
