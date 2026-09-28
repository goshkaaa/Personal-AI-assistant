"""Interactive Gmail OAuth setup."""

import argparse
import os

from google_auth_oauthlib.flow import InstalledAppFlow

from .config import EmailSettings, GmailAccountSettings, private_path
from .providers.gmail import SCOPES


def main() -> None:
    parser = argparse.ArgumentParser(description="Authorize a configured Gmail account")
    parser.add_argument("--account", help="Account ID from EMAIL_ACCOUNTS_FILE")
    arguments = parser.parse_args()

    account = EmailSettings.from_env().account(arguments.account)
    if not isinstance(account, GmailAccountSettings):
        raise RuntimeError(f"Account {account.account_id!r} does not use Gmail OAuth")

    credentials_file = private_path(account.credentials_file)
    token_file = private_path(account.token_file)

    if not credentials_file.is_file():
        raise RuntimeError(f"Gmail OAuth credentials not found: {credentials_file}")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_file),
        scopes=SCOPES,
    )
    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=8766,
        open_browser=False,
        authorization_prompt_message="\nOpen this URL in a browser:\n{url}\n",
        success_message="Gmail connected. You can close this window.",
    )

    descriptor = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(credentials.to_json())
    token_file.chmod(0o600)
    print(f"Gmail account {account.account_id!r} authorized; token saved to {token_file}")


if __name__ == "__main__":
    main()
