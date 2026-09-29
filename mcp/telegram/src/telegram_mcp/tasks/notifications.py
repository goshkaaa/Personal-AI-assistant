"""Aggregated owner notifications for autonomous Telegram tasks."""

import os
import subprocess
import time
from pathlib import Path

from ..config import env_path, load_env
from .database import database
from .task_repository import TaskRepository, task_repository

POLL_SECONDS = 10
PROGRESS_COOLDOWN_SECONDS = 1800


class OwnerNotifier:
    def __init__(self, command: str, profile_home: Path, system_home: Path) -> None:
        self.command = command
        self.profile_home = profile_home
        self.system_home = system_home

    @classmethod
    def from_env(cls) -> "OwnerNotifier":
        load_env()
        system_home = env_path("MCP_SYSTEM_HOME", Path.home())
        profile_name = os.environ.get(
            "HERMES_PROFILE_NAME",
            os.environ.get("TG_SESSION_NAME", "default"),
        )
        return cls(
            command=os.environ.get("HERMES_COMMAND", "hermes").strip() or "hermes",
            profile_home=env_path(
                "HERMES_PROFILE_HOME",
                system_home / ".hermes" / "profiles" / profile_name,
            ),
            system_home=system_home,
        )

    def send(self, text: str) -> None:
        result = subprocess.run(
            [self.command, "send", "--to", "telegram", "--quiet", text],
            env={
                "HERMES_HOME": str(self.profile_home),
                "HOME": str(self.system_home),
                "PATH": "/usr/local/bin:/usr/bin:/bin",
            },
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.strip()
                or result.stdout.strip()
                or f"hermes send exited {result.returncode}"
            )


class NotificationDispatcher:
    def __init__(self, tasks: TaskRepository, notifier: OwnerNotifier) -> None:
        self.tasks = tasks
        self.notifier = notifier

    def run_once(self) -> bool:
        rows = self.tasks.pending_notifications()
        if not rows:
            return False
        for kind in ("NEEDS_USER", "DONE", "PROGRESS"):
            self._process(kind, rows)
        return True

    def _process(self, kind: str, rows: list[dict]) -> None:
        groups: dict[int, list[dict]] = {}
        for row in rows:
            if row["notification_type"] == kind:
                groups.setdefault(row["task_id"], []).append(row)

        for task_id, group in groups.items():
            if kind == "PROGRESS" and self._progress_is_throttled(task_id):
                continue
            texts = []
            seen_texts = set()
            for row in group:
                text = (row["text"] or "").strip()
                if text and text not in seen_texts:
                    seen_texts.add(text)
                    texts.append(text)

            notification_ids = [row["id"] for row in group]
            if not texts:
                self.tasks.mark_notifications_sent(notification_ids)
                continue

            self.notifier.send(self._message(kind, group[0]["task_title"], texts))
            self.tasks.mark_notifications_sent(notification_ids)
            if kind == "PROGRESS":
                self.tasks.mark_progress(task_id)
            print(f"[NOTIFY {kind}] task={task_id} items={len(texts)}", flush=True)

    def _progress_is_throttled(self, task_id: int) -> bool:
        last_progress = self.tasks.last_progress_at(task_id)
        if not last_progress:
            return False
        try:
            timestamp = time.mktime(time.strptime(last_progress[:19], "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            return False
        return time.time() - timestamp < PROGRESS_COOLDOWN_SECONDS

    @staticmethod
    def _message(kind: str, title: str, texts: list[str]) -> str:
        labels = {
            "NEEDS_USER": "Нужна информация",
            "DONE": "Результат",
            "PROGRESS": "Промежуточный итог",
        }
        content = texts[0] if len(texts) == 1 else "\n".join(f"• {text}" for text in texts)
        return f"{labels[kind]} по задаче «{title}»:\n\n{content}"


def main() -> None:
    database.initialize()
    dispatcher = NotificationDispatcher(task_repository, OwnerNotifier.from_env())
    print("Telegram owner notification dispatcher starting", flush=True)
    while True:
        try:
            dispatcher.run_once()
        except subprocess.TimeoutExpired:
            print("[NOTIFY ERROR] hermes send timed out", flush=True)
        except Exception as exc:
            print(f"[NOTIFY ERROR] {type(exc).__name__}: {exc}", flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
