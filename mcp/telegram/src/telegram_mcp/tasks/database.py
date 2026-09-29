"""Private SQLite database used by Telegram background tasks."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from ..config import DATA_DIR, env_path, private_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    date TEXT,
    direction TEXT NOT NULL,
    sender_id INTEGER,
    sender_name TEXT,
    sender_username TEXT,
    chat_title TEXT,
    chat_username TEXT,
    text TEXT,
    reply_to_message_id INTEGER,
    PRIMARY KEY (chat_id, message_id)
);
CREATE INDEX IF NOT EXISTS idx_messages_chat_date ON messages(chat_id, date);

CREATE TABLE IF NOT EXISTS managed_chats (
    chat_id INTEGER PRIMARY KEY,
    chat_title TEXT,
    chat_username TEXT,
    reason TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    goal TEXT NOT NULL,
    required_fields TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    silent_mode INTEGER NOT NULL DEFAULT 1,
    notification_cooldown_minutes INTEGER NOT NULL DEFAULT 30,
    max_followups INTEGER NOT NULL DEFAULT 1,
    max_clarifications INTEGER NOT NULL DEFAULT 2,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

CREATE TABLE IF NOT EXISTS task_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'SILENT',
    missing_fields TEXT,
    result_summary TEXT,
    needs_user_question TEXT,
    clarification_count INTEGER NOT NULL DEFAULT 0,
    followup_count INTEGER NOT NULL DEFAULT 0,
    last_incoming_at TEXT,
    last_outgoing_at TEXT,
    last_progress_at TEXT,
    next_followup_at TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, chat_id),
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);
CREATE INDEX IF NOT EXISTS idx_task_contacts_task ON task_contacts(task_id);
CREATE INDEX IF NOT EXISTS idx_task_contacts_chat ON task_contacts(chat_id);
CREATE INDEX IF NOT EXISTS idx_task_contacts_state ON task_contacts(state);

CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    task_contact_id INTEGER,
    chat_id INTEGER,
    message_id INTEGER,
    event_type TEXT NOT NULL,
    payload TEXT,
    processed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    processed_at TEXT,
    claimed_at TEXT,
    last_error TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(id),
    FOREIGN KEY(task_contact_id) REFERENCES task_contacts(id)
);
CREATE INDEX IF NOT EXISTS idx_task_events_pending ON task_events(processed, created_at);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    notification_type TEXT NOT NULL,
    text TEXT NOT NULL,
    sent INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    sent_at TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);
CREATE INDEX IF NOT EXISTS idx_notifications_unsent ON notifications(sent, created_at);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        private_path(self.path)
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=30000")
            self._secure_files()
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            self._migrate_events(connection)
        self._secure_files()

    def _migrate_events(self, connection: sqlite3.Connection) -> None:
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(task_events)").fetchall()
        }
        additions = {
            "claimed_at": "TEXT",
            "last_error": "TEXT",
            "attempt_count": "INTEGER NOT NULL DEFAULT 0",
            "next_attempt_at": "TEXT",
        }
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE task_events ADD COLUMN {name} {definition}")

        connection.execute("""
            DELETE FROM task_events
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM task_events
                GROUP BY task_id, chat_id, message_id, event_type
            )
        """)
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_task_events_message
            ON task_events(task_id, chat_id, message_id, event_type)
        """)

    def _secure_files(self) -> None:
        private_path(self.path)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(f"{self.path}{suffix}")
            if sidecar.exists():
                with suppress(OSError):
                    sidecar.chmod(0o600)


database = Database(env_path("MCP_DB_PATH", DATA_DIR / "conversations.db"))
