import os
import sqlite3
import stat
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

# Import-time schema initialization must never touch the real conversation DB.
_IMPORT_TEMP = tempfile.TemporaryDirectory()
os.environ["MCP_DB_PATH"] = str(Path(_IMPORT_TEMP.name) / "import.db")

from telegram_mcp.tasks.database import database  # noqa: E402
from telegram_mcp.tasks.task_repository import task_repository  # noqa: E402


class StorageInvariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        database.path = Path(self.temporary.name) / "conversations.db"
        database.initialize()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _queue_event(self, *, chat_id: int = 42, message_id: int = 100) -> int:
        task_id = task_repository.create(title="price", goal="collect a quote")
        task_repository.attach(task_id=task_id, chat_id=chat_id)
        queued = task_repository.queue_incoming(
            chat_id=chat_id,
            message_id=message_id,
            text="hello",
        )
        self.assertTrue(queued)
        return task_id

    def test_database_is_private_and_enforces_foreign_keys(self) -> None:
        mode = stat.S_IMODE(database.path.stat().st_mode)
        self.assertEqual(mode, 0o600)

        with database.connect() as db:
            self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    "INSERT INTO task_contacts(task_id, chat_id) VALUES (?, ?)",
                    (999_999, 42),
                )
        with self.assertRaises(sqlite3.ProgrammingError):
            db.execute("SELECT 1")

    def test_listener_replay_does_not_duplicate_an_event(self) -> None:
        task_id = self._queue_event()
        duplicate = task_repository.queue_incoming(
            chat_id=42,
            message_id=100,
            text="hello again",
        )
        self.assertFalse(duplicate)

        with database.connect() as db:
            count = db.execute(
                "SELECT COUNT(*) FROM task_events WHERE task_id=?",
                (task_id,),
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_two_workers_cannot_claim_the_same_event(self) -> None:
        self._queue_event()
        barrier = threading.Barrier(2)

        def claim_after_barrier():
            barrier.wait()
            return task_repository.claim_event()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: claim_after_barrier(), range(2)))

        claimed = [result for result in results if result is not None]
        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0]["message_id"], 100)

    def test_failed_event_is_backed_off_before_reclaim(self) -> None:
        self._queue_event()
        event = task_repository.claim_event()
        self.assertIsNotNone(event)

        task_repository.release_event(event["id"], "temporary failure")
        self.assertIsNone(task_repository.claim_event())

        with database.connect() as db:
            row = db.execute(
                "SELECT attempt_count, last_error FROM task_events WHERE id=?",
                (event["id"],),
            ).fetchone()
        self.assertEqual(row["attempt_count"], 1)
        self.assertEqual(row["last_error"], "temporary failure")

    def test_one_chat_cannot_silently_feed_two_active_tasks(self) -> None:
        first_task = task_repository.create(title="first", goal="first goal")
        second_task = task_repository.create(title="second", goal="second goal")
        task_repository.attach(task_id=first_task, chat_id=42)

        with self.assertRaisesRegex(ValueError, "already attached"):
            task_repository.attach(task_id=second_task, chat_id=42)


if __name__ == "__main__":
    unittest.main()
