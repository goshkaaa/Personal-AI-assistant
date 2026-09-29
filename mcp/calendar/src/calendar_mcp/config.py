"""Validated configuration for one or more calendar accounts."""

import json
import os
import re
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeAlias
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

BASE_DIR = Path(sys.prefix).resolve().parent
ENV_FILE = Path(os.environ.get("MCP_ENV_FILE", BASE_DIR / ".env")).expanduser().resolve()
PRIVATE_DIR = Path.home() / ".config" / "personal-ai-assistant" / "secrets"
DATA_DIR = Path.home() / ".local" / "share" / "personal-ai-assistant"
ACCOUNT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

CALDAV_URLS = {
    "icloud": "https://caldav.icloud.com/",
    "yandex": "https://caldav.yandex.ru/",
    "mailru": "https://calendar.mail.ru/",
}


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
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer") from error
    return bounded_int(value, name, minimum=minimum, maximum=maximum)


def bounded_int(value: Any, name: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value


def env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    path = Path(raw).expanduser() if raw else default.expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as error:
        raise ConfigurationError(f"Unknown calendar timezone: {value}") from error


def read_private_secret(path: Path, *, label: str, maximum_bytes: int = 4096) -> str:
    if not path.exists():
        raise ConfigurationError(f"{label} credential is not configured")
    if not path.is_file():
        raise ConfigurationError(f"{label} credential path is not a regular file")
    metadata = path.stat()
    if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
        raise ConfigurationError(f"{label} credential file must be owned by the service user")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ConfigurationError(f"{label} credential file is too permissive; use chmod 600")
    if metadata.st_size > maximum_bytes:
        raise ConfigurationError(f"{label} credential file is unexpectedly large")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ConfigurationError(f"{label} credential file is empty")
    return value


def file_status(path: Path) -> dict[str, bool]:
    exists = path.is_file()
    private = exists and stat.S_IMODE(path.stat().st_mode) & 0o077 == 0
    return {"file_exists": exists, "file_private": private}


@dataclass(frozen=True)
class CalDavAccountSettings:
    account_id: str
    label: str
    username: str
    password_file: Path
    url: str
    timezone_name: str
    write_calendar_id: str = ""
    write_enabled: bool = False
    disable_http3: bool = False
    provider: Literal["icloud", "yandex", "mailru", "caldav"] = "caldav"

    @property
    def timezone(self) -> ZoneInfo:
        return timezone(self.timezone_name)

    def read_password(self) -> str:
        return read_private_secret(self.password_file, label=self.label)

    def credential_status(self) -> dict[str, object]:
        return {"username_configured": bool(self.username), **file_status(self.password_file)}


@dataclass(frozen=True)
class GoogleAccountSettings:
    account_id: str
    label: str
    credentials_file: Path
    token_file: Path
    timezone_name: str
    write_calendar_id: str = ""
    write_enabled: bool = False
    provider: Literal["google"] = field(default="google", init=False)

    @property
    def timezone(self) -> ZoneInfo:
        return timezone(self.timezone_name)

    def credential_status(self) -> dict[str, object]:
        credentials_exist = self.credentials_file.is_file()
        token_exists = self.token_file.is_file()
        return {
            "oauth_client_configured": credentials_exist,
            "oauth_client_private": (
                credentials_exist
                and stat.S_IMODE(self.credentials_file.stat().st_mode) & 0o077 == 0
            ),
            "oauth_token_configured": token_exists,
            "oauth_token_private": (
                token_exists and stat.S_IMODE(self.token_file.stat().st_mode) & 0o077 == 0
            ),
        }


CalendarAccountSettings: TypeAlias = CalDavAccountSettings | GoogleAccountSettings


@dataclass(frozen=True)
class Settings:
    accounts: tuple[CalendarAccountSettings, ...]
    default_account_id: str
    proposal_ttl_seconds: int
    state_db: Path
    timeout_seconds: int
    max_range_days: int
    max_results: int

    @classmethod
    def from_file(cls, path: Path) -> "Settings":
        return _settings_from_file(path.expanduser().resolve())

    def account(self, account_id: str | None = None) -> CalendarAccountSettings:
        selected_id = account_id or self.default_account_id
        for account in self.accounts:
            if account.account_id == selected_id:
                return account
        available = ", ".join(account.account_id for account in self.accounts)
        raise ConfigurationError(
            f"Unknown calendar account {selected_id!r}. Available accounts: {available}"
        )


def get_settings() -> Settings:
    load_env()
    accounts_file = env_path(
        "CALENDAR_ACCOUNTS_FILE",
        PRIVATE_DIR / "calendar-accounts.json",
    )
    if accounts_file.is_file():
        return Settings.from_file(accounts_file)
    if "CALENDAR_ACCOUNTS_FILE" in os.environ:
        raise ConfigurationError(f"Calendar accounts file not found: {accounts_file}")
    return _legacy_settings()


def _settings_from_file(path: Path) -> Settings:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigurationError(f"Cannot read calendar accounts file {path}: {error}") from error
    if not isinstance(raw, dict) or not isinstance(raw.get("accounts"), list):
        raise ConfigurationError("Calendar accounts file must contain an 'accounts' array")

    default_timezone = _optional_string(raw, "timezone") or "Europe/Moscow"
    _ = timezone(default_timezone)
    accounts = tuple(
        _parse_account(item, path.parent, default_timezone=default_timezone)
        for item in raw["accounts"]
    )
    if not accounts:
        raise ConfigurationError("At least one calendar account must be configured")
    account_ids = [account.account_id for account in accounts]
    if len(account_ids) != len(set(account_ids)):
        raise ConfigurationError("Calendar account IDs must be unique")
    default_account_id = raw.get("default_account") or account_ids[0]
    if default_account_id not in account_ids:
        raise ConfigurationError(f"Unknown default calendar account: {default_account_id!r}")

    return Settings(
        accounts=accounts,
        default_account_id=default_account_id,
        proposal_ttl_seconds=bounded_int(
            raw.get("proposal_ttl_seconds", 600),
            "proposal_ttl_seconds",
            minimum=60,
            maximum=3600,
        ),
        state_db=_path(raw, "state_db", path.parent, DATA_DIR / "calendar.sqlite3"),
        timeout_seconds=bounded_int(
            raw.get("timeout_seconds", 25),
            "timeout_seconds",
            minimum=5,
            maximum=60,
        ),
        max_range_days=bounded_int(
            raw.get("max_range_days", 90),
            "max_range_days",
            minimum=1,
            maximum=366,
        ),
        max_results=bounded_int(
            raw.get("max_results", 200),
            "max_results",
            minimum=10,
            maximum=500,
        ),
    )


def _legacy_settings() -> Settings:
    timezone_name = os.environ.get("CALENDAR_TIMEZONE", "Europe/Moscow").strip()
    _ = timezone(timezone_name)
    account = CalDavAccountSettings(
        account_id="default",
        label="iCloud Calendar",
        provider="icloud",
        username=os.environ.get("ICLOUD_USERNAME", "").strip(),
        password_file=env_path(
            "ICLOUD_APP_PASSWORD_FILE",
            PRIVATE_DIR / "icloud-calendar-password",
        ),
        url=CALDAV_URLS["icloud"],
        timezone_name=timezone_name,
        write_calendar_id=os.environ.get("CALENDAR_WRITE_CALENDAR_ID", "").strip(),
        write_enabled=env_bool("MCP_ALLOW_CALENDAR_WRITE", False),
        disable_http3=True,
    )
    return Settings(
        accounts=(account,),
        default_account_id=account.account_id,
        proposal_ttl_seconds=env_int(
            "CALENDAR_PROPOSAL_TTL_SECONDS", 600, minimum=60, maximum=3600
        ),
        state_db=env_path("CALENDAR_STATE_DB", DATA_DIR / "calendar.sqlite3"),
        timeout_seconds=env_int("CALENDAR_TIMEOUT_SECONDS", 25, minimum=5, maximum=60),
        max_range_days=env_int("CALENDAR_MAX_RANGE_DAYS", 90, minimum=1, maximum=366),
        max_results=env_int("CALENDAR_MAX_RESULTS", 200, minimum=10, maximum=500),
    )


def _parse_account(
    raw: Any,
    base_dir: Path,
    *,
    default_timezone: str,
) -> CalendarAccountSettings:
    if not isinstance(raw, dict):
        raise ConfigurationError("Each calendar account must be an object")
    account_id = _required_string(raw, "id")
    if not ACCOUNT_ID_PATTERN.fullmatch(account_id):
        raise ConfigurationError(
            f"Invalid calendar account ID {account_id!r}; use lowercase letters, digits, _ or -"
        )
    provider = _required_string(raw, "provider")
    label = _optional_string(raw, "label") or account_id
    timezone_name = _optional_string(raw, "timezone") or default_timezone
    _ = timezone(timezone_name)
    write_calendar_id = _optional_string(raw, "write_calendar_id") or ""
    write_enabled = _bool(raw, "allow_write", default=False)

    if provider == "google":
        return GoogleAccountSettings(
            account_id=account_id,
            label=label,
            credentials_file=_path(raw, "credentials_file", base_dir),
            token_file=_path(
                raw,
                "token_file",
                base_dir,
                PRIVATE_DIR / f"google-calendar-{account_id}-token.json",
            ),
            timezone_name=timezone_name,
            write_calendar_id=write_calendar_id,
            write_enabled=write_enabled,
        )

    if provider in {"icloud", "yandex", "mailru", "caldav"}:
        url = _optional_string(raw, "url") or CALDAV_URLS.get(provider, "")
        _validate_caldav_url(url)
        username = _required_string(raw, "username")
        return CalDavAccountSettings(
            account_id=account_id,
            label=label,
            provider=provider,
            username=username,
            password_file=_path(raw, "password_file", base_dir),
            url=url,
            timezone_name=timezone_name,
            write_calendar_id=write_calendar_id,
            write_enabled=write_enabled,
            disable_http3=_bool(raw, "disable_http3", default=provider == "icloud"),
        )

    raise ConfigurationError(
        f"Unsupported calendar provider {provider!r} for account {account_id!r}"
    )


def _validate_caldav_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ConfigurationError("CalDAV URL must be an HTTPS URL without embedded credentials")


def _required_string(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"Calendar account field {key!r} must be a non-empty string")
    return value.strip()


def _optional_string(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigurationError(f"Calendar account field {key!r} must be a string")
    return value.strip() or None


def _bool(raw: dict[str, Any], key: str, *, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ConfigurationError(f"Calendar account field {key!r} must be a boolean")
    return value


def _path(
    raw: dict[str, Any],
    key: str,
    base_dir: Path,
    default: Path | None = None,
) -> Path:
    value = raw.get(key)
    if value is None and default is None:
        raise ConfigurationError(f"Calendar account field {key!r} is required")
    if value is not None and not isinstance(value, str):
        raise ConfigurationError(f"Calendar account field {key!r} must be a path string")
    selected = Path(value).expanduser() if value else default
    if selected is None:
        raise ConfigurationError(f"Calendar account field {key!r} is required")
    if not selected.is_absolute():
        selected = base_dir / selected
    return selected.resolve()


load_env()
