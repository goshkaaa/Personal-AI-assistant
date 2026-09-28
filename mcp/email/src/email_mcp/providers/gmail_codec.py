"""Encode and decode Gmail API messages."""

import base64
from email.message import EmailMessage
from typing import Any


class GmailMessageCodec:
    @staticmethod
    def headers(message: dict[str, Any]) -> dict[str, str]:
        values = message.get("payload", {}).get("headers", [])
        return {header["name"].lower(): header["value"] for header in values}

    @classmethod
    def body(cls, payload: dict[str, Any]) -> str:
        if payload.get("mimeType") == "text/plain":
            return cls._decode(payload.get("body", {}).get("data"))

        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain":
                text = cls.body(part)
                if text:
                    return text

        for part in payload.get("parts", []):
            text = cls.body(part)
            if text:
                return text
        return ""

    @classmethod
    def serialize(cls, message: dict[str, Any]) -> dict[str, Any]:
        headers = cls.headers(message)
        return {
            "id": message["id"],
            "thread_id": message["threadId"],
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "cc": headers.get("cc", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "body": cls.body(message.get("payload", {})),
            "snippet": message.get("snippet", ""),
            "labels": message.get("labelIds", []),
        }

    @staticmethod
    def encode(
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        in_reply_to: str | None = None,
        references: str | None = None,
    ) -> str:
        message = EmailMessage()
        message["To"] = to
        message["Subject"] = subject
        if cc:
            message["Cc"] = cc
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = references
        message.set_content(body)
        return base64.urlsafe_b64encode(message.as_bytes()).decode()

    @staticmethod
    def _decode(data: str | None) -> str:
        if not data:
            return ""
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + padding).decode("utf-8", errors="replace")
