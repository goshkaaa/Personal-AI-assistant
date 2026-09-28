#!/usr/bin/env python3
"""Interactively install iCloud credentials without exposing them in argv/history."""

import getpass
import os
import pwd
import re
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
SERVICE_HOME = Path(pwd.getpwuid(os.geteuid()).pw_dir)
SECRET_FILE = SERVICE_HOME / ".config" / "hermes" / "secrets" / "icloud-calendar-password"
EMAIL_RE = re.compile(r"^[^\s=@]+@[^\s=@]+$")


def atomic_write(path: Path, content: str, *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, path)
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def update_env(username: str) -> None:
    updates = {
        "ICLOUD_USERNAME": username,
        "ICLOUD_APP_PASSWORD_FILE": str(SECRET_FILE),
        "CALENDAR_TIMEZONE": "Europe/Moscow",
        "MCP_ALLOW_CALENDAR_WRITE": "false",
        "CALENDAR_PROPOSAL_TTL_SECONDS": "600",
        "CALENDAR_STATE_DB": "data/calendar.sqlite3",
    }
    existing = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    output: list[str] = []
    seen: set[str] = set()
    for line in existing:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            output.append(line)
    if output and output[-1]:
        output.append("")
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={value}")
    atomic_write(ENV_FILE, "\n".join(output).rstrip() + "\n", mode=0o600)


def main() -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        raise SystemExit("Run this helper as the hermes user, not root")

    username = input("Apple Account email: ").strip()
    if not EMAIL_RE.fullmatch(username):
        raise SystemExit("Expected an Apple Account email address")

    password = getpass.getpass("Apple app-specific password (input hidden): ").strip()
    if len(password) < 12:
        raise SystemExit("The app-specific password looks too short")

    atomic_write(SECRET_FILE, password + "\n", mode=0o600)
    update_env(username)
    print("iCloud credentials installed; calendar writes remain disabled.")
    print("Restart the Hermes gateway for your profile, then list calendars.")


if __name__ == "__main__":
    main()
