"""Gmail MCP tool registration and write-safety policy."""

from mcp.server.mcpserver import MCPServer

from .client import GmailClient
from .config import GmailSettings


def register_email_tools(mcp: MCPServer) -> None:
    """Attach Gmail tools to the application server."""

    @mcp.tool()
    def email_search(query: str = "", max_results: int = 20) -> list[dict]:
        """Search this agent's Gmail mailbox using Gmail search syntax."""
        return GmailClient.from_env().search(query, max_results)

    @mcp.tool()
    def email_list_unread(max_results: int = 20) -> list[dict]:
        """List unread messages in this agent's Gmail mailbox."""
        return GmailClient.from_env().unread(max_results)

    @mcp.tool()
    def email_get_message(message_id: str) -> dict:
        """Read one Gmail message by message ID."""
        return GmailClient.from_env().get_message(message_id)

    @mcp.tool()
    def email_get_thread(thread_id: str) -> list[dict]:
        """Read all messages in a Gmail conversation thread."""
        return GmailClient.from_env().get_thread(thread_id)

    @mcp.tool()
    def email_create_draft(
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
    ) -> dict:
        """Create an email draft without sending it."""
        return GmailClient.from_env().create_draft(to, subject, body, cc)

    @mcp.tool()
    def email_create_reply_draft(message_id: str, body: str) -> dict:
        """Create a reply in the original Gmail thread without sending it."""
        return GmailClient.from_env().create_reply_draft(message_id, body)

    @mcp.tool()
    def email_send(
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        user_confirmed: bool = False,
    ) -> dict:
        """Send a new email after server enablement and explicit confirmation."""
        if not GmailSettings.from_env().allow_send:
            return {
                "status": "disabled",
                "message": (
                    "Email sending is disabled on the server. Set "
                    "MCP_ALLOW_EMAIL_SEND=true after reviewing the deployment."
                ),
            }
        if not user_confirmed:
            return {
                "status": "confirmation_required",
                "message": (
                    "Explicit user confirmation is required before sending. Create a draft instead."
                ),
            }
        return GmailClient.from_env().send(to, subject, body, cc)

    @mcp.tool()
    def email_reply(
        message_id: str,
        body: str,
        user_confirmed: bool = False,
    ) -> dict:
        """Reply to an email after server enablement and explicit confirmation."""
        if not GmailSettings.from_env().allow_send:
            return {
                "status": "disabled",
                "message": (
                    "Email sending is disabled on the server. Set "
                    "MCP_ALLOW_EMAIL_SEND=true after reviewing the deployment."
                ),
            }
        if not user_confirmed:
            return {
                "status": "confirmation_required",
                "message": "Explicit user confirmation is required before sending the reply.",
            }
        return GmailClient.from_env().reply(message_id, body)
