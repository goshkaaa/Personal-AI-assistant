"""Home Assistant MCP application."""

from mcp.server.mcpserver import MCPServer

from .tools import register_tools


def create_server() -> MCPServer:
    server = MCPServer(
        name="homeassistant",
        instructions=(
            "Read Home Assistant state freely. Service calls are write actions and "
            "must target an explicitly identified entity."
        ),
    )
    register_tools(server)
    return server


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
