"""Configuration for the private Apple Calendar MCP server."""

import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

BASE_DIR = Path(sys.prefix).resolve().parent
ENV_FILE = Path(os.environ.get("MCP_ENV_FILE", BASE_DIR / ".env")).expanduser().resolve()
PRIVATE_DIR = Path.home() / ".config" / "personal-ai-assistant" / "secrets"
DATA_DIR = Path.home() / ".local" / "share" / "personal-ai-assistant"
DEFAULT_SECRET_FILE = PRIVATE_DIR / "icloud-calendar-password"


class ConfigurationError(RuntimeError):
    """A safe, user-facing configuration error."""


def load_env(path: Path = ENV_FILE) -> None:
    """Load simple KEY=VALUE pairs without overriding the process environment."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    try:
        value = default if raw is None else int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value


def env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    path = Path(raw).expanduser() if raw else default.expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


@dataclass(frozen=True)
class Settings:
    username: str
    password_file: Path
    timezone_name: str
    write_calendar_id: str
    write_enabled: bool
    proposal_ttl_seconds: int
    state_db: Path
    timeout_seconds: int
    max_range_days: int
    max_results: int

    @property
    def timezone(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ConfigurationError(f"Unknown CALENDAR_TIMEZONE: {self.timezone_name}") from exc

    def read_app_password(self) -> str:
        """Read an app-specific password without ever placing it in logs or argv."""
        path = self.password_file
        if not path.exists():
            raise ConfigurationError("Apple Calendar credential is not configured on the server")
        if not path.is_file():
            raise ConfigurationError("Apple Calendar credential path is not a regular file")

        metadata = path.stat()
        if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
            raise ConfigurationError(
                "Apple Calendar credential file must be owned by the service user"
            )
        mode = stat.S_IMODE(metadata.st_mode)
        if mode & 0o077:
            raise ConfigurationError(
                "Apple Calendar credential file is too permissive; use chmod 600"
            )
        if metadata.st_size > 1024:
            raise ConfigurationError("Apple Calendar credential file is unexpectedly large")

        password = path.read_text(encoding="utf-8").strip()
        if not password:
            raise ConfigurationError("Apple Calendar credential file is empty")
        return password

    def credential_status(self) -> dict[str, object]:
        exists = self.password_file.is_file()
        private = False
        if exists:
            private = stat.S_IMODE(self.password_file.stat().st_mode) & 0o077 == 0
        return {
            "username_configured": bool(self.username),
            "password_file_exists": exists,
            "password_file_private": private,
        }


def get_settings() -> Settings:
    load_env()
    timezone_name = os.environ.get("CALENDAR_TIMEZONE", "Europe/Moscow").strip()
    settings = Settings(
        username=os.environ.get("ICLOUD_USERNAME", "").strip(),
        password_file=env_path("ICLOUD_APP_PASSWORD_FILE", DEFAULT_SECRET_FILE),
        timezone_name=timezone_name,
        write_calendar_id=os.environ.get("CALENDAR_WRITE_CALENDAR_ID", "").strip(),
        write_enabled=env_bool("MCP_ALLOW_CALENDAR_WRITE", False),
        proposal_ttl_seconds=env_int(
            "CALENDAR_PROPOSAL_TTL_SECONDS", 600, minimum=60, maximum=3600
        ),
        state_db=env_path("CALENDAR_STATE_DB", DATA_DIR / "calendar.sqlite3"),
        timeout_seconds=env_int("CALENDAR_TIMEOUT_SECONDS", 25, minimum=5, maximum=60),
        max_range_days=env_int("CALENDAR_MAX_RANGE_DAYS", 90, minimum=1, maximum=366),
        max_results=env_int("CALENDAR_MAX_RESULTS", 200, minimum=10, maximum=500),
    )
    # Validate eagerly without requiring credentials, so an unconfigured MCP can start.
    _ = settings.timezone
    return settings
