#!/usr/bin/env python3
"""Install configured background processes as systemd user services."""

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIT_DIR = Path.home() / ".config" / "systemd" / "user"

SERVICES = {
    "personal-assistant-telegram-listener": ("telegram", "telegram-listener"),
    "personal-assistant-telegram-worker": ("telegram", "telegram-worker"),
    "personal-assistant-telegram-notifier": ("telegram", "telegram-notifier"),
}
LOCATION_SERVICE = "personal-assistant-homeassistant-location-recorder"


def unit(command: str, service: str = "telegram") -> str:
    executable = ROOT / "mcp" / service / ".venv" / "bin" / command
    env_file = ROOT / "mcp" / service / ".env"
    if not executable.is_file():
        raise SystemExit(f"Missing {executable}; run make setup first")
    return f"""[Unit]
Description=Personal AI Assistant: {command}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={ROOT / "mcp" / service}
Environment={json.dumps(f"MCP_ENV_FILE={env_file}", ensure_ascii=False)}
ExecStart={executable}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


def location_recorder_configured() -> bool:
    env_file = ROOT / "mcp" / "homeassistant" / ".env"
    if not env_file.is_file():
        return False
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "HOME_ASSISTANT_LOCATION_ENTITIES":
            return bool(value.strip().strip('"').strip("'"))
    return False


def main() -> None:
    if not shutil.which("systemctl"):
        raise SystemExit("systemd is not available on this machine")

    services = dict(SERVICES)
    if location_recorder_configured():
        services[LOCATION_SERVICE] = (
            "homeassistant",
            "homeassistant-location-recorder",
        )

    UNIT_DIR.mkdir(parents=True, exist_ok=True)
    for name, (service, command) in services.items():
        path = UNIT_DIR / f"{name}.service"
        path.write_text(unit(command, service), encoding="utf-8")
        print(f"Wrote {path}")

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(
        ["systemctl", "--user", "enable", "--now", *services],
        check=True,
    )


if __name__ == "__main__":
    main()
