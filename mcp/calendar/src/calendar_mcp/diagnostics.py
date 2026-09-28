"""Human-readable validation for the private calendar account configuration."""

from .service import CalendarService


def main() -> None:
    service = CalendarService.from_env()
    accounts = service.list_accounts()
    print(f"Calendar configuration is valid: {len(accounts)} account(s)")
    for account in accounts:
        default_marker = " (default)" if account["is_default"] else ""
        write_policy = "write enabled" if account["write_enabled"] else "write disabled"
        print(
            f"- {account['account_id']}: {account['provider']}, "
            f"{account['label']}{default_marker}, {write_policy}"
        )


if __name__ == "__main__":
    main()
