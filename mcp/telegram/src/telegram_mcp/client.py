"""Telegram client construction shared by every runtime process."""

import os
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from pyrogram import Client

from .config import DATA_DIR, env_path


@dataclass(frozen=True, slots=True)
class TelegramSettings:
    """Credentials and session location for one Pyrogram client."""

    api_id: int
    api_hash: str
    session_name: str
    session_dir: Path

    @classmethod
    def from_env(
        cls,
        *,
        session_variable: str = "TG_SESSION_NAME",
        default_session: str = "hermes_mcp",
    ) -> "TelegramSettings":
        try:
            api_id = int(os.environ["TG_API_ID"])
            api_hash = os.environ["TG_API_HASH"]
        except KeyError as exc:
            raise RuntimeError(f"Missing required Telegram setting: {exc.args[0]}") from exc
        except ValueError as exc:
            raise RuntimeError("TG_API_ID must be an integer") from exc

        session_dir = env_path("TG_SESSION_DIR", DATA_DIR)
        session_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with suppress(OSError):
            session_dir.chmod(0o700)

        return cls(
            api_id=api_id,
            api_hash=api_hash,
            session_name=os.environ.get(session_variable, default_session),
            session_dir=session_dir,
        )


def create_client(settings: TelegramSettings | None = None) -> Client:
    """Build a fresh Pyrogram client for a short-lived operation."""
    current = settings or TelegramSettings.from_env()
    return Client(
        name=current.session_name,
        api_id=current.api_id,
        api_hash=current.api_hash,
        workdir=str(current.session_dir),
    )


def send_reply(chat_id: int, message_id: int, text: str) -> dict:
    """Send one validated reply for the autonomous conversation worker."""
    text = str(text).strip()

    if not text:
        raise ValueError("Message cannot be empty")

    if len(text) > 4000:
        raise ValueError("Message exceeds 4000 characters")

    with create_client() as app:
        chat = app.get_chat(int(chat_id))
        message = app.send_message(
            chat_id=chat.id,
            text=text,
            reply_to_message_id=int(message_id),
        )

    return {
        "chat_id": message.chat.id,
        "message_id": message.id,
        "date": message.date.isoformat() if message.date else None,
        "text": text,
    }
