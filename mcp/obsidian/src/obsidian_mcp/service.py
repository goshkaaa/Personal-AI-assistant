"""Operations on one Obsidian vault."""

import os
import subprocess
from datetime import datetime
from pathlib import Path

from .config import ObsidianSettings
from .security import reject_secrets, safe_title


class ObsidianVault:
    def __init__(self, settings: ObsidianSettings) -> None:
        self.settings = settings

    @classmethod
    def from_env(cls) -> "ObsidianVault":
        return cls(ObsidianSettings.from_env())

    @property
    def path(self) -> Path:
        return self.settings.vault

    def note_path(self, title: str) -> Path:
        path = (self.path / f"{safe_title(title)}.md").resolve()
        if self.path not in path.parents:
            raise ValueError("Invalid note path")
        return path

    def create(self, title: str, content: str = "") -> dict:
        title = safe_title(title)
        content = str(content).strip()
        reject_secrets(content)
        path = self.note_path(title)
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        body = f"# {title}\n\n> Создано Hermes: {self._now()}\n"
        if content:
            body += f"\n{content}\n"
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return {"created": False, "exists": True, "title": title, "path": str(path)}
        with os.fdopen(descriptor, "w", encoding="utf-8") as note:
            note.write(body)
        return {"created": True, "exists": False, "title": title, "path": str(path)}

    def update(self, title: str, content: str, section: str = "") -> dict:
        title = safe_title(title)
        content = str(content).strip()
        section = str(section).strip()
        if not content:
            raise ValueError("Content cannot be empty")
        reject_secrets(content)

        path = self.note_path(title)
        if not path.exists():
            self.create(title)

        addition = "\n\n"
        if section:
            addition += f"## {section}\n\n"
        addition += f"{content}\n\n_Обновлено: {self._now()}_\n"
        with path.open("a", encoding="utf-8") as note:
            note.write(addition)
        return {
            "updated": True,
            "title": title,
            "path": str(path),
            "section": section or None,
        }

    def get(self, title: str) -> dict:
        title = safe_title(title)
        path = self.note_path(title)
        if not path.exists():
            return {"found": False, "title": title}
        return {
            "found": True,
            "title": title,
            "path": str(path),
            "content": path.read_text(encoding="utf-8"),
        }

    def list(self, query: str = "") -> list[dict]:
        query = str(query).strip().casefold()
        results = []
        for path in sorted(self.path.glob("*.md")):
            if (
                query
                and query not in path.stem.casefold()
                and query not in path.read_text(encoding="utf-8", errors="replace").casefold()
            ):
                continue
            metadata = path.stat()
            results.append(
                {
                    "title": path.stem,
                    "path": str(path),
                    "size": metadata.st_size,
                    "modified": datetime.fromtimestamp(metadata.st_mtime).isoformat(
                        timespec="seconds"
                    ),
                }
            )
        return results

    def send(self, title: str) -> dict:
        title = safe_title(title)
        path = self.note_path(title)
        if not path.exists():
            return {
                "sent": False,
                "found": False,
                "title": title,
                "reason": "Note not found",
            }

        result = subprocess.run(
            [self.settings.hermes_command, "send", "--to", "telegram", "--quiet", f"MEDIA:{path}"],
            env=os.environ.copy(),
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
        return {"sent": True, "found": True, "title": title, "filename": path.name}

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M")
