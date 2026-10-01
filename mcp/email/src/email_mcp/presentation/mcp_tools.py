"""MCP tool registration for the Email application."""

from mcp.server.mcpserver import MCPServer

from ..application.service import EmailService


def register_email_tools(mcp: MCPServer, service: EmailService) -> None:
    """Attach email tools backed by the process-scoped application service."""

    @mcp.tool()
    def email_list_accounts() -> list[dict]:
        """List configured mailboxes and the account IDs accepted by other email tools."""
        return service.list_accounts()

    @mcp.tool()
    def email_search(
        query: str = "",
        max_results: int = 20,
        account_id: str | None = None,
    ) -> list[dict]:
        """Search one mailbox. Gmail accepts Gmail syntax; IMAP searches message text."""
        return service.search(query, max_results, account_id)

    @mcp.tool()
    def email_list_unread(
        max_results: int = 20,
        account_id: str | None = None,
    ) -> list[dict]:
        """List unread messages in the selected mailbox."""
        return service.unread(max_results, account_id)

    @mcp.tool()
    def email_get_message(message_id: str, account_id: str | None = None) -> dict:
        """Read one message from the selected mailbox."""
        return service.get_message(message_id, account_id)

    @mcp.tool()
    def email_get_thread(thread_id: str, account_id: str | None = None) -> list[dict]:
        """Read a conversation; generic IMAP accounts return the selected message."""
        return service.get_thread(thread_id, account_id)

    @mcp.tool()
    def email_create_draft(
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        account_id: str | None = None,
    ) -> dict:
        """Create a draft in the selected mailbox without sending it."""
        return service.create_draft(to, subject, body, cc, account_id)

    @mcp.tool()
    def email_create_reply_draft(
        message_id: str,
        body: str,
        account_id: str | None = None,
    ) -> dict:
        """Create a reply draft in the selected mailbox without sending it."""
        return service.create_reply_draft(message_id, body, account_id)

    @mcp.tool()
    def email_send(
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        user_confirmed: bool = False,
        account_id: str | None = None,
    ) -> dict:
        """Send a new message after per-account enablement and explicit confirmation."""
        return service.send(
            to,
            subject,
            body,
            cc,
            account_id,
            user_confirmed=user_confirmed,
        )

    @mcp.tool()
    def email_reply(
        message_id: str,
        body: str,
        user_confirmed: bool = False,
        account_id: str | None = None,
    ) -> dict:
        """Reply from the selected mailbox after enablement and explicit confirmation."""
        return service.reply(
            message_id,
            body,
            account_id,
            user_confirmed=user_confirmed,
        )
