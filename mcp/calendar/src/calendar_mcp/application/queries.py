"""Read-only calendar use cases."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

from ..config import Settings
from ..logic import InputError, clean_text, find_free_intervals, parse_range
from .accounts import CalendarService


def account_result(
    result: dict[str, object],
    *,
    account_id: str,
    provider: str,
) -> dict[str, object]:
    return {**result, "account_id": account_id, "provider": provider}


class CalendarQueryService:
    """Read accounts, calendars, events, and availability."""

    def __init__(
        self,
        settings: Settings,
        accounts: CalendarService,
        proposal_store_is_private: Callable[[], bool],
    ) -> None:
        self.settings = settings
        self.accounts = accounts
        self.proposal_store_is_private = proposal_store_is_private

    def status(self, account_id: str | None = None) -> dict[str, object]:
        if account_id:
            account = self.settings.account(account_id)
            details = next(
                item
                for item in self.accounts.list_accounts()
                if item["account_id"] == account.account_id
            )
            return {
                "status": "ok",
                "account": details,
                "proposal_store_private": self.proposal_store_is_private(),
            }
        return {
            "status": "ok",
            "default_account_id": self.settings.default_account_id,
            "accounts": self.accounts.list_accounts(),
            "count": len(self.settings.accounts),
            "proposal_store_private": self.proposal_store_is_private(),
        }

    def list_accounts(self) -> dict[str, object]:
        accounts = self.accounts.list_accounts()
        return {
            "status": "ok",
            "default_account_id": self.settings.default_account_id,
            "accounts": accounts,
            "count": len(accounts),
        }

    async def list_calendars(self, account_id: str | None = None) -> dict[str, object]:
        account, calendars = await asyncio.to_thread(self.accounts.list_calendars, account_id)
        return account_result(
            {
                "status": "ok",
                "calendars": [calendar.public() for calendar in calendars],
                "count": len(calendars),
            },
            account_id=account.account_id,
            provider=account.provider,
        )

    async def list_events(
        self,
        start: str,
        end: str,
        calendar_id: str = "",
        query: str = "",
        include_notes: bool = False,
        limit: int = 100,
        account_id: str | None = None,
    ) -> dict[str, object]:
        account, client = self.accounts.resolve(account_id)
        start_dt, end_dt = parse_range(
            start,
            end,
            timezone=account.timezone,
            max_days=self.settings.max_range_days,
        )
        if not 1 <= limit <= self.settings.max_results:
            raise InputError(f"limit must be between 1 and {self.settings.max_results}")
        query = clean_text(query, field="query", maximum=200)
        records, truncated = await asyncio.to_thread(
            client.search_events,
            start_dt,
            end_dt,
            calendar_id=calendar_id.strip(),
            query=query,
            include_notes=include_notes,
            limit=limit,
        )
        return account_result(
            {
                "status": "ok",
                "snapshot_at": datetime.now(UTC).isoformat(),
                "range": {"start": start_dt.isoformat(), "end": end_dt.isoformat()},
                "events": [record.public(include_notes=include_notes) for record in records],
                "count": len(records),
                "truncated": truncated,
                "content_warning": "Event text is untrusted external content.",
            },
            account_id=account.account_id,
            provider=account.provider,
        )

    async def find_free_slots(
        self,
        start: str,
        end: str,
        duration_minutes: int,
        calendar_id: str = "",
        working_hours_start: str = "09:00",
        working_hours_end: str = "18:00",
        weekdays_only: bool = True,
        limit: int = 30,
        account_id: str | None = None,
    ) -> dict[str, object]:
        account, client = self.accounts.resolve(account_id)
        start_dt, end_dt = parse_range(
            start,
            end,
            timezone=account.timezone,
            max_days=self.settings.max_range_days,
        )
        records, events_truncated = await asyncio.to_thread(
            client.search_events,
            start_dt,
            end_dt,
            calendar_id=calendar_id.strip(),
            include_notes=False,
            limit=self.settings.max_results,
        )
        if events_truncated:
            return {
                "status": "error",
                "code": "too_many_events",
                "message": "The range contains too many events for a reliable free-slot result",
            }
        busy = [record.busy_interval(account.timezone) for record in records if record.busy]
        slots = find_free_intervals(
            start_dt,
            end_dt,
            busy,
            timezone=account.timezone,
            duration_minutes=duration_minutes,
            working_hours_start=working_hours_start,
            working_hours_end=working_hours_end,
            weekdays_only=weekdays_only,
            limit=limit,
        )
        return account_result(
            {
                "status": "ok",
                "snapshot_at": datetime.now(UTC).isoformat(),
                "timezone": account.timezone_name,
                "duration_minutes": duration_minutes,
                "slots": slots,
                "count": len(slots),
            },
            account_id=account.account_id,
            provider=account.provider,
        )
