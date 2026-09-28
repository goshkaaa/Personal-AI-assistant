"""Obsidian MCP settings."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(sys.prefix).resolve().parent
ENV_FILE = Path(os.environ.get("MCP_ENV_FILE", BASE_DIR / ".env")).expanduser().resolve()


def load_env(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip():
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class ObsidianSettings:
    vault: Path
    hermes_command: str

    @classmethod
    def from_env(cls) -> "ObsidianSettings":
        load_env()
        return cls(
            vault=Path(os.environ.get("OBSIDIAN_VAULT_PATH", "~/Obsidian")).expanduser().resolve(),
            hermes_command=os.environ.get("HERMES_COMMAND", "hermes").strip() or "hermes",
        )
