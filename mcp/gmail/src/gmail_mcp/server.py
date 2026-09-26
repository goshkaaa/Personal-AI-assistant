"""Gmail MCP server."""

from mcp.server.mcpserver import MCPServer

from .tools import register_email_tools


def create_server() -> MCPServer:
    server = MCPServer(
        name="gmail",
        instructions=(
            "Read Gmail, work with threads, and create drafts. New messages and replies "
            "are sent only when server policy and the individual call both allow it."
        ),
    )
    register_email_tools(server)
    return server


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
