"""Long-running Telegram update listener.

Only chats managed by this service are recorded. The listener never answers
messages itself; autonomous decisions are queued for the worker.
"""

from pyrogram import filters
from pyrogram.handlers import MessageHandler

from .client import TelegramSettings, create_client
from .serializers import log_message
from .tasks.conversations import conversations
from .tasks.database import database
from .tasks.task_repository import task_repository


def incoming_message(_client, message) -> None:
    if not conversations.is_managed(message.chat.id):
        return

    log_message(message)
    direction = "OUT" if message.outgoing else "IN"
    queued = False

    if not message.outgoing:
        queued = task_repository.queue_incoming(
            chat_id=message.chat.id,
            message_id=message.id,
            text=message.text or message.caption or "",
        )

    print(
        f"[{direction}] "
        f"chat={message.chat.id} "
        f"message={message.id} "
        f"task_event={'yes' if queued else 'no'}",
        flush=True,
    )


def create_listener():
    """Create the dedicated listener client without connecting at import time."""
    settings = TelegramSettings.from_env(
        session_variable="TG_LISTENER_SESSION_NAME",
        default_session="hermes_listener",
    )
    app = create_client(settings)
    app.add_handler(MessageHandler(incoming_message, filters.all))
    return app


def main() -> None:
    print("Telegram event listener starting...", flush=True)
    database.initialize()
    create_listener().run()


if __name__ == "__main__":
    main()
