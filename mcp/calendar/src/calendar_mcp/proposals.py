"""Small private SQLite store for short-lived, idempotent calendar proposals."""

import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import closing, suppress
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    uid: str
    account_id: str
    calendar_id: str
    payload: dict[str, object]
    created_at: int
    expires_at: int
    committed_at: int | None
    receipt: dict[str, object] | None


class ProposalStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with suppress(OSError):
            path.parent.chmod(0o700)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    uid TEXT NOT NULL UNIQUE,
                    account_id TEXT NOT NULL,
                    calendar_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    committed_at INTEGER,
                    receipt_json TEXT
                );
                CREATE TABLE IF NOT EXISTS write_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    calendar_id TEXT NOT NULL,
                    uid_hash TEXT NOT NULL,
                    result TEXT NOT NULL
                );
                """
            )
            self._ensure_column(
                connection,
                table="proposals",
                column="account_id",
                definition="TEXT NOT NULL DEFAULT 'default'",
            )
            self._ensure_column(
                connection,
                table="write_audit",
                column="account_id",
                definition="TEXT NOT NULL DEFAULT 'default'",
            )
        with suppress(OSError):
            self.path.chmod(0o600)

    def create(
        self,
        *,
        account_id: str,
        calendar_id: str,
        uid: str,
        payload: dict[str, object],
        ttl_seconds: int,
    ) -> Proposal:
        now = int(time.time())
        self.purge(now=now)
        proposal_id = secrets.token_urlsafe(18)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO proposals (
                    proposal_id, uid, account_id, calendar_id, payload_json, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    uid,
                    account_id,
                    calendar_id,
                    encoded,
                    now,
                    now + ttl_seconds,
                ),
            )
        proposal = self.get(proposal_id)
        if proposal is None:  # pragma: no cover - protects against storage corruption
            raise RuntimeError("Failed to persist calendar proposal")
        return proposal

    def get(self, proposal_id: str) -> Proposal | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM proposals WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
        if row is None:
            return None
        return Proposal(
            proposal_id=row["proposal_id"],
            uid=row["uid"],
            account_id=row["account_id"],
            calendar_id=row["calendar_id"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            committed_at=row["committed_at"],
            receipt=json.loads(row["receipt_json"]) if row["receipt_json"] else None,
        )

    def mark_committed(
        self,
        proposal_id: str,
        *,
        account_id: str,
        calendar_id: str,
        uid: str,
        receipt: dict[str, object],
        result: str,
    ) -> None:
        now = int(time.time())
        encoded_receipt = json.dumps(
            receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        uid_hash = hashlib.sha256(uid.encode("utf-8")).hexdigest()[:20]
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                UPDATE proposals
                SET committed_at = ?, receipt_json = ?, payload_json = '{}'
                WHERE proposal_id = ? AND committed_at IS NULL
                """,
                (now, encoded_receipt, proposal_id),
            )
            connection.execute(
                """
                INSERT INTO write_audit (
                    created_at, action, account_id, calendar_id, uid_hash, result
                ) VALUES (?, 'create', ?, ?, ?, ?)
                """,
                (now, account_id, calendar_id, uid_hash, result),
            )

    def record_failure(
        self,
        *,
        account_id: str,
        calendar_id: str,
        uid: str,
        result: str,
    ) -> None:
        now = int(time.time())
        uid_hash = hashlib.sha256(uid.encode("utf-8")).hexdigest()[:20]
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO write_audit (
                    created_at, action, account_id, calendar_id, uid_hash, result
                ) VALUES (?, 'create', ?, ?, ?, ?)
                """,
                (now, account_id, calendar_id, uid_hash, result[:80]),
            )

    @staticmethod
    def _ensure_column(
        connection: sqlite3.Connection,
        *,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def purge(self, *, now: int | None = None) -> None:
        current = int(time.time()) if now is None else now
        receipt_cutoff = current - 24 * 60 * 60
        audit_cutoff = current - 30 * 24 * 60 * 60
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "DELETE FROM proposals WHERE committed_at IS NULL AND expires_at < ?",
                (current,),
            )
            connection.execute(
                "DELETE FROM proposals WHERE committed_at IS NOT NULL AND committed_at < ?",
                (receipt_cutoff,),
            )
            connection.execute("DELETE FROM write_audit WHERE created_at < ?", (audit_cutoff,))


def secure_database_permissions(path: Path) -> bool:
    if not path.exists():
        return True
    return os.stat(path).st_mode & 0o077 == 0
