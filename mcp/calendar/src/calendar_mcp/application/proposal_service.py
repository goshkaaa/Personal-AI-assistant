"""Safe create/delete proposal preparation use cases."""

import asyncio
import uuid
from datetime import UTC, datetime

from ..config import ConfigurationError, Settings
from ..domain.ports import ProposalRepository
from ..logic import InputError, as_interval, clean_text, normalize_event_times, parse_range
from ..models import CalendarServiceError
from .accounts import CalendarService


class CalendarProposalService:
    """Prepare immutable, short-lived calendar write proposals."""

    def __init__(
        self,
        settings: Settings,
        accounts: CalendarService,
        proposals: ProposalRepository,
    ) -> None:
        self.settings = settings
        self.accounts = accounts
        self.proposals = proposals

    async def prepare_delete_event(
        self,
        event_id: str,
        start: str,
        end: str,
        calendar_id: str = "",
        account_id: str | None = None,
    ) -> dict[str, object]:
        account, client = self.accounts.resolve(account_id)
        self._require_write_calendar(account.account_id, account.write_calendar_id)
        event_id = clean_text(event_id, field="event_id", maximum=128, required=True)
        target_calendar_id = calendar_id.strip() or account.write_calendar_id
        if target_calendar_id != account.write_calendar_id:
            raise InputError("Only the account's configured write calendar can be modified")
        start_dt, end_dt = parse_range(
            start,
            end,
            timezone=account.timezone,
            max_days=self.settings.max_range_days,
        )
        records, truncated = await asyncio.to_thread(
            client.search_events,
            start_dt,
            end_dt,
            calendar_id=target_calendar_id,
            include_notes=False,
            limit=self.settings.max_results,
        )
        matches = [record for record in records if record.event_id == event_id]
        if not matches:
            if truncated:
                raise CalendarServiceError(
                    "too_many_events",
                    "The range contains too many events; use a narrower range",
                )
            return {
                "status": "not_found",
                "message": "The event was not found in the selected account, calendar, and range",
            }
        if len(matches) != 1:
            raise CalendarServiceError("ambiguous_event", "The event id was not unique")

        record = matches[0]
        if record.recurrence_id is not None:
            return {
                "status": "unsupported",
                "code": "recurring_event",
                "message": "Deleting recurring events is not supported safely yet",
            }
        if not record.provider_event_id:
            raise CalendarServiceError(
                "event_reference_missing",
                "The provider did not return a deletable event reference",
            )

        payload: dict[str, object] = {
            "account_id": account.account_id,
            "provider": account.provider,
            "calendar_id": record.calendar_id,
            "calendar_name": record.calendar_name,
            "event_id": record.event_id,
            "title": record.title,
            "start": record.start.isoformat(),
            "end": record.end.isoformat(),
            "all_day": record.all_day,
        }
        proposal = self.proposals.create(
            action="delete",
            account_id=account.account_id,
            calendar_id=record.calendar_id,
            uid=uuid.uuid4().hex,
            target_ref=record.provider_event_id,
            payload=payload,
            ttl_seconds=self.settings.proposal_ttl_seconds,
        )
        return {
            "status": "prepared",
            "action": "delete",
            "proposal_id": proposal.proposal_id,
            "expires_at": datetime.fromtimestamp(proposal.expires_at, UTC).isoformat(),
            "event": payload,
            "write_enabled": account.write_enabled,
            "next_step": (
                "Call calendar_commit_delete_event with this proposal_id only after the user "
                "explicitly asks to delete this exact event. Interactive approval is required."
            ),
        }

    async def prepare_event(
        self,
        title: str,
        start: str,
        end: str,
        all_day: bool = False,
        location: str = "",
        description: str = "",
        account_id: str | None = None,
    ) -> dict[str, object]:
        account, client = self.accounts.resolve(account_id)
        self._require_write_calendar(account.account_id, account.write_calendar_id)
        title = clean_text(title, field="title", maximum=200, required=True)
        location = clean_text(location, field="location", maximum=300)
        description = clean_text(description, field="description", maximum=2000)
        times = normalize_event_times(start, end, all_day=all_day)
        target = await asyncio.to_thread(client.require_calendar, account.write_calendar_id)
        interval = as_interval(times.start, times.end, timezone=account.timezone)
        records, truncated = await asyncio.to_thread(
            client.search_events,
            interval.start,
            interval.end,
            calendar_id=target.calendar_id,
            include_notes=False,
            limit=self.settings.max_results,
        )
        if truncated:
            raise CalendarServiceError(
                "too_many_events",
                "Too many overlapping events to prepare a safe proposal",
            )
        conflicts = []
        for record in records:
            if not record.busy:
                continue
            busy = record.busy_interval(account.timezone)
            if busy.start < interval.end and busy.end > interval.start:
                conflicts.append(
                    {
                        "start": busy.start.astimezone(account.timezone).isoformat(),
                        "end": busy.end.astimezone(account.timezone).isoformat(),
                        "all_day": record.all_day,
                    }
                )

        payload: dict[str, object] = {
            "account_id": account.account_id,
            "provider": account.provider,
            "calendar_id": target.calendar_id,
            "calendar_name": target.name,
            "title": title,
            **times.as_payload(),
            "timezone": account.timezone_name,
            "location": location,
            "description": description,
            "conflict_count": len(conflicts),
            "conflicts": conflicts[:20],
        }
        proposal = self.proposals.create(
            account_id=account.account_id,
            calendar_id=target.calendar_id,
            uid=uuid.uuid4().hex,
            payload=payload,
            ttl_seconds=self.settings.proposal_ttl_seconds,
        )
        return {
            "status": "prepared",
            "proposal_id": proposal.proposal_id,
            "expires_at": datetime.fromtimestamp(proposal.expires_at, UTC).isoformat(),
            "event": payload,
            "write_enabled": account.write_enabled,
            "next_step": (
                "Call calendar_commit_event with this proposal_id only after the user explicitly "
                "asks to create this exact event. Interactive approval is still required."
            ),
        }

    @staticmethod
    def _require_write_calendar(account_id: str, calendar_id: str) -> None:
        if not calendar_id:
            raise ConfigurationError(
                f"write_calendar_id is not configured for account {account_id!r}; "
                "list calendars and choose one"
            )
