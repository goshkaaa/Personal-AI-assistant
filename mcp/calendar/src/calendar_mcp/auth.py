"""Interactive Google Calendar OAuth setup."""

import argparse
import json

from google_auth_oauthlib.flow import InstalledAppFlow

from .config import GoogleAccountSettings, get_settings, read_private_secret
from .providers.google import SCOPES
from .secrets import write_private


def main() -> None:
    parser = argparse.ArgumentParser(description="Authorize a configured Google Calendar account")
    parser.add_argument("--account", help="Account ID from CALENDAR_ACCOUNTS_FILE")
    arguments = parser.parse_args()

    account = get_settings().account(arguments.account)
    if not isinstance(account, GoogleAccountSettings):
        raise RuntimeError(f"Account {account.account_id!r} does not use Google OAuth")
    if not account.credentials_file.is_file():
        raise RuntimeError(f"Google OAuth credentials not found: {account.credentials_file}")

    client_config = json.loads(
        read_private_secret(
            account.credentials_file,
            label=f"{account.label} OAuth client",
            maximum_bytes=65_536,
        )
    )
    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=SCOPES,
    )
    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=8767,
        open_browser=False,
        authorization_prompt_message="\nOpen this URL in a browser:\n{url}\n",
        success_message="Google Calendar connected. You can close this window.",
    )
    write_private(account.token_file, credentials.to_json())
    print(f"Google Calendar account {account.account_id!r} authorized")


if __name__ == "__main__":
    main()
