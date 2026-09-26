"""Shared configuration helpers for the personal MCP services.

The services are often launched by systemd with a very small environment, so
they may load a local ``.env`` file.  Paths remain overridable to keep the
checkout portable and to make offline tests independent from production data.
"""

import os
import sys
from contextlib import suppress
from pathlib import Path

BASE_DIR = Path(sys.prefix).resolve().parent
ENV_FILE = Path(os.environ.get("MCP_ENV_FILE", BASE_DIR / ".env")).expanduser().resolve()
PRIVATE_DIR = Path.home() / ".config" / "personal-ai-assistant" / "secrets"
DATA_DIR = Path.home() / ".local" / "share" / "personal-ai-assistant" / "telegram"


def load_env(path: Path = ENV_FILE, *, required: bool = False) -> None:
    """Load simple KEY=VALUE entries without overwriting process settings."""
    if not path.exists():
        if required:
            raise RuntimeError(f"Environment file not found: {path}")
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def env_path(name: str, default: Path) -> Path:
    """Return an expanded absolute path; relative settings use ``BASE_DIR``."""
    raw = os.environ.get(name)
    path = Path(raw).expanduser() if raw else default.expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def private_path(path: Path) -> Path:
    """Create a private parent directory and normalize existing file modes."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with suppress(OSError):
        path.parent.chmod(0o700)

    if path.exists():
        with suppress(OSError):
            path.chmod(0o600)
    return path


# Importing a service module should see the same local configuration. Explicit
# process environment values still win because ``load_env`` uses setdefault.
load_env()
