"""Multi-account email MCP server."""

from mcp.server.mcpserver import MCPServer

from .composition import EmailContainer
from .presentation.mcp_tools import register_email_tools


def create_server(container: EmailContainer | None = None) -> MCPServer:
    dependencies = container or EmailContainer()
    server = MCPServer(
        name="email",
        instructions=(
            "Work with configured Gmail and IMAP/SMTP accounts through one interface. "
            "Choose an account_id when more than one mailbox exists. New messages and "
            "replies are sent only when account policy and the individual call both allow it."
        ),
    )
    register_email_tools(server, dependencies.service)
    return server


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
