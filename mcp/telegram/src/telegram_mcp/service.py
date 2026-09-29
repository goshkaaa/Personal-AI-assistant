"""Telegram operations exposed by the MCP adapter."""

from collections.abc import Callable
from contextlib import suppress
from typing import Any

from pyrogram.types import InputPhoneContact

from .client import create_client
from .serializers import (
    display_name,
    log_message,
    normalize_peer,
    serialize_chat,
    serialize_message,
)
from .tasks.conversations import conversations


class TelegramService:
    def __init__(self, client_factory: Callable[[], Any] = create_client) -> None:
        self.client_factory = client_factory

    def search_chats(self, query: str, limit: int = 20) -> list[dict]:
        query = query.strip().lower().lstrip("@")
        if not query:
            return []

        results = []
        try:
            with self.client_factory() as app:
                for dialog in app.get_dialogs():
                    chat = dialog.chat
                    values = (
                        getattr(chat, "title", None),
                        getattr(chat, "first_name", None),
                        getattr(chat, "last_name", None),
                        getattr(chat, "username", None),
                    )
                    if query in " ".join(str(value) for value in values if value).lower():
                        results.append(serialize_chat(chat))
                        if len(results) >= max(1, min(int(limit), 50)):
                            break
            return results
        except Exception as exc:
            self._raise("search", exc)

    def resolve_chat(self, chat_id: str) -> dict:
        try:
            with self.client_factory() as app:
                chat = app.get_chat(normalize_peer(chat_id))
            return serialize_chat(chat)
        except Exception as exc:
            self._raise("resolve", exc)

    def get_messages(self, chat_id: str, limit: int = 20) -> list[dict]:
        try:
            with self.client_factory() as app:
                messages = list(
                    app.get_chat_history(
                        normalize_peer(chat_id),
                        limit=max(1, min(int(limit), 100)),
                    )
                )
                for message in messages:
                    log_message(message)
            messages.reverse()
            return [serialize_message(message) for message in messages]
        except Exception as exc:
            self._raise("read", exc)

    def send_message(self, chat_id: str, text: str) -> dict:
        return self._send(chat_id, text)

    def reply(self, chat_id: str, message_id: int, text: str) -> dict:
        return self._send(chat_id, text, int(message_id))

    def resolve_phone(self, phone: str) -> dict:
        digits = "".join(character for character in str(phone).strip() if character.isdigit())
        if not 7 <= len(digits) <= 15:
            raise ValueError("Phone number must contain 7-15 digits.")

        normalized = "+" + digits
        contact = InputPhoneContact(
            phone=normalized,
            first_name="MCP",
            last_name="Temporary",
        )
        try:
            with self.client_factory() as app:
                users = app.import_contacts([contact])
                if not users:
                    return {
                        "found": False,
                        "phone": normalized,
                        "reason": "Telegram did not resolve this number to an accessible user.",
                    }
                resolved_user = users[0]
                try:
                    return {
                        "found": True,
                        "phone": normalized,
                        "user": {
                            "id": resolved_user.id,
                            "first_name": getattr(resolved_user, "first_name", None),
                            "last_name": getattr(resolved_user, "last_name", None),
                            "username": getattr(resolved_user, "username", None),
                            "is_bot": bool(getattr(resolved_user, "is_bot", False)),
                        },
                        "chat_id": resolved_user.id,
                    }
                finally:
                    # The contact exists only to resolve the number and must not remain imported.
                    with suppress(Exception):
                        app.delete_contacts(resolved_user.id)
        except Exception as exc:
            self._raise("phone resolve", exc)

    @staticmethod
    def managed_chats() -> list[dict]:
        return conversations.managed_chats()

    @staticmethod
    def logged_messages(chat_id: int, limit: int = 50) -> list[dict]:
        return conversations.messages(int(chat_id), max(1, min(int(limit), 200)))

    def _send(self, chat_id: str, text: str, reply_to: int | None = None) -> dict:
        text = text.strip()
        if not text:
            raise ValueError("Message cannot be empty")
        if len(text) > 4000:
            raise ValueError("Message exceeds 4000 characters")

        try:
            with self.client_factory() as app:
                chat = app.get_chat(normalize_peer(chat_id))
                message = app.send_message(
                    chat_id=chat.id,
                    text=text,
                    reply_to_message_id=reply_to,
                )
                log_message(message)
                conversations.mark_managed(
                    chat.id,
                    getattr(chat, "title", None) or display_name(chat),
                    getattr(chat, "username", None),
                    "reply_sent_by_owner" if reply_to else "message_sent_by_owner",
                )
            result = {
                "success": True,
                "delivered": True,
                "chat": serialize_chat(chat),
                "message_id": message.id,
                "text": text,
            }
            if reply_to:
                result["reply_to_message_id"] = reply_to
            return result
        except Exception as exc:
            self._raise("reply" if reply_to else "send", exc)

    @staticmethod
    def _raise(operation: str, exc: Exception) -> None:
        raise RuntimeError(f"Telegram {operation} failed: {type(exc).__name__}: {exc}") from exc
