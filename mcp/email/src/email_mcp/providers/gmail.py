"""Small object-oriented client for the Gmail API."""

import os
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from ..config import EmailSettings, GmailAccountSettings, private_path
from .gmail_codec import GmailMessageCodec

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


class GmailClient:
    def __init__(self, settings: GmailAccountSettings, service: Any | None = None) -> None:
        self.settings = settings
        self._service = service

    @classmethod
    def from_env(cls, account_id: str | None = None) -> "GmailClient":
        account = EmailSettings.from_env().account(account_id)
        if not isinstance(account, GmailAccountSettings):
            raise ValueError(f"Email account {account.account_id!r} is not a Gmail account")
        return cls(account)

    @property
    def service(self) -> Any:
        if self._service is None:
            self._service = self._connect()
        return self._service

    def search(self, query: str = "", max_results: int = 20) -> list[dict[str, Any]]:
        result = (
            self.service.users()
            .messages()
            .list(
                userId="me",
                q=query or None,
                maxResults=min(max(int(max_results), 1), 100),
            )
            .execute()
        )
        return [self._metadata(reference["id"]) for reference in result.get("messages", [])]

    def unread(self, max_results: int = 20) -> list[dict[str, Any]]:
        return self.search("is:unread", max_results)

    def get_message(self, message_id: str) -> dict[str, Any]:
        message = (
            self.service.users().messages().get(userId="me", id=message_id, format="full").execute()
        )
        return GmailMessageCodec.serialize(message)

    def get_thread(self, thread_id: str) -> list[dict[str, Any]]:
        thread = (
            self.service.users().threads().get(userId="me", id=thread_id, format="full").execute()
        )
        return [GmailMessageCodec.serialize(message) for message in thread.get("messages", [])]

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
    ) -> dict[str, str]:
        return self._create_draft(GmailMessageCodec.encode(to, subject, body, cc))

    def create_reply_draft(self, message_id: str, body: str) -> dict[str, str]:
        raw, thread_id = self._build_reply(message_id, body)
        return self._create_draft(raw, thread_id)

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
    ) -> dict[str, str]:
        raw = GmailMessageCodec.encode(to, subject, body, cc)
        result = self.service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {
            "message_id": result["id"],
            "thread_id": result["threadId"],
            "status": "sent",
        }

    def reply(self, message_id: str, body: str) -> dict[str, str]:
        raw, thread_id = self._build_reply(message_id, body)
        result = (
            self.service.users()
            .messages()
            .send(userId="me", body={"raw": raw, "threadId": thread_id})
            .execute()
        )
        return {
            "message_id": result["id"],
            "thread_id": result["threadId"],
            "status": "sent",
        }

    def _connect(self) -> Any:
        token_path = self.settings.token_file
        if not token_path.is_file():
            raise RuntimeError(f"Gmail token not found: {token_path}. Run email-auth first.")

        private_path(token_path)
        credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            temporary = token_path.with_suffix(f"{token_path.suffix}.tmp")
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as token_file:
                token_file.write(credentials.to_json())
            temporary.replace(token_path)
            token_path.chmod(0o600)
        return build("gmail", "v1", credentials=credentials, cache_discovery=False)

    def _metadata(self, message_id: str) -> dict[str, Any]:
        message = (
            self.service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"],
            )
            .execute()
        )
        headers = GmailMessageCodec.headers(message)
        return {
            "id": message["id"],
            "thread_id": message["threadId"],
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "snippet": message.get("snippet", ""),
            "labels": message.get("labelIds", []),
        }

    def _create_draft(self, raw: str, thread_id: str | None = None) -> dict[str, str]:
        message: dict[str, str] = {"raw": raw}
        if thread_id:
            message["threadId"] = thread_id
        result = (
            self.service.users().drafts().create(userId="me", body={"message": message}).execute()
        )
        return {
            "draft_id": result["id"],
            "message_id": result["message"]["id"],
            "status": "draft_created",
        }

    def _build_reply(self, message_id: str, body: str) -> tuple[str, str]:
        original = (
            self.service.users().messages().get(userId="me", id=message_id, format="full").execute()
        )
        headers = GmailMessageCodec.headers(original)
        recipient = headers.get("reply-to") or headers.get("from")
        if not recipient:
            raise ValueError("The original message has no reply address")

        subject = headers.get("subject", "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        original_message_id = headers.get("message-id", "")
        references = " ".join(
            value for value in (headers.get("references", ""), original_message_id) if value
        )
        raw = GmailMessageCodec.encode(
            recipient,
            subject,
            body,
            in_reply_to=original_message_id or None,
            references=references or None,
        )
        return raw, original["threadId"]
