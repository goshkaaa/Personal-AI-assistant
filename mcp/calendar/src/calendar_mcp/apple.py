"""Bounded, typed access to Apple iCloud Calendar over CalDAV."""

import hashlib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Iterator

from caldav import error as caldav_error
from caldav import get_davclient
from icalendar import Calendar as ICalendar
from icalendar import Event as IEvent
from niquests import Session
from niquests.exceptions import ConnectionError as NiquestsConnectionError

from .config import ConfigurationError, Settings
from .logic import BusyInterval, as_interval

ICLOUD_CALDAV_URL = "https://caldav.icloud.com/"


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

    def busy_interval(self, settings: Settings) -> BusyInterval:
        return as_interval(self.start, self.end, timezone=settings.timezone)

    def public(self, *, include_notes: bool) -> dict[str, object]:
        occurrence = self.recurrence_id.isoformat() if self.recurrence_id else ""
        event_key = hashlib.sha256(
            f"{self.calendar_id}\0{self.uid}\0{occurrence}".encode()
        ).hexdigest()[:24]
        result: dict[str, object] = {
            "event_id": event_key,
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


class AppleCalendarService:
    def __init__(self, settings: Settings):
        self.settings = settings

    @contextmanager
    def _principal(self) -> Iterator[object]:
        if not self.settings.username:
            raise ConfigurationError("ICLOUD_USERNAME is not configured")
        password = self.settings.read_app_password()
        try:
            client = get_davclient(
                url=ICLOUD_CALDAV_URL,
                username=self.settings.username,
                password=password,
                timeout=self.settings.timeout_seconds,
                ssl_verify_cert=True,
                require_tls=True,
            )
            if client is None:  # pragma: no cover - explicit arguments always build a client
                raise CalendarServiceError("client_failed", "Failed to create CalDAV client")

            # niquests may upgrade iCloud to HTTP/3 over IPv6. On some VPS networks the QUIC
            # datagram exceeds the path MTU and Linux raises EMSGSIZE before authentication.
            # Apple CalDAV works normally over HTTP/1.1 or HTTP/2, so fail away from QUIC while
            # keeping IPv6 and TLS certificate verification enabled.
            client.session.close()
            client.session = Session(disable_http3=True)

            with client:
                yield client.get_principal()
        except ConfigurationError:
            raise
        except CalendarServiceError:
            raise
        except caldav_error.AuthorizationError as exc:
            raise CalendarServiceError(
                "auth_failed",
                "Apple Calendar authentication failed; check the Apple Account email and "
                "app-specific password",
            ) from exc
        except caldav_error.RateLimitError as exc:
            raise CalendarServiceError(
                "rate_limited", "Apple Calendar temporarily rate-limited the request"
            ) from exc
        except NiquestsConnectionError as exc:
            raise CalendarServiceError(
                "transport_failed",
                "Apple Calendar network transport failed before an authentication response; "
                "do not replace credentials based on this error",
            ) from exc
        except Exception as exc:
            # Raw CalDAV errors may contain account URLs or event bodies. Keep them out of MCP.
            raise CalendarServiceError(
                "caldav_failed",
                f"Apple Calendar request failed ({type(exc).__name__})",
            ) from exc

    def list_calendars(self) -> list[CalendarInfo]:
        with self._principal() as principal:
            calendars = principal.get_calendars()
            return [self._calendar_info(calendar) for calendar in calendars]

    def search_events(
        self,
        start: datetime,
        end: datetime,
        *,
        calendar_id: str = "",
        query: str = "",
        include_notes: bool = False,
        limit: int,
    ) -> tuple[list[EventRecord], bool]:
        query_folded = query.casefold().strip()
        records: list[EventRecord] = []
        truncated = False

        with self._principal() as principal:
            calendars = principal.get_calendars()
            selected = self._select(calendars, calendar_id, allow_all=True)
            for calendar in selected:
                info = self._calendar_info(calendar)
                calendar_records: list[EventRecord] = []
                resources = calendar.search(
                    event=True,
                    start=start,
                    end=end,
                    expand=True,
                    sort_keys=["dtstart"],
                )
                for resource in resources:
                    try:
                        record = self._event_record(
                            resource,
                            info,
                            include_notes=include_notes or bool(query_folded),
                        )
                    except CalendarServiceError as exc:
                        if exc.code == "invalid_event":
                            continue
                        raise
                    if (
                        query_folded
                        and query_folded
                        not in "\n".join((record.title, record.location, record.notes)).casefold()
                    ):
                        continue
                    calendar_records.append(record)
                    if len(calendar_records) > limit:
                        truncated = True
                        break
                records.extend(calendar_records)

        records.sort(key=lambda item: item.busy_interval(self.settings).start)
        return records[:limit], truncated or len(records) > limit

    def create_event(
        self,
        payload: dict[str, object],
        *,
        uid: str,
    ) -> tuple[str, bool]:
        """Create once; return (uid, recovered_existing)."""
        calendar_id = str(payload["calendar_id"])
        with self._principal() as principal:
            calendars = principal.get_calendars()
            calendar = self._select(calendars, calendar_id, allow_all=False)[0]

            if self._event_exists(calendar, uid):
                return uid, True

            ical = self._build_ical(payload, uid=uid)
            try:
                calendar.add_event(ical=ical, no_overwrite=True)
            except caldav_error.PutError:
                # A previous attempt may have reached iCloud before its response was lost.
                if self._event_exists(calendar, uid):
                    return uid, True
                raise
            return uid, False

    def require_calendar(self, calendar_id: str) -> CalendarInfo:
        with self._principal() as principal:
            calendars = principal.get_calendars()
            calendar = self._select(calendars, calendar_id, allow_all=False)[0]
            return self._calendar_info(calendar)

    def _select(self, calendars: list, calendar_id: str, *, allow_all: bool) -> list:
        if not calendar_id:
            if allow_all:
                return calendars
            raise ConfigurationError("CALENDAR_WRITE_CALENDAR_ID is not configured")
        selected = [
            calendar for calendar in calendars if self._calendar_id(calendar) == calendar_id
        ]
        if not selected:
            raise CalendarServiceError(
                "calendar_not_found",
                "The selected calendar no longer exists; list calendars and update its id",
            )
        return selected

    def _calendar_info(self, calendar) -> CalendarInfo:
        calendar_id = self._calendar_id(calendar)
        try:
            name = str(calendar.get_display_name() or "").strip()
        except Exception:
            name = ""
        if not name:
            name = f"Calendar {calendar_id[:8]}"
        name = " ".join(name.replace("\x00", "").split())[:200]
        return CalendarInfo(
            calendar_id=calendar_id,
            name=name or "Calendar",
            is_write_target=calendar_id == self.settings.write_calendar_id,
        )

    @staticmethod
    def _calendar_id(calendar) -> str:
        canonical_url = str(calendar.url).rstrip("/") + "/"
        return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:24]

    def _event_record(
        self,
        resource,
        calendar: CalendarInfo,
        *,
        include_notes: bool,
    ) -> EventRecord:
        component = resource.get_icalendar_component()
        start = self._date_value(component, "DTSTART")
        if start is None:
            raise CalendarServiceError("invalid_event", "An Apple Calendar event has no start")
        end = self._date_value(component, "DTEND")
        if end is None:
            duration = self._date_value(component, "DURATION")
            if isinstance(duration, timedelta):
                end = start + duration
            elif isinstance(start, datetime):
                end = start
            else:
                end = start + timedelta(days=1)

        all_day = isinstance(start, date) and not isinstance(start, datetime)
        if all_day != (isinstance(end, date) and not isinstance(end, datetime)):
            raise CalendarServiceError(
                "invalid_event", "An Apple Calendar event has incompatible start and end values"
            )

        status = self._text_value(component, "STATUS", 40).upper() or "CONFIRMED"
        transparent = self._text_value(component, "TRANSP", 40).upper() == "TRANSPARENT"
        recurrence_id = self._date_value(component, "RECURRENCE-ID")
        uid = self._text_value(component, "UID", 512)
        if not uid:
            uid = hashlib.sha256(str(resource.url).encode("utf-8")).hexdigest()

        return EventRecord(
            calendar_id=calendar.calendar_id,
            calendar_name=calendar.name,
            uid=uid,
            title=self._text_value(component, "SUMMARY", 300) or "(без названия)",
            start=start,
            end=end,
            all_day=all_day,
            location=self._text_value(component, "LOCATION", 300),
            notes=self._text_value(component, "DESCRIPTION", 1000) if include_notes else "",
            status=status,
            recurrence_id=recurrence_id,
            busy=status != "CANCELLED" and not transparent,
            floating_time=(
                isinstance(start, datetime) and (start.tzinfo is None or start.utcoffset() is None)
            ),
        )

    @staticmethod
    def _date_value(component, name: str):
        value = component.get(name)
        if value is None:
            return None
        return getattr(value, "dt", value)

    @staticmethod
    def _text_value(component, name: str, maximum: int) -> str:
        value = component.get(name)
        if value is None:
            return ""
        text = str(value).replace("\x00", "").strip()
        return text[:maximum]

    @staticmethod
    def _event_exists(calendar, uid: str) -> bool:
        try:
            return calendar.get_event_by_uid(uid) is not None
        except caldav_error.NotFoundError:
            return False
        except caldav_error.DAVError:
            matches = calendar.search(event=True, uid=uid)
            return bool(matches)

    @staticmethod
    def _build_ical(payload: dict[str, object], *, uid: str) -> ICalendar:
        all_day = bool(payload["all_day"])
        if all_day:
            start: date | datetime = date.fromisoformat(str(payload["start"]))
            end: date | datetime = date.fromisoformat(str(payload["end"]))
        else:
            # ISO inputs carry fixed UTC offsets, not reusable IANA timezone ids. Persisting
            # those offsets as TZID values loses timezone information in some iCalendar parsers,
            # so store the exact instants as RFC-compliant UTC values.
            start = datetime.fromisoformat(str(payload["start"])).astimezone(UTC)
            end = datetime.fromisoformat(str(payload["end"])).astimezone(UTC)

        calendar = ICalendar()
        calendar.add("prodid", "-//Hermes Apple Calendar MCP//EN")
        calendar.add("version", "2.0")
        event = IEvent()
        event.add("uid", uid)
        event.add("dtstamp", datetime.now(UTC))
        event.add("dtstart", start)
        event.add("dtend", end)
        event.add("summary", str(payload["title"]))
        event.add("status", "CONFIRMED")
        event.add("transp", "OPAQUE")
        location = str(payload.get("location", ""))
        description = str(payload.get("description", ""))
        if location:
            event.add("location", location)
        if description:
            event.add("description", description)
        calendar.add_component(event)
        return calendar
