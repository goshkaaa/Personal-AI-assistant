"""Obsidian MCP tool registration."""

from mcp.server.mcpserver import MCPServer

from .service import ObsidianVault


def register_tools(server: MCPServer) -> None:
    @server.tool()
    def obsidian_create_note(title: str, content: str = "") -> dict:
        """Create a new Markdown note without overwriting an existing note."""
        return ObsidianVault.from_env().create(title, content)

    @server.tool()
    def obsidian_update_note(title: str, content: str, section: str = "") -> dict:
        """Append useful information, optionally under a section heading."""
        return ObsidianVault.from_env().update(title, content, section)

    @server.tool()
    def obsidian_get_note(title: str) -> dict:
        """Read a complete Markdown note."""
        return ObsidianVault.from_env().get(title)

    @server.tool()
    def obsidian_list_notes(query: str = "") -> list[dict]:
        """List notes or search their titles and content."""
        return ObsidianVault.from_env().list(query)

    @server.tool()
    def obsidian_send_note(title: str) -> dict:
        """Send a note file through the owner's Telegram profile."""
        return ObsidianVault.from_env().send(title)
