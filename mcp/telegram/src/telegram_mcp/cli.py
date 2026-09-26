"""Operational commands for Telegram authorization and live diagnostics."""

import argparse

from .client import TelegramSettings, create_client


def login_main() -> None:
    """Authorize the primary userbot session interactively."""
    settings = TelegramSettings.from_env()
    with create_client(settings) as app:
        me = app.get_me()

    print("\nTelegram authorization: OK")
    print(f"User ID: {me.id}")
    print(f"Username: @{me.username}" if me.username else "Username: —")
    print(f"Session: {settings.session_dir / (settings.session_name + '.session')}")


def listener_login_main() -> None:
    """Authorize the dedicated long-running listener session."""
    settings = TelegramSettings.from_env(
        session_variable="TG_LISTENER_SESSION_NAME",
        default_session="hermes_listener",
    )
    with create_client(settings) as app:
        me = app.get_me()

    print("Listener authorization: OK")
    print(f"User ID: {me.id}")
    print(f"Session: {settings.session_dir / (settings.session_name + '.session')}")


def smoke_main() -> None:
    """Check connectivity; sending to Saved Messages is explicit opt-in."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--send",
        action="store_true",
        help="also send a test message to Telegram Saved Messages",
    )
    args = parser.parse_args()

    with create_client() as app:
        me = app.get_me()
        print("Telegram connection: OK")
        print(f"Account ID: {me.id}")

        if args.send:
            message = app.send_message(
                "me",
                "Hermes MCP live check: Telegram delivery works.",
            )
            print(f"Saved Messages delivery: OK (message_id={message.id})")
