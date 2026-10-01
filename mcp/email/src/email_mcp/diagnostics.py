"""Human-readable validation for the private email account configuration."""

from .composition import EmailContainer


def main() -> None:
    accounts = EmailContainer().service.list_accounts()
    print(f"Email configuration is valid: {len(accounts)} account(s)")
    for account in accounts:
        default_marker = " (default)" if account["is_default"] else ""
        send_policy = "send enabled" if account["sending_enabled"] else "send disabled"
        print(
            f"- {account['account_id']}: {account['provider']}, "
            f"{account['label']}{default_marker}, {send_policy}"
        )


if __name__ == "__main__":
    main()
