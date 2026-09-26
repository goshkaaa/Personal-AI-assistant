"""Interactive Gmail OAuth setup."""

import os

from google_auth_oauthlib.flow import InstalledAppFlow

from .client import SCOPES
from .config import GmailSettings, private_path


def main() -> None:
    settings = GmailSettings.from_env()
    credentials_file = private_path(settings.credentials_file)
    token_file = private_path(settings.token_file)

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
    print(f"Gmail token saved to {token_file}")


if __name__ == "__main__":
    main()
