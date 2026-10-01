"""Ports used by calendar application services."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Protocol

from ..models import CalendarInfo, EventRecord

if TYPE_CHECKING:
    from ..config import CalendarAccountSettings, Settings


class CalendarClient(Protocol):
    def list_calendars(self) -> list[CalendarInfo]: ...

    def search_events(
        self,
        start: datetime,
        end: datetime,
        *,
        calendar_id: str = "",
        query: str = "",
        include_notes: bool = False,
        limit: int,
    ) -> tuple[list[EventRecord], bool]: ...

    def create_event(
        self,
        payload: dict[str, object],
        *,
        uid: str,
    ) -> tuple[str, bool]: ...

    def delete_event(self, calendar_id: str, provider_event_id: str) -> bool: ...

    def require_calendar(self, calendar_id: str) -> CalendarInfo: ...


class CalendarClientFactory(Protocol):
    def build(
        self,
        settings: "Settings",
        account: "CalendarAccountSettings",
    ) -> CalendarClient: ...


class ProposalRecord(Protocol):
    proposal_id: str
    action: str
    uid: str
    target_ref: str
    account_id: str
    calendar_id: str
    payload: dict[str, object]
    expires_at: int
    receipt: dict[str, object] | None


class ProposalRepository(Protocol):
    def create(
        self,
        *,
        account_id: str,
        calendar_id: str,
        uid: str,
        payload: dict[str, object],
        ttl_seconds: int,
        action: str = "create",
        target_ref: str = "",
    ) -> ProposalRecord: ...

    def get(self, proposal_id: str) -> ProposalRecord | None: ...

    def mark_committed(
        self,
        proposal_id: str,
        *,
        account_id: str,
        calendar_id: str,
        uid: str,
        receipt: dict[str, object],
        result: str,
        action: str = "create",
    ) -> None: ...

    def record_failure(
        self,
        *,
        account_id: str,
        calendar_id: str,
        uid: str,
        result: str,
        action: str = "create",
    ) -> None: ...

    def is_private(self) -> bool: ...


class ConfirmationResult(Enum):
    ACCEPTED = "accepted"
    DECLINED = "declined"
    UNAVAILABLE = "unavailable"


class ConfirmationGateway(Protocol):
    async def confirm(self, proposal: ProposalRecord) -> ConfirmationResult: ...
