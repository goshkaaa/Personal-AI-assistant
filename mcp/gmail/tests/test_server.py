import base64
import sys
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import MagicMock

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from gmail_mcp.client import GmailClient  # noqa: E402
from gmail_mcp.config import GmailSettings  # noqa: E402
from gmail_mcp.server import create_server  # noqa: E402


class GmailServerTests(unittest.TestCase):
    def test_public_tool_contract(self) -> None:
        server = create_server()
        self.assertEqual(
            set(server._tool_manager._tools),
            {
                "email_create_draft",
                "email_create_reply_draft",
                "email_get_message",
                "email_get_thread",
                "email_list_unread",
                "email_reply",
                "email_search",
                "email_send",
            },
        )

    def test_reply_stays_in_thread_and_sets_email_headers(self) -> None:
        service = MagicMock()
        messages = service.users.return_value.messages.return_value
        messages.get.return_value.execute.return_value = {
            "id": "original",
            "threadId": "thread-1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Question"},
                    {"name": "Message-ID", "value": "<original@example.com>"},
                ]
            },
        }
        messages.send.return_value.execute.return_value = {
            "id": "reply",
            "threadId": "thread-1",
        }
        settings = GmailSettings(Path("credentials"), Path("token"), allow_send=True)

        result = GmailClient(settings, service).reply("original", "Answer")

        body = messages.send.call_args.kwargs["body"]
        padding = "=" * (-len(body["raw"]) % 4)
        message = BytesParser(policy=policy.default).parsebytes(
            base64.urlsafe_b64decode(body["raw"] + padding)
        )
        self.assertEqual(result["status"], "sent")
        self.assertEqual(body["threadId"], "thread-1")
        self.assertEqual(message["To"], "sender@example.com")
        self.assertEqual(message["Subject"], "Re: Question")
        self.assertEqual(message["In-Reply-To"], "<original@example.com>")


if __name__ == "__main__":
    unittest.main()
