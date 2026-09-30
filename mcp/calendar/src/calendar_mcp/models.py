"""Provider-neutral calendar domain models."""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .logic import BusyInterval, as_interval


class CalendarServiceError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CalendarInfo:
    calendar_id: str
    name: str
    is_write_target: bool

    def public(self) -> dict[str, object]:
        return {
            "calendar_id": self.calendar_id,
            "name": self.name,
            "is_write_target": self.is_write_target,
        }


@dataclass(frozen=True)
class EventRecord:
    calendar_id: str
    calendar_name: str
    uid: str
    title: str
    start: date | datetime
    end: date | datetime
    all_day: bool
    location: str
    notes: str
    status: str
    recurrence_id: date | datetime | None
    busy: bool
    floating_time: bool
    provider_event_id: str = ""

    @property
    def event_id(self) -> str:
        occurrence = self.recurrence_id.isoformat() if self.recurrence_id else ""
        provider_reference = self.provider_event_id or self.uid
        return hashlib.sha256(
            f"{self.calendar_id}\0{provider_reference}\0{occurrence}".encode()
        ).hexdigest()[:24]

    def busy_interval(self, timezone: ZoneInfo) -> BusyInterval:
        return as_interval(self.start, self.end, timezone=timezone)

    def public(self, *, include_notes: bool) -> dict[str, object]:
        occurrence = self.recurrence_id.isoformat() if self.recurrence_id else ""
        result: dict[str, object] = {
            "event_id": self.event_id,
            "calendar_id": self.calendar_id,
            "calendar_name": self.calendar_name,
            "uid": self.uid,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "all_day": self.all_day,
            "location": self.location,
            "status": self.status,
            "busy": self.busy,
            "recurrence_id": occurrence or None,
            "floating_time": self.floating_time,
            "untrusted_external_content": True,
        }
        if include_notes:
            result["notes"] = self.notes
        return result
