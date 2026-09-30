"""Home Assistant configuration and credential handling."""

import os
import stat
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(sys.prefix).resolve().parent
ENV_FILE = Path(os.environ.get("MCP_ENV_FILE", BASE_DIR / ".env")).expanduser().resolve()
DEFAULT_TOKEN_FILE = (
    Path.home() / ".config" / "personal-ai-assistant" / "secrets" / "home-assistant-token"
)
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "personal-ai-assistant" / "homeassistant"


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


def env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    try:
        value = default if raw is None else int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


def env_path(name: str, default: Path) -> Path:
    value = Path(os.environ.get(name, str(default))).expanduser()
    if not value.is_absolute():
        value = BASE_DIR / value
    return value.resolve()


@dataclass(frozen=True)
class HomeAssistantSettings:
    url: str
    token_file: Path
    token_from_environment: str
    allow_write: bool
    timeout_seconds: int
    reverse_geocoding_url: str = ""
    reverse_geocoding_language: str = "ru"

    @classmethod
    def from_env(cls) -> "HomeAssistantSettings":
        load_env()
        token_path = Path(
            os.environ.get("HOME_ASSISTANT_TOKEN_FILE", str(DEFAULT_TOKEN_FILE))
        ).expanduser()
        if not token_path.is_absolute():
            token_path = BASE_DIR / token_path

        url = os.environ.get("HOME_ASSISTANT_URL", "").strip().rstrip("/")
        if url and urllib.parse.urlsplit(url).scheme not in {"http", "https"}:
            raise RuntimeError("HOME_ASSISTANT_URL must use http or https")

        reverse_geocoding_url = os.environ.get("HOME_ASSISTANT_REVERSE_GEOCODING_URL", "").strip()
        if reverse_geocoding_url:
            parsed_geocoder = urllib.parse.urlsplit(reverse_geocoding_url)
            if parsed_geocoder.scheme != "https" and parsed_geocoder.hostname not in {
                "127.0.0.1",
                "localhost",
            }:
                raise RuntimeError(
                    "HOME_ASSISTANT_REVERSE_GEOCODING_URL must use https or localhost"
                )

        return cls(
            url=url,
            token_file=token_path.resolve(),
            token_from_environment=os.environ.get("HOME_ASSISTANT_TOKEN", "").strip(),
            allow_write=env_bool("MCP_ALLOW_HOME_ASSISTANT_WRITE"),
            timeout_seconds=env_int(
                "HOME_ASSISTANT_TIMEOUT_SECONDS",
                15,
                minimum=1,
                maximum=60,
            ),
            reverse_geocoding_url=reverse_geocoding_url,
            reverse_geocoding_language=os.environ.get(
                "HOME_ASSISTANT_REVERSE_GEOCODING_LANGUAGE", "ru"
            ).strip()
            or "ru",
        )

    def read_token(self) -> str:
        if self.token_from_environment:
            return self.token_from_environment
        if not self.token_file.is_file():
            raise RuntimeError("Home Assistant credential is not configured")

        metadata = self.token_file.stat()
        if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
            raise RuntimeError("Home Assistant token file must be owned by the service user")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise RuntimeError("Home Assistant token file is too permissive; use chmod 600")

        token = self.token_file.read_text(encoding="utf-8").strip()
        if not token:
            raise RuntimeError("Home Assistant token file is empty")
        return token


@dataclass(frozen=True)
class LocationSettings:
    database_path: Path
    entity_ids: tuple[str, ...]
    interval_seconds: int
    retention_hours: int

    @classmethod
    def from_env(cls) -> "LocationSettings":
        load_env()
        entity_ids = tuple(
            dict.fromkeys(
                entity.strip()
                for entity in os.environ.get("HOME_ASSISTANT_LOCATION_ENTITIES", "").split(",")
                if entity.strip()
            )
        )
        for entity_id in entity_ids:
            domain = entity_id.partition(".")[0]
            if domain not in {"person", "device_tracker"}:
                raise RuntimeError(
                    "HOME_ASSISTANT_LOCATION_ENTITIES must contain only person.* "
                    "or device_tracker.* entities"
                )

        return cls(
            database_path=env_path(
                "HOME_ASSISTANT_LOCATION_DB",
                DEFAULT_DATA_DIR / "locations.db",
            ),
            entity_ids=entity_ids,
            interval_seconds=env_int(
                "HOME_ASSISTANT_LOCATION_INTERVAL_SECONDS",
                600,
                minimum=60,
                maximum=86400,
            ),
            retention_hours=env_int(
                "HOME_ASSISTANT_LOCATION_RETENTION_HOURS",
                72,
                minimum=1,
                maximum=720,
            ),
        )
