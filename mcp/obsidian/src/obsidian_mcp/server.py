"""Obsidian MCP application."""

from mcp.server.mcpserver import MCPServer

from .tools import register_tools


def create_server() -> MCPServer:
    server = MCPServer(
        name="obsidian",
        instructions=(
            "Persistent Markdown knowledge base for the owner. Use it only when the owner "
            "asks to work with notes. Never store passwords, tokens, OAuth credentials, "
            "session data, or other secrets."
        ),
    )
    register_tools(server)
    return server


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
