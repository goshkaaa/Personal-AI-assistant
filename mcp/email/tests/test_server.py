import base64
import json
import sys
import tempfile
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import MagicMock, patch

SRC = Path(__file__).resolve().parents[1] / "src"
PROVIDER_EXAMPLES = Path(__file__).resolve().parents[1] / "providers"
sys.path.insert(0, str(SRC))

import email_mcp.service as legacy_service  # noqa: E402
from email_mcp.composition import EmailContainer  # noqa: E402
from email_mcp.config import (  # noqa: E402
    EmailSettings,
    GmailAccountSettings,
    ImapSmtpAccountSettings,
    write_private,
)
from email_mcp.providers.gmail import GmailClient  # noqa: E402
from email_mcp.providers.imap_smtp import ImapSmtpClient, InternetMessageCodec  # noqa: E402
from email_mcp.server import create_server  # noqa: E402

EmailService = legacy_service.EmailService


class EmailServerTests(unittest.TestCase):
    @patch("email_mcp.service.EmailSettings.from_env")
    def test_legacy_service_factory_and_settings_export(self, from_env) -> None:
        settings = EmailSettings(accounts=(), default_account_id="default")
        from_env.return_value = settings

        service = EmailService.from_env()

        self.assertIs(legacy_service.EmailSettings, EmailSettings)
        self.assertIs(service.settings, settings)

    def test_private_write_replaces_token_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            token = Path(temporary) / "secrets" / "token.json"
            write_private(token, "first")
            write_private(token, "second")

            self.assertEqual(token.read_text(encoding="utf-8"), "second")
            self.assertEqual(token.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(token.parent.glob(f".{token.name}.*")), [])

    def test_public_tool_contract(self) -> None:
        server = create_server()
        self.assertEqual(
            set(server._tool_manager._tools),
            {
                "email_create_draft",
                "email_create_reply_draft",
                "email_get_message",
                "email_get_thread",
                "email_list_accounts",
                "email_list_unread",
                "email_reply",
                "email_search",
                "email_send",
            },
        )

    def test_container_reuses_application_service_and_account_client(self) -> None:
        account = GmailAccountSettings(
            account_id="personal",
            label="Personal",
            address="me@example.com",
            credentials_file=Path("credentials"),
            token_file=Path("token"),
        )
        settings = EmailSettings(accounts=(account,), default_account_id="personal")
        factory = MagicMock()
        factory.create.return_value = MagicMock(search=MagicMock(return_value=[]))
        container = EmailContainer(settings=settings, client_factory=factory)

        self.assertIs(container.service, container.service)
        container.service.search("first")
        container.service.search("second")

        factory.create.assert_called_once_with(account)

    def test_send_and_reply_require_policy_and_explicit_confirmation(self) -> None:
        blocked = GmailAccountSettings(
            account_id="blocked",
            label="Blocked",
            address="blocked@example.com",
            credentials_file=Path("credentials"),
            token_file=Path("blocked-token"),
        )
        enabled = GmailAccountSettings(
            account_id="enabled",
            label="Enabled",
            address="enabled@example.com",
            credentials_file=Path("credentials"),
            token_file=Path("enabled-token"),
            allow_send=True,
        )
        settings = EmailSettings(accounts=(blocked, enabled), default_account_id="blocked")
        blocked_client = MagicMock()
        enabled_client = MagicMock()
        service = EmailService(
            settings,
            clients={"blocked": blocked_client, "enabled": enabled_client},
        )

        self.assertEqual(
            service.send("to@example.com", "Subject", "Body", user_confirmed=True)["status"],
            "disabled",
        )
        self.assertEqual(
            service.reply("message-1", "Body", user_confirmed=True)["status"],
            "disabled",
        )
        self.assertEqual(
            service.send(
                "to@example.com",
                "Subject",
                "Body",
                account_id="enabled",
            )["status"],
            "confirmation_required",
        )
        self.assertEqual(
            service.reply("message-1", "Body", account_id="enabled")["status"],
            "confirmation_required",
        )
        blocked_client.send.assert_not_called()
        blocked_client.reply.assert_not_called()
        enabled_client.send.assert_not_called()
        enabled_client.reply.assert_not_called()

        service.send(
            "to@example.com",
            "Subject",
            "Body",
            account_id="enabled",
            user_confirmed=True,
        )
        service.reply("message-1", "Body", account_id="enabled", user_confirmed=True)
        enabled_client.send.assert_called_once_with("to@example.com", "Subject", "Body", None)
        enabled_client.reply.assert_called_once_with("message-1", "Body")

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
        settings = GmailAccountSettings(
            account_id="personal",
            label="Personal",
            address="me@example.com",
            credentials_file=Path("credentials"),
            token_file=Path("token"),
            allow_send=True,
        )

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

    def test_multiple_provider_accounts_are_loaded_and_routed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_file = root / "accounts.json"
            config_file.write_text(
                json.dumps(
                    {
                        "default_account": "personal",
                        "accounts": [
                            {
                                "id": "personal",
                                "provider": "gmail",
                                "label": "Personal Gmail",
                                "address": "me@example.com",
                                "credentials_file": "google-client.json",
                                "token_file": "google-token.json",
                            },
                            {
                                "id": "work",
                                "provider": "yandex",
                                "label": "Work",
                                "address": "me@example.com",
                                "password_file": "work-password",
                                "allow_send": True,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            settings = EmailSettings.from_file(config_file)

        self.assertEqual(settings.default_account_id, "personal")
        self.assertIsInstance(settings.account(), GmailAccountSettings)
        work = settings.account("work")
        self.assertIsInstance(work, ImapSmtpAccountSettings)
        self.assertEqual(work.imap_host, "imap.yandex.ru")
        self.assertEqual(work.smtp_host, "smtp.yandex.ru")
        self.assertEqual(work.smtp_port, 465)
        self.assertEqual(work.smtp_security, "ssl")
        work_client = MagicMock()
        work_client.search.return_value = [{"id": "message-1"}]
        service = EmailService(settings, clients={"work": work_client})
        accounts = service.list_accounts()
        self.assertEqual([item["account_id"] for item in accounts], ["personal", "work"])
        self.assertFalse(accounts[0]["sending_enabled"])
        self.assertTrue(accounts[1]["sending_enabled"])
        self.assertEqual(
            service.search("quarterly report", account_id="work"),
            [
                {
                    "id": "message-1",
                    "account_id": "work",
                    "provider": "yandex",
                }
            ],
        )
        work_client.search.assert_called_once_with("quarterly report", 20)

    def test_imap_message_references_are_opaque_and_reversible(self) -> None:
        reference = ImapSmtpClient._encode_reference("Archive/2026:Q4", "481")

        self.assertEqual(
            ImapSmtpClient._decode_reference(reference),
            ("Archive/2026:Q4", "481"),
        )

    def test_imap_search_fetches_summary_headers_in_one_batch(self) -> None:
        settings = ImapSmtpAccountSettings(
            account_id="work",
            label="Work",
            address="me@example.com",
            username="me@example.com",
            password_file=Path("password"),
            imap_host="imap.example.com",
            smtp_host="smtp.example.com",
        )
        client = ImapSmtpClient(settings)
        connection = MagicMock()
        connection.uid.side_effect = [
            ("OK", [b"10 20"]),
            (
                "OK",
                [
                    (b"1 (UID 10 BODY[HEADER.FIELDS] {18}", b"Subject: First\r\n\r\n"),
                    (b"2 (UID 20 BODY[HEADER.FIELDS] {19}", b"Subject: Second\r\n\r\n"),
                ],
            ),
        ]

        with patch.object(client, "_mailbox") as mailbox:
            mailbox.return_value.__enter__.return_value = connection
            result = client.search(max_results=2)

        self.assertEqual([message["subject"] for message in result], ["Second", "First"])
        self.assertEqual(connection.uid.call_count, 2)
        fetch_call = connection.uid.call_args_list[1]
        self.assertEqual(fetch_call.args[1], "10,20")
        self.assertIn("HEADER.FIELDS", fetch_call.args[2])
        self.assertNotEqual(fetch_call.args[2], "(BODY.PEEK[])")

    def test_imap_connection_is_closed_when_starttls_fails(self) -> None:
        settings = ImapSmtpAccountSettings(
            account_id="work",
            label="Work",
            address="me@example.com",
            username="me@example.com",
            password_file=Path("password"),
            imap_host="imap.example.com",
            smtp_host="smtp.example.com",
            imap_security="starttls",
        )
        client = ImapSmtpClient(settings)
        connection = MagicMock()
        connection.starttls.side_effect = OSError("TLS negotiation failed")

        with (
            patch(
                "email_mcp.providers.imap_smtp.imaplib.IMAP4",
                return_value=connection,
            ),
            self.assertRaisesRegex(OSError, "TLS negotiation failed"),
            client._imap_connection(),
        ):
            self.fail("connection context unexpectedly opened")

        connection.logout.assert_called_once_with()

    def test_checked_in_provider_examples_are_valid(self) -> None:
        expected_hosts = {
            "yandex": ("imap.yandex.ru", "smtp.yandex.ru"),
            "mailru": ("imap.mail.ru", "smtp.mail.ru"),
            "icloud": ("imap.mail.me.com", "smtp.mail.me.com"),
        }
        for provider, hosts in expected_hosts.items():
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as temporary:
                account = json.loads(
                    (PROVIDER_EXAMPLES / provider / "account.example.json").read_text(
                        encoding="utf-8"
                    )
                )
                config_file = Path(temporary) / "accounts.json"
                config_file.write_text(json.dumps({"accounts": [account]}), encoding="utf-8")

                settings = EmailSettings.from_file(config_file)
                configured = settings.account()

                self.assertIsInstance(configured, ImapSmtpAccountSettings)
                self.assertEqual(configured.provider, provider)
                self.assertEqual((configured.imap_host, configured.smtp_host), hosts)

        gmail_example = json.loads(
            (PROVIDER_EXAMPLES / "gmail" / "account.example.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as temporary:
            config_file = Path(temporary) / "accounts.json"
            config_file.write_text(
                json.dumps({"accounts": [gmail_example]}),
                encoding="utf-8",
            )
            self.assertIsInstance(
                EmailSettings.from_file(config_file).account(), GmailAccountSettings
            )

        custom_example = json.loads(
            (PROVIDER_EXAMPLES / "custom" / "account.example.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as temporary:
            config_file = Path(temporary) / "accounts.json"
            config_file.write_text(
                json.dumps({"accounts": [custom_example]}),
                encoding="utf-8",
            )
            configured = EmailSettings.from_file(config_file).account()
            self.assertIsInstance(configured, ImapSmtpAccountSettings)
            self.assertEqual(configured.provider, "imap_smtp")
            self.assertEqual(configured.imap_host, "imap.example.com")

    def test_standard_message_codec_handles_unicode_and_reply_headers(self) -> None:
        message = InternetMessageCodec.create(
            "me@example.com",
            "friend@example.com",
            "Привет",
            "Встретимся завтра.",
            in_reply_to="<original@example.com>",
            references="<original@example.com>",
        )

        serialized = InternetMessageCodec.serialize(message, "message-1", include_body=True)

        self.assertEqual(serialized["subject"], "Привет")
        self.assertEqual(serialized["body"], "Встретимся завтра.")
        self.assertEqual(serialized["thread_id"], "message-1")
        self.assertEqual(serialized["internet_message_id"], str(message["Message-ID"]))
        self.assertEqual(message["In-Reply-To"], "<original@example.com>")

    def test_sent_message_is_not_reported_as_failed_when_sent_copy_cannot_be_stored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            password_file = Path(temporary) / "password"
            password_file.write_text("app-password\n", encoding="utf-8")
            password_file.chmod(0o600)
            settings = ImapSmtpAccountSettings(
                account_id="work",
                label="Work",
                address="me@example.com",
                username="me@example.com",
                password_file=password_file,
                imap_host="imap.example.com",
                smtp_host="smtp.example.com",
                sent_mailbox="Sent",
            )
            client = ImapSmtpClient(settings)

            with (
                patch("email_mcp.providers.imap_smtp.smtplib.SMTP_SSL") as smtp,
                patch.object(
                    client,
                    "_append_sent_copy",
                    side_effect=RuntimeError("archive unavailable"),
                ),
            ):
                result = client.send("friend@example.com", "Subject", "Body")

        smtp.return_value.__enter__.return_value.send_message.assert_called_once()
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["sent_copy_status"], "failed")
        self.assertIn("archive unavailable", result["warning"])


if __name__ == "__main__":
    unittest.main()
