#!/usr/bin/env python3
"""Install the Telegram background processes as systemd user services."""

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIT_DIR = Path.home() / ".config" / "systemd" / "user"

SERVICES = {
    "personal-assistant-telegram-listener": "telegram-listener",
    "personal-assistant-telegram-worker": "telegram-worker",
    "personal-assistant-telegram-notifier": "telegram-notifier",
}


def unit(command: str) -> str:
    executable = ROOT / "mcp" / "telegram" / ".venv" / "bin" / command
    env_file = ROOT / "mcp" / "telegram" / ".env"
    if not executable.is_file():
        raise SystemExit(f"Missing {executable}; run make setup first")
    return f"""[Unit]
Description=Personal AI Assistant: {command}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={ROOT / "mcp" / "telegram"}
Environment={json.dumps(f"MCP_ENV_FILE={env_file}", ensure_ascii=False)}
ExecStart={executable}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


def main() -> None:
    if not shutil.which("systemctl"):
        raise SystemExit("systemd is not available on this machine")

    UNIT_DIR.mkdir(parents=True, exist_ok=True)
    for name, command in SERVICES.items():
        path = UNIT_DIR / f"{name}.service"
        path.write_text(unit(command), encoding="utf-8")
        print(f"Wrote {path}")

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(
        ["systemctl", "--user", "enable", "--now", *SERVICES],
        check=True,
    )


if __name__ == "__main__":
    main()
