"""Persistence for Telegram messages and managed chats."""

from .database import Database, database


class ConversationRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_message(
        self,
        *,
        chat_id: int,
        message_id: int,
        date: str | None,
        direction: str,
        sender_id: int | None,
        sender_name: str | None,
        sender_username: str | None,
        chat_title: str | None,
        chat_username: str | None,
        text: str,
        reply_to_message_id: int | None,
    ) -> None:
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO messages (
                    chat_id, message_id, date, direction,
                    sender_id, sender_name, sender_username,
                    chat_title, chat_username, text, reply_to_message_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, message_id) DO UPDATE SET
                    date=excluded.date,
                    direction=excluded.direction,
                    sender_id=excluded.sender_id,
                    sender_name=excluded.sender_name,
                    sender_username=excluded.sender_username,
                    chat_title=excluded.chat_title,
                    chat_username=excluded.chat_username,
                    text=excluded.text,
                    reply_to_message_id=excluded.reply_to_message_id
                """,
                (
                    chat_id,
                    message_id,
                    date,
                    direction,
                    sender_id,
                    sender_name,
                    sender_username,
                    chat_title,
                    chat_username,
                    text,
                    reply_to_message_id,
                ),
            )

    def mark_managed(
        self,
        chat_id: int,
        chat_title: str | None,
        chat_username: str | None,
        reason: str = "owner",
    ) -> None:
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO managed_chats (
                    chat_id, chat_title, chat_username, reason, active
                )
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(chat_id) DO UPDATE SET
                    chat_title=excluded.chat_title,
                    chat_username=excluded.chat_username,
                    reason=excluded.reason,
                    active=1,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (chat_id, chat_title, chat_username, reason),
            )

    def is_managed(self, chat_id: int) -> bool:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT active FROM managed_chats WHERE chat_id=?",
                (chat_id,),
            ).fetchone()
        return bool(row and row["active"])

    def managed_chats(self) -> list[dict]:
        with self.db.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM managed_chats
                WHERE active=1
                ORDER BY updated_at DESC
            """).fetchall()
        return [dict(row) for row in rows]

    def messages(self, chat_id: int, limit: int = 50) -> list[dict]:
        limit = max(1, min(int(limit), 200))
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM (
                    SELECT * FROM messages
                    WHERE chat_id=?
                    ORDER BY date DESC, message_id DESC
                    LIMIT ?
                )
                ORDER BY date ASC, message_id ASC
                """,
                (chat_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]


conversations = ConversationRepository(database)
