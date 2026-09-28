"""Securely store an app password for a configured IMAP/SMTP account."""

import argparse
import getpass
import os

from .config import EmailSettings, ImapSmtpAccountSettings, private_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Store an email app password with mode 0600")
    parser.add_argument("--account", required=True, help="IMAP/SMTP account ID")
    arguments = parser.parse_args()

    account = EmailSettings.from_env().account(arguments.account)
    if not isinstance(account, ImapSmtpAccountSettings):
        raise RuntimeError(f"Account {account.account_id!r} does not use an app-password file")

    password = getpass.getpass(f"App password for {account.label}: ").strip()
    if not password:
        raise ValueError("App password cannot be empty")
    confirmation = getpass.getpass("Repeat app password: ").strip()
    if password != confirmation:
        raise ValueError("App passwords do not match")

    password_file = private_path(account.password_file)
    temporary = password_file.with_suffix(f"{password_file.suffix}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(password)
            output.write("\n")
        temporary.replace(password_file)
        password_file.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(f"App password for {account.account_id!r} saved to {password_file}")


if __name__ == "__main__":
    main()
