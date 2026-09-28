"""Configuration for one or more email accounts."""

import json
import os
import re
import sys
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeAlias

from .providers.presets import IMAP_SMTP_PRESETS

BASE_DIR = Path(sys.prefix).resolve().parent
ENV_FILE = Path(os.environ.get("MCP_ENV_FILE", BASE_DIR / ".env")).expanduser().resolve()
PRIVATE_DIR = Path.home() / ".config" / "personal-ai-assistant" / "secrets"
ACCOUNT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


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
class GmailAccountSettings:
    account_id: str
    label: str
    address: str
    credentials_file: Path
    token_file: Path
    allow_send: bool = False
    provider: Literal["gmail"] = field(default="gmail", init=False)


@dataclass(frozen=True)
class ImapSmtpAccountSettings:
    account_id: str
    label: str
    address: str
    username: str
    password_file: Path
    imap_host: str
    smtp_host: str
    provider: Literal["imap_smtp", "yandex", "mailru", "icloud"] = "imap_smtp"
    imap_port: int = 993
    smtp_port: int = 465
    imap_security: Literal["ssl", "starttls"] = "ssl"
    smtp_security: Literal["ssl", "starttls"] = "ssl"
    inbox_mailbox: str = "INBOX"
    drafts_mailbox: str = "Drafts"
    sent_mailbox: str | None = None
    allow_send: bool = False


EmailAccountSettings: TypeAlias = GmailAccountSettings | ImapSmtpAccountSettings


@dataclass(frozen=True)
class EmailSettings:
    accounts: tuple[EmailAccountSettings, ...]
    default_account_id: str

    @classmethod
    def from_env(cls) -> "EmailSettings":
        load_env()
        accounts_file = env_path("EMAIL_ACCOUNTS_FILE", PRIVATE_DIR / "email-accounts.json")
        if accounts_file.is_file():
            return cls.from_file(accounts_file)
        if "EMAIL_ACCOUNTS_FILE" in os.environ:
            raise RuntimeError(f"Email accounts file not found: {accounts_file}")
        return cls._legacy_gmail_settings()

    @classmethod
    def from_file(cls, path: Path) -> "EmailSettings":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Cannot read email accounts file {path}: {error}") from error

        if not isinstance(raw, dict) or not isinstance(raw.get("accounts"), list):
            raise ValueError("Email accounts file must contain an 'accounts' array")
        accounts = tuple(cls._parse_account(item, path.parent) for item in raw["accounts"])
        if not accounts:
            raise ValueError("At least one email account must be configured")

        account_ids = [account.account_id for account in accounts]
        if len(account_ids) != len(set(account_ids)):
            raise ValueError("Email account IDs must be unique")

        default_account_id = raw.get("default_account") or account_ids[0]
        if default_account_id not in account_ids:
            raise ValueError(f"Unknown default email account: {default_account_id!r}")
        return cls(accounts=accounts, default_account_id=default_account_id)

    def account(self, account_id: str | None = None) -> EmailAccountSettings:
        selected_id = account_id or self.default_account_id
        for account in self.accounts:
            if account.account_id == selected_id:
                return account
        available = ", ".join(account.account_id for account in self.accounts)
        raise ValueError(f"Unknown email account {selected_id!r}. Available accounts: {available}")

    @classmethod
    def _legacy_gmail_settings(cls) -> "EmailSettings":
        account = GmailAccountSettings(
            account_id="default",
            label="Gmail",
            address="",
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
        return cls(accounts=(account,), default_account_id=account.account_id)

    @classmethod
    def _parse_account(cls, raw: Any, base_dir: Path) -> EmailAccountSettings:
        if not isinstance(raw, dict):
            raise ValueError("Each email account must be an object")

        account_id = cls._required_string(raw, "id")
        if not ACCOUNT_ID_PATTERN.fullmatch(account_id):
            raise ValueError(
                f"Invalid email account ID {account_id!r}; use lowercase letters, digits, _ or -"
            )
        provider = cls._required_string(raw, "provider")
        label = cls._optional_string(raw, "label") or account_id
        address = cls._optional_string(raw, "address") or ""
        allow_send = cls._bool(raw, "allow_send", default=False)

        if provider == "gmail":
            return GmailAccountSettings(
                account_id=account_id,
                label=label,
                address=address,
                credentials_file=cls._path(
                    raw,
                    "credentials_file",
                    base_dir,
                    PRIVATE_DIR / "gmail-credentials.json",
                ),
                token_file=cls._path(
                    raw,
                    "token_file",
                    base_dir,
                    PRIVATE_DIR / f"gmail-{account_id}-token.json",
                ),
                allow_send=allow_send,
            )

        if provider == "imap_smtp" or provider in IMAP_SMTP_PRESETS:
            preset = IMAP_SMTP_PRESETS.get(provider)
            imap = cls._optional_mapping(raw, "imap")
            smtp = cls._optional_mapping(raw, "smtp")
            username = cls._optional_string(raw, "username") or address
            if not address or not username:
                raise ValueError(f"IMAP/SMTP account {account_id!r} needs address and username")
            return ImapSmtpAccountSettings(
                account_id=account_id,
                label=label,
                address=address,
                username=username,
                password_file=cls._path(raw, "password_file", base_dir),
                imap_host=cls._host(imap, "host", preset.imap_host if preset else None),
                imap_port=cls._port(imap, "port", preset.imap_port if preset else 993),
                imap_security=cls._security(
                    imap,
                    "security",
                    preset.imap_security if preset else "ssl",
                ),
                smtp_host=cls._host(smtp, "host", preset.smtp_host if preset else None),
                smtp_port=cls._port(smtp, "port", preset.smtp_port if preset else 465),
                smtp_security=cls._security(
                    smtp,
                    "security",
                    preset.smtp_security if preset else "ssl",
                ),
                provider=provider,
                inbox_mailbox=cls._optional_string(imap, "inbox") or "INBOX",
                drafts_mailbox=(
                    cls._optional_string(imap, "drafts")
                    or (preset.drafts_mailbox if preset else "Drafts")
                ),
                sent_mailbox=(
                    cls._optional_string(imap, "sent") or (preset.sent_mailbox if preset else None)
                ),
                allow_send=allow_send,
            )

        raise ValueError(f"Unsupported email provider {provider!r} for account {account_id!r}")

    @staticmethod
    def _required_string(raw: dict[str, Any], key: str) -> str:
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Email account field {key!r} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _optional_string(raw: dict[str, Any], key: str) -> str | None:
        value = raw.get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"Email account field {key!r} must be a string")
        return value.strip() or None

    @staticmethod
    def _optional_mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
        value = raw.get(key, {})
        if not isinstance(value, dict):
            raise ValueError(f"Email account field {key!r} must be an object")
        return value

    @staticmethod
    def _host(raw: dict[str, Any], key: str, default: str | None) -> str:
        value = raw.get(key, default)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Email account field {key!r} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _bool(raw: dict[str, Any], key: str, *, default: bool) -> bool:
        value = raw.get(key, default)
        if not isinstance(value, bool):
            raise ValueError(f"Email account field {key!r} must be a boolean")
        return value

    @staticmethod
    def _port(raw: dict[str, Any], key: str, default: int) -> int:
        value = raw.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
            raise ValueError(f"Email account field {key!r} must be a valid TCP port")
        return value

    @staticmethod
    def _security(
        raw: dict[str, Any],
        key: str,
        default: Literal["ssl", "starttls"],
    ) -> Literal["ssl", "starttls"]:
        value = raw.get(key, default)
        if value not in {"ssl", "starttls"}:
            raise ValueError(f"Email account field {key!r} must be 'ssl' or 'starttls'")
        return value

    @staticmethod
    def _path(
        raw: dict[str, Any],
        key: str,
        base_dir: Path,
        default: Path | None = None,
    ) -> Path:
        value = raw.get(key)
        if value is None and default is None:
            raise ValueError(f"Email account field {key!r} is required")
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Email account field {key!r} must be a path string")
        selected = Path(value).expanduser() if value else default
        if selected is None:  # Kept explicit for static type checkers.
            raise ValueError(f"Email account field {key!r} is required")
        if not selected.is_absolute():
            selected = base_dir / selected
        return selected.resolve()


load_env()
