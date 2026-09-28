"""Standards-based email client backed by IMAP and SMTP."""

import base64
import imaplib
import os
import smtplib
import ssl
import time
from collections.abc import Generator
from contextlib import contextmanager, suppress
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate, getaddresses, make_msgid, parseaddr
from pathlib import Path
from typing import Any

from ..config import ImapSmtpAccountSettings


class InternetMessageCodec:
    """Translate RFC 5322 messages to and from the MCP's stable data model."""

    @classmethod
    def serialize(
        cls,
        message: EmailMessage,
        message_id: str,
        *,
        include_body: bool,
    ) -> dict[str, Any]:
        body = cls.body(message) if include_body else ""
        preview_source = body or cls.header(message, "Subject")
        return {
            "id": message_id,
            "thread_id": message_id,
            "internet_message_id": cls.header(message, "Message-ID"),
            "from": cls.header(message, "From"),
            "reply_to": cls.header(message, "Reply-To"),
            "to": cls.header(message, "To"),
            "cc": cls.header(message, "Cc"),
            "subject": cls.header(message, "Subject"),
            "date": cls.header(message, "Date"),
            "body": body,
            "snippet": " ".join(preview_source.split())[:240],
            "labels": [],
        }

    @staticmethod
    def header(message: EmailMessage, name: str) -> str:
        value = message.get(name)
        if value is None:
            return ""
        try:
            return str(make_header(decode_header(str(value))))
        except (LookupError, UnicodeError):
            return str(value)

    @classmethod
    def body(cls, message: EmailMessage) -> str:
        if message.is_multipart():
            plain_parts: list[str] = []
            html_parts: list[str] = []
            for part in message.walk():
                if part.is_multipart() or part.get_content_disposition() == "attachment":
                    continue
                content_type = part.get_content_type()
                if content_type not in {"text/plain", "text/html"}:
                    continue
                content = cls._content(part)
                if content_type == "text/plain":
                    plain_parts.append(content)
                else:
                    html_parts.append(content)
            return "\n".join(plain_parts or html_parts).strip()
        return cls._content(message).strip()

    @staticmethod
    def _content(message: EmailMessage) -> str:
        try:
            content = message.get_content()
        except (LookupError, UnicodeError):
            payload = message.get_payload(decode=True) or b""
            return payload.decode(message.get_content_charset() or "utf-8", errors="replace")
        if isinstance(content, bytes):
            return content.decode(message.get_content_charset() or "utf-8", errors="replace")
        return str(content)

    @staticmethod
    def create(
        sender: str,
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        *,
        in_reply_to: str | None = None,
        references: str | None = None,
    ) -> EmailMessage:
        message = EmailMessage()
        message["From"] = sender
        message["To"] = to
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=True)
        sender_domain = parseaddr(sender)[1].rpartition("@")[2] or None
        message["Message-ID"] = make_msgid(domain=sender_domain)
        if cc:
            message["Cc"] = cc
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = references
        message.set_content(body)
        return message


class ImapSmtpClient:
    """Provider-neutral mailbox operations using encrypted IMAP and SMTP."""

    timeout_seconds = 30

    def __init__(self, settings: ImapSmtpAccountSettings) -> None:
        self.settings = settings

    def search(self, query: str = "", max_results: int = 20) -> list[dict[str, Any]]:
        criteria: list[str | bytes] = ["ALL"]
        charset: str | None = None
        if query.strip():
            value = query.strip()
            criteria = ["TEXT", self._quoted_search_value(value)]
            charset = "UTF-8" if not value.isascii() else None
        return self._search(criteria, max_results, charset=charset)

    def unread(self, max_results: int = 20) -> list[dict[str, Any]]:
        return self._search(["UNSEEN"], max_results)

    def get_message(self, message_id: str) -> dict[str, Any]:
        mailbox, uid = self._decode_reference(message_id)
        with self._mailbox(mailbox, readonly=True) as connection:
            raw = self._fetch(connection, uid)
        return InternetMessageCodec.serialize(
            self._parse(raw),
            message_id,
            include_body=True,
        )

    def get_thread(self, thread_id: str) -> list[dict[str, Any]]:
        # RFC 3501 has no portable conversation primitive. Returning the selected
        # message is deterministic; provider-specific adapters can offer richer threads.
        return [self.get_message(thread_id)]

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
    ) -> dict[str, str]:
        message = InternetMessageCodec.create(self.settings.address, to, subject, body, cc)
        return self._append_draft(message)

    def create_reply_draft(self, message_id: str, body: str) -> dict[str, str]:
        message = self._build_reply(message_id, body)
        return self._append_draft(message)

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
    ) -> dict[str, str]:
        message = InternetMessageCodec.create(self.settings.address, to, subject, body, cc)
        return self._send(message)

    def reply(self, message_id: str, body: str) -> dict[str, str]:
        message = self._build_reply(message_id, body)
        return self._send(message)

    def _search(
        self,
        criteria: list[str | bytes],
        max_results: int,
        *,
        charset: str | None = None,
    ) -> list[dict[str, Any]]:
        limit = min(max(int(max_results), 1), 100)
        with self._mailbox(self.settings.inbox_mailbox, readonly=True) as connection:
            status, data = connection.uid("search", charset, *criteria)
            self._require_ok(status, "IMAP search")
            raw_uids = data[0] if data else b""
            uids = raw_uids.split()[-limit:]
            messages: list[dict[str, Any]] = []
            for raw_uid in reversed(uids):
                uid = raw_uid.decode("ascii")
                reference = self._encode_reference(self.settings.inbox_mailbox, uid)
                raw = self._fetch(connection, uid)
                messages.append(
                    InternetMessageCodec.serialize(
                        self._parse(raw),
                        reference,
                        include_body=False,
                    )
                )
            return messages

    def _build_reply(self, message_id: str, body: str) -> EmailMessage:
        original = self.get_message(message_id)
        recipient = parseaddr(original["reply_to"] or original["from"])[1]
        if not recipient:
            raise ValueError("The original message has no reply address")
        subject = original["subject"]
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        original_message_id = original["internet_message_id"]
        return InternetMessageCodec.create(
            self.settings.address,
            recipient,
            subject,
            body,
            in_reply_to=original_message_id,
            references=original_message_id,
        )

    def _append_draft(self, message: EmailMessage) -> dict[str, str]:
        message_id = str(message["Message-ID"])
        with self._imap_connection() as connection:
            status, _ = connection.append(
                self.settings.drafts_mailbox,
                r"(\Draft)",
                imaplib.Time2Internaldate(time.time()),
                message.as_bytes(policy=policy.SMTP),
            )
            self._require_ok(status, "IMAP draft append")
        return {
            "draft_id": message_id,
            "message_id": message_id,
            "status": "draft_created",
        }

    def _send(self, message: EmailMessage) -> dict[str, str]:
        recipients = [address for _, address in getaddresses(message.get_all("to", [])) if address]
        recipients.extend(
            address for _, address in getaddresses(message.get_all("cc", [])) if address
        )
        if not recipients:
            raise ValueError("At least one valid recipient is required")

        password = self._read_password(self.settings.password_file)
        context = ssl.create_default_context()
        if self.settings.smtp_security == "ssl":
            with smtplib.SMTP_SSL(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.timeout_seconds,
                context=context,
            ) as connection:
                connection.login(self.settings.username, password)
                connection.send_message(message, to_addrs=recipients)
        else:
            with smtplib.SMTP(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.timeout_seconds,
            ) as connection:
                connection.ehlo()
                connection.starttls(context=context)
                connection.ehlo()
                connection.login(self.settings.username, password)
                connection.send_message(message, to_addrs=recipients)

        message_id = str(message["Message-ID"])
        result = {"message_id": message_id, "thread_id": message_id, "status": "sent"}
        if self.settings.sent_mailbox:
            try:
                self._append_sent_copy(message)
            except (imaplib.IMAP4.error, OSError, RuntimeError) as error:
                # SMTP has already accepted the message. Reporting the whole operation as
                # failed would invite a retry and could send a duplicate.
                result["sent_copy_status"] = "failed"
                result["warning"] = f"Message sent, but the Sent copy could not be stored: {error}"
            else:
                result["sent_copy_status"] = "stored"
        return result

    def _append_sent_copy(self, message: EmailMessage) -> None:
        with self._imap_connection() as connection:
            status, _ = connection.append(
                self.settings.sent_mailbox,
                r"(\Seen)",
                imaplib.Time2Internaldate(time.time()),
                message.as_bytes(policy=policy.SMTP),
            )
            self._require_ok(status, "IMAP sent-message append")

    @contextmanager
    def _mailbox(self, mailbox: str, *, readonly: bool) -> Generator[Any, None, None]:
        with self._imap_connection() as connection:
            status, _ = connection.select(mailbox, readonly=readonly)
            self._require_ok(status, f"select IMAP mailbox {mailbox!r}")
            yield connection

    @contextmanager
    def _imap_connection(self) -> Generator[Any, None, None]:
        context = ssl.create_default_context()
        if self.settings.imap_security == "ssl":
            connection = imaplib.IMAP4_SSL(
                self.settings.imap_host,
                self.settings.imap_port,
                ssl_context=context,
                timeout=self.timeout_seconds,
            )
        else:
            connection = imaplib.IMAP4(
                self.settings.imap_host,
                self.settings.imap_port,
                timeout=self.timeout_seconds,
            )
            connection.starttls(ssl_context=context)

        try:
            connection.login(
                self.settings.username,
                self._read_password(self.settings.password_file),
            )
            yield connection
        finally:
            with suppress(imaplib.IMAP4.error, OSError):
                connection.logout()

    @staticmethod
    def _fetch(connection: Any, uid: str) -> bytes:
        status, data = connection.uid("fetch", uid, "(BODY.PEEK[])")
        ImapSmtpClient._require_ok(status, f"fetch IMAP message {uid!r}")
        for item in data or []:
            if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], bytes):
                return item[1]
        raise RuntimeError(f"IMAP server returned no content for message {uid!r}")

    @staticmethod
    def _parse(raw: bytes) -> EmailMessage:
        parsed = BytesParser(policy=policy.default).parsebytes(raw)
        if not isinstance(parsed, EmailMessage):
            raise TypeError("Expected EmailMessage from standards-compliant parser")
        return parsed

    @staticmethod
    def _read_password(path: Path) -> str:
        if not path.is_file():
            raise RuntimeError(f"Email password file not found: {path}")
        if os.name != "nt" and path.stat().st_mode & 0o077:
            raise PermissionError(f"Email password file must have mode 0600: {path}")
        password = path.read_text(encoding="utf-8").strip()
        if not password:
            raise RuntimeError(f"Email password file is empty: {path}")
        return password

    @staticmethod
    def _quoted_search_value(value: str) -> bytes:
        escaped = value.encode("utf-8").replace(b"\\", b"\\\\").replace(b'"', b'\\"')
        return b'"' + escaped + b'"'

    @staticmethod
    def _encode_reference(mailbox: str, uid: str) -> str:
        encoded = base64.urlsafe_b64encode(f"{mailbox}\0{uid}".encode()).decode().rstrip("=")
        return f"imap_{encoded}"

    @staticmethod
    def _decode_reference(reference: str) -> tuple[str, str]:
        if not reference.startswith("imap_"):
            raise ValueError("Invalid IMAP message ID")
        encoded = reference.removeprefix("imap_")
        padding = "=" * (-len(encoded) % 4)
        try:
            mailbox, uid = base64.urlsafe_b64decode(encoded + padding).decode().split("\0", 1)
        except (ValueError, UnicodeDecodeError) as error:
            raise ValueError("Invalid IMAP message ID") from error
        if not mailbox or not uid.isdigit():
            raise ValueError("Invalid IMAP message ID")
        return mailbox, uid

    @staticmethod
    def _require_ok(status: str, operation: str) -> None:
        if status != "OK":
            raise RuntimeError(f"{operation} failed with status {status!r}")
