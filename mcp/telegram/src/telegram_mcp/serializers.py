"""Pure Telegram serialization plus the local message audit adapter."""

from typing import Any

from .tasks.conversations import conversations


def display_name(user: Any | None) -> str | None:
    if not user:
        return None

    name = " ".join(
        value
        for value in (
            getattr(user, "first_name", None),
            getattr(user, "last_name", None),
        )
        if value
    ).strip()
    return name or getattr(user, "username", None)


def normalize_peer(value: str | int) -> str | int:
    if isinstance(value, int):
        return value

    normalized = str(value).strip()
    if not normalized:
        raise ValueError("chat_id cannot be empty")
    if normalized.lstrip("-").isdigit():
        return int(normalized)
    return normalized


def serialize_chat(chat: Any) -> dict:
    return {
        "id": chat.id,
        "type": str(chat.type),
        "title": getattr(chat, "title", None),
        "first_name": getattr(chat, "first_name", None),
        "last_name": getattr(chat, "last_name", None),
        "username": getattr(chat, "username", None),
    }


def serialize_message(message: Any) -> dict:
    sender = getattr(message, "from_user", None)
    return {
        "id": message.id,
        "chat_id": message.chat.id if message.chat else None,
        "date": message.date.isoformat() if message.date else None,
        "text": message.text or message.caption or "",
        "outgoing": bool(getattr(message, "outgoing", False)),
        "sender": {
            "id": sender.id if sender else None,
            "name": display_name(sender),
            "username": getattr(sender, "username", None),
        }
        if sender
        else None,
        "reply_to_message_id": getattr(message, "reply_to_message_id", None),
    }


def log_message(message: Any) -> None:
    sender = getattr(message, "from_user", None)
    chat = message.chat
    conversations.save_message(
        chat_id=chat.id,
        message_id=message.id,
        date=message.date.isoformat() if message.date else None,
        direction="outgoing" if message.outgoing else "incoming",
        sender_id=getattr(sender, "id", None),
        sender_name=display_name(sender),
        sender_username=getattr(sender, "username", None),
        chat_title=getattr(chat, "title", None) or display_name(chat),
        chat_username=getattr(chat, "username", None),
        text=message.text or message.caption or "",
        reply_to_message_id=getattr(message, "reply_to_message_id", None),
    )
