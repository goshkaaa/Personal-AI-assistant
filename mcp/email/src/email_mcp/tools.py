"""Provider-neutral email tools and write-safety policy."""

from mcp.server.mcpserver import MCPServer

from .service import EmailService


def register_email_tools(mcp: MCPServer) -> None:
    """Attach multi-account email tools to the application server."""

    @mcp.tool()
    def email_list_accounts() -> list[dict]:
        """List configured mailboxes and the account IDs accepted by other email tools."""
        return EmailService.from_env().list_accounts()

    @mcp.tool()
    def email_search(
        query: str = "",
        max_results: int = 20,
        account_id: str | None = None,
    ) -> list[dict]:
        """Search one mailbox. Gmail accepts Gmail syntax; IMAP searches message text."""
        return EmailService.from_env().search(query, max_results, account_id)

    @mcp.tool()
    def email_list_unread(
        max_results: int = 20,
        account_id: str | None = None,
    ) -> list[dict]:
        """List unread messages in the selected mailbox."""
        return EmailService.from_env().unread(max_results, account_id)

    @mcp.tool()
    def email_get_message(message_id: str, account_id: str | None = None) -> dict:
        """Read one message from the selected mailbox."""
        return EmailService.from_env().get_message(message_id, account_id)

    @mcp.tool()
    def email_get_thread(thread_id: str, account_id: str | None = None) -> list[dict]:
        """Read a conversation; generic IMAP accounts return the selected message."""
        return EmailService.from_env().get_thread(thread_id, account_id)

    @mcp.tool()
    def email_create_draft(
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        account_id: str | None = None,
    ) -> dict:
        """Create a draft in the selected mailbox without sending it."""
        return EmailService.from_env().create_draft(to, subject, body, cc, account_id)

    @mcp.tool()
    def email_create_reply_draft(
        message_id: str,
        body: str,
        account_id: str | None = None,
    ) -> dict:
        """Create a reply draft in the selected mailbox without sending it."""
        return EmailService.from_env().create_reply_draft(message_id, body, account_id)

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
        service = EmailService.from_env()
        account = service.settings.account(account_id)
        if not account.allow_send:
            return {
                "status": "disabled",
                "account_id": account.account_id,
                "message": "Email sending is disabled in the selected account configuration.",
            }
        if not user_confirmed:
            return {
                "status": "confirmation_required",
                "account_id": account.account_id,
                "message": (
                    "Explicit user confirmation is required before sending. Create a draft instead."
                ),
            }
        return service.send(to, subject, body, cc, account_id)

    @mcp.tool()
    def email_reply(
        message_id: str,
        body: str,
        user_confirmed: bool = False,
        account_id: str | None = None,
    ) -> dict:
        """Reply from the selected mailbox after enablement and explicit confirmation."""
        service = EmailService.from_env()
        account = service.settings.account(account_id)
        if not account.allow_send:
            return {
                "status": "disabled",
                "account_id": account.account_id,
                "message": "Email sending is disabled in the selected account configuration.",
            }
        if not user_confirmed:
            return {
                "status": "confirmation_required",
                "account_id": account.account_id,
                "message": "Explicit user confirmation is required before sending the reply.",
            }
        return service.reply(message_id, body, account_id)
