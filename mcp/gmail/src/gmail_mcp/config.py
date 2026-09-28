"""Local Gmail settings."""

import os
import sys
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(sys.prefix).resolve().parent
ENV_FILE = Path(os.environ.get("MCP_ENV_FILE", BASE_DIR / ".env")).expanduser().resolve()
PRIVATE_DIR = Path.home() / ".config" / "personal-ai-assistant" / "secrets"


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


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    path = Path(raw).expanduser() if raw else default.expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def private_path(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with suppress(OSError):
        path.parent.chmod(0o700)
    if path.exists():
        with suppress(OSError):
            path.chmod(0o600)
    return path


@dataclass(frozen=True)
class GmailSettings:
    credentials_file: Path
    token_file: Path
    allow_send: bool

    @classmethod
    def from_env(cls) -> "GmailSettings":
        load_env()
        return cls(
            credentials_file=env_path(
                "GMAIL_CREDENTIALS_FILE",
                PRIVATE_DIR / "gmail-credentials.json",
            ),
            token_file=env_path(
                "GMAIL_TOKEN_FILE",
                PRIVATE_DIR / "gmail-token.json",
            ),
            allow_send=env_bool("MCP_ALLOW_EMAIL_SEND"),
        )


load_env()
