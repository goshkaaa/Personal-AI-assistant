"""Persistence for autonomous tasks, events, and owner notifications."""

import time

from .database import Database, database

CONTACT_FIELDS = {
    "state",
    "missing_fields",
    "result_summary",
    "needs_user_question",
    "clarification_count",
    "followup_count",
    "last_outgoing_at",
}


class TaskRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(
        self,
        *,
        title: str,
        goal: str,
        required_fields: str | None = None,
        silent_mode: bool = True,
    ) -> int:
        with self.db.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tasks (title, goal, required_fields, silent_mode)
                VALUES (?, ?, ?, ?)
                """,
                (title, goal, required_fields, 1 if silent_mode else 0),
            )
        return int(cursor.lastrowid)

    def find(self, task_id: int) -> dict | None:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id=?",
                (int(task_id),),
            ).fetchone()
        return dict(row) if row else None

    def list_tasks(self, status: str | None = None) -> list[dict]:
        with self.db.connect() as connection:
            if status:
                rows = connection.execute(
                    "SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = connection.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def status(self, task_id: int) -> dict:
        task = self.find(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} does not exist")
        with self.db.connect() as connection:
            contacts = connection.execute(
                """
                SELECT id, chat_id, state, missing_fields, result_summary,
                       needs_user_question, clarification_count, followup_count,
                       last_incoming_at, last_outgoing_at, next_followup_at,
                       active, created_at, updated_at
                FROM task_contacts
                WHERE task_id=?
                ORDER BY id
                """,
                (int(task_id),),
            ).fetchall()
        return {"task": task, "contacts": [dict(row) for row in contacts]}

    def cancel(self, task_id: int) -> None:
        task = self.find(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} does not exist")
        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE tasks
                SET status='CANCELLED', updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (int(task_id),),
            )
            connection.execute(
                """
                UPDATE task_contacts
                SET active=0, updated_at=CURRENT_TIMESTAMP
                WHERE task_id=?
                """,
                (int(task_id),),
            )

    def attach(self, *, task_id: int, chat_id: int) -> int:
        task = self.find(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} does not exist")
        if task["status"] != "ACTIVE":
            raise ValueError(f"Task {task_id} is not active")

        with self.db.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            conflict = connection.execute(
                """
                SELECT tc.task_id
                FROM task_contacts tc
                JOIN tasks t ON t.id=tc.task_id
                WHERE tc.chat_id=?
                  AND tc.active=1
                  AND t.status='ACTIVE'
                  AND tc.task_id<>?
                LIMIT 1
                """,
                (chat_id, task_id),
            ).fetchone()
            if conflict:
                raise ValueError(
                    f"Chat {chat_id} is already attached to active task {conflict['task_id']}"
                )

            cursor = connection.execute(
                """
                INSERT INTO task_contacts (task_id, chat_id, state)
                VALUES (?, ?, 'SILENT')
                ON CONFLICT(task_id, chat_id) DO UPDATE SET
                    active=1,
                    state='SILENT',
                    updated_at=CURRENT_TIMESTAMP
                """,
                (task_id, chat_id),
            )
            row = connection.execute(
                "SELECT id FROM task_contacts WHERE task_id=? AND chat_id=?",
                (task_id, chat_id),
            ).fetchone()
        return int(row["id"] if row else cursor.lastrowid)

    def active_contact(self, chat_id: int) -> dict | None:
        with self.db.connect() as connection:
            row = connection.execute(
                """
                SELECT tc.*, t.title AS task_title, t.goal AS task_goal,
                       t.required_fields, t.silent_mode, t.max_followups,
                       t.max_clarifications
                FROM task_contacts tc
                JOIN tasks t ON t.id = tc.task_id
                WHERE tc.chat_id=? AND tc.active=1 AND t.status='ACTIVE'
                ORDER BY tc.updated_at DESC
                LIMIT 1
                """,
                (chat_id,),
            ).fetchone()
        return dict(row) if row else None

    def queue_incoming(self, *, chat_id: int, message_id: int, text: str) -> bool:
        with self.db.connect() as connection:
            contact = connection.execute(
                """
                SELECT tc.id, tc.task_id
                FROM task_contacts tc
                JOIN tasks t ON t.id = tc.task_id
                WHERE tc.chat_id=? AND tc.active=1 AND t.status='ACTIVE'
                ORDER BY tc.updated_at DESC
                LIMIT 1
                """,
                (chat_id,),
            ).fetchone()
            if not contact:
                return False

            connection.execute(
                """
                UPDATE task_contacts
                SET last_incoming_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (contact["id"],),
            )
            cursor = connection.execute(
                """
                INSERT INTO task_events (
                    task_id, task_contact_id, chat_id, message_id, event_type, payload
                )
                VALUES (?, ?, ?, ?, 'INCOMING_MESSAGE', ?)
                ON CONFLICT(task_id, chat_id, message_id, event_type) DO NOTHING
                """,
                (contact["task_id"], contact["id"], chat_id, message_id, text),
            )
        return cursor.rowcount == 1

    def claim_event(self) -> dict | None:
        with self.db.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""
                UPDATE task_events
                SET processed=0,
                    claimed_at=NULL,
                    last_error=COALESCE(last_error, 'worker lease expired')
                WHERE processed=2
                  AND claimed_at < datetime('now', '-10 minutes')
            """)
            row = connection.execute("""
                SELECT e.*, t.title AS task_title, t.goal AS task_goal,
                       t.required_fields, t.silent_mode, t.max_followups,
                       t.max_clarifications, tc.state, tc.followup_count,
                       tc.clarification_count, tc.missing_fields, tc.result_summary
                FROM task_events e
                JOIN tasks t ON t.id = e.task_id
                JOIN task_contacts tc ON tc.id = e.task_contact_id
                WHERE e.processed=0
                  AND (e.next_attempt_at IS NULL OR e.next_attempt_at <= CURRENT_TIMESTAMP)
                  AND t.status='ACTIVE'
                  AND tc.active=1
                  AND NOT EXISTS (
                      SELECT 1 FROM task_events claimed
                      WHERE claimed.task_contact_id=e.task_contact_id
                        AND claimed.processed=2
                  )
                ORDER BY e.created_at ASC, e.id ASC
                LIMIT 1
            """).fetchone()
            if not row:
                return None

            claimed = connection.execute(
                """
                UPDATE task_events
                SET processed=2, claimed_at=CURRENT_TIMESTAMP,
                    next_attempt_at=NULL, last_error=NULL
                WHERE id=? AND processed=0
                """,
                (row["id"],),
            )
            return dict(row) if claimed.rowcount == 1 else None

    def finish_event(self, event_id: int) -> None:
        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE task_events
                SET processed=1, processed_at=CURRENT_TIMESTAMP,
                    claimed_at=NULL, next_attempt_at=NULL, last_error=NULL
                WHERE id=?
                """,
                (int(event_id),),
            )

    def release_event(self, event_id: int, error: str) -> None:
        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE task_events
                SET processed=0,
                    claimed_at=NULL,
                    attempt_count=attempt_count + 1,
                    next_attempt_at=datetime(
                        'now',
                        '+' || CASE
                            WHEN attempt_count=0 THEN 5
                            WHEN attempt_count=1 THEN 15
                            WHEN attempt_count=2 THEN 60
                            ELSE 300
                        END || ' seconds'
                    ),
                    last_error=?
                WHERE id=? AND processed=2
                """,
                (str(error)[:2000], int(event_id)),
            )

    def event_is_claimed(self, event_id: int) -> bool:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT processed FROM task_events WHERE id=?",
                (int(event_id),),
            ).fetchone()
        return bool(row and row["processed"] == 2)

    def update_contact(self, contact_id: int, **fields: object) -> None:
        values_by_name = {key: value for key, value in fields.items() if key in CONTACT_FIELDS}
        if not values_by_name:
            return
        values_by_name["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        assignments = ", ".join(f"{key}=?" for key in values_by_name)
        values = [*values_by_name.values(), int(contact_id)]
        with self.db.connect() as connection:
            connection.execute(
                f"UPDATE task_contacts SET {assignments} WHERE id=?",
                values,
            )

    def complete_contact(self, contact_id: int) -> None:
        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE task_contacts
                SET active=0, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (int(contact_id),),
            )
            connection.execute(
                """
                UPDATE task_events
                SET processed=1, processed_at=CURRENT_TIMESTAMP,
                    claimed_at=NULL, last_error='contact already completed'
                WHERE task_contact_id=? AND processed=0
                """,
                (int(contact_id),),
            )

    def completion_state(self, task_id: int) -> tuple[int, list[dict]]:
        with self.db.connect() as connection:
            remaining = connection.execute(
                "SELECT COUNT(*) AS count FROM task_contacts WHERE task_id=? AND active=1",
                (int(task_id),),
            ).fetchone()["count"]
            contacts = connection.execute(
                """
                SELECT chat_id, state, result_summary
                FROM task_contacts
                WHERE task_id=?
                ORDER BY id
                """,
                (int(task_id),),
            ).fetchall()
        return int(remaining), [dict(contact) for contact in contacts]

    def complete_task(self, task_id: int) -> None:
        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE tasks
                SET status='DONE', completed_at=CURRENT_TIMESTAMP,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (int(task_id),),
            )

    def queue_notification(self, task_id: int, kind: str, text: str) -> None:
        if not text:
            return
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO notifications(task_id, notification_type, text)
                VALUES (?, ?, ?)
                """,
                (int(task_id), kind, text),
            )

    def pending_notifications(self) -> list[dict]:
        with self.db.connect() as connection:
            rows = connection.execute("""
                SELECT n.id, n.task_id, n.notification_type, n.text,
                       n.created_at, t.title AS task_title
                FROM notifications n
                JOIN tasks t ON t.id = n.task_id
                WHERE n.sent=0
                ORDER BY CASE n.notification_type
                    WHEN 'NEEDS_USER' THEN 1
                    WHEN 'DONE' THEN 2
                    WHEN 'PROGRESS' THEN 3
                    ELSE 4
                END, n.created_at ASC
            """).fetchall()
        return [dict(row) for row in rows]

    def mark_notifications_sent(self, notification_ids: list[int]) -> None:
        if not notification_ids:
            return
        placeholders = ",".join("?" for _ in notification_ids)
        with self.db.connect() as connection:
            connection.execute(
                f"UPDATE notifications SET sent=1, sent_at=CURRENT_TIMESTAMP "
                f"WHERE id IN ({placeholders})",
                notification_ids,
            )

    def last_progress_at(self, task_id: int) -> str | None:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT MAX(last_progress_at) AS value FROM task_contacts WHERE task_id=?",
                (int(task_id),),
            ).fetchone()
        return row["value"] if row else None

    def mark_progress(self, task_id: int) -> None:
        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE task_contacts
                SET last_progress_at=CURRENT_TIMESTAMP
                WHERE task_id=?
                """,
                (int(task_id),),
            )


task_repository = TaskRepository(database)
