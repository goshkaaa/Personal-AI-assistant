"""Securely store a CalDAV app password for a configured account."""

import argparse
import getpass

from .config import CalDavAccountSettings, get_settings
from .secrets import write_private


def main() -> None:
    parser = argparse.ArgumentParser(description="Store a CalDAV app password with mode 0600")
    parser.add_argument("--account", required=True, help="CalDAV account ID")
    arguments = parser.parse_args()

    account = get_settings().account(arguments.account)
    if not isinstance(account, CalDavAccountSettings):
        raise RuntimeError(f"Account {account.account_id!r} does not use a password file")
    password = getpass.getpass(f"App password for {account.label}: ").strip()
    if not password:
        raise ValueError("App password cannot be empty")
    confirmation = getpass.getpass("Repeat app password: ").strip()
    if password != confirmation:
        raise ValueError("App passwords do not match")
    write_private(account.password_file, password + "\n")
    print(f"App password for {account.account_id!r} saved to {account.password_file}")


if __name__ == "__main__":
    main()
