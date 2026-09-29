"""Google Calendar API adapter."""

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..config import (
    ConfigurationError,
    GoogleAccountSettings,
    Settings,
    read_private_secret,
)
from ..models import CalendarInfo, CalendarServiceError, EventRecord
from ..secrets import write_private

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


class GoogleCalendarService:
    def __init__(
        self,
        settings: Settings,
        account: GoogleAccountSettings,
        service: Any | None = None,
    ) -> None:
        self.settings = settings
        self.account = account
        self._service = service

    @property
    def service(self) -> Any:
        if self._service is None:
            self._service = self._connect()
        return self._service

    def list_calendars(self) -> list[CalendarInfo]:
        return [self._calendar_info(item) for item in self._calendar_entries()]

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
        calendars = self._select_calendars(calendar_id, allow_all=True)
        time_min = start.astimezone(UTC).isoformat().replace("+00:00", "Z")
        time_max = end.astimezone(UTC).isoformat().replace("+00:00", "Z")
        records: list[EventRecord] = []
        truncated = False
        for calendar in calendars:
            info = self._calendar_info(calendar)
            page_token: str | None = None
            while True:
                remaining = limit + 1 - len(records)
                if remaining <= 0:
                    truncated = True
                    break
                request = self.service.events().list(
                    calendarId=calendar["id"],
                    timeMin=time_min,
                    timeMax=time_max,
                    q=query or None,
                    singleEvents=True,
                    orderBy="startTime",
                    showDeleted=False,
                    maxResults=min(remaining, 2500),
                    pageToken=page_token,
                )
                response = self._execute(request, "list events")
                for item in response.get("items", []):
                    if item.get("status") == "cancelled":
                        continue
                    try:
                        records.append(self._event_record(item, info, include_notes=include_notes))
                    except CalendarServiceError as error:
                        if error.code != "invalid_event":
                            raise
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
            if truncated:
                break

        records.sort(key=lambda item: item.busy_interval(self.account.timezone).start)
        return records[:limit], truncated or len(records) > limit

    def create_event(
        self,
        payload: dict[str, object],
        *,
        uid: str,
    ) -> tuple[str, bool]:
        calendar = self._select_calendars(str(payload["calendar_id"]), allow_all=False)[0]
        try:
            self.service.events().get(calendarId=calendar["id"], eventId=uid).execute()
            return uid, True
        except HttpError as error:
            if error.resp.status != 404:
                raise self._calendar_error(error, "check event") from error

        body = self._event_body(payload, uid=uid)
        try:
            result = (
                self.service.events()
                .insert(calendarId=calendar["id"], body=body, sendUpdates="none")
                .execute()
            )
        except HttpError as error:
            if error.resp.status == 409:
                return uid, True
            raise self._calendar_error(error, "create event") from error
        return str(result.get("id") or uid), False

    def require_calendar(self, calendar_id: str) -> CalendarInfo:
        calendar = self._select_calendars(calendar_id, allow_all=False)[0]
        return self._calendar_info(calendar)

    def _connect(self) -> Any:
        token_path = self.account.token_file
        if not token_path.is_file():
            raise ConfigurationError(
                f"Google Calendar token not found for {self.account.account_id!r}; "
                "run calendar-auth"
            )
        try:
            token = json.loads(
                read_private_secret(
                    token_path,
                    label=f"{self.account.label} OAuth token",
                    maximum_bytes=65_536,
                )
            )
            credentials = Credentials.from_authorized_user_info(token, SCOPES)
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                write_private(token_path, credentials.to_json())
        except (json.JSONDecodeError, ValueError, RefreshError) as error:
            raise CalendarServiceError(
                "auth_failed",
                f"Google Calendar authorization is invalid for {self.account.account_id!r}; "
                "run calendar-auth again",
            ) from error
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def _calendar_entries(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            response = self._execute(
                self.service.calendarList().list(pageToken=page_token),
                "list calendars",
            )
            entries.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return entries

    def _select_calendars(self, calendar_id: str, *, allow_all: bool) -> list[dict[str, Any]]:
        calendars = self._calendar_entries()
        if not calendar_id:
            if allow_all:
                return calendars
            raise ConfigurationError(
                f"No write_calendar_id is configured for account {self.account.account_id!r}"
            )
        selected = [item for item in calendars if self._opaque_id(item["id"]) == calendar_id]
        if not selected:
            raise CalendarServiceError(
                "calendar_not_found",
                "The selected calendar no longer exists; list calendars and update its id",
            )
        return selected

    def _calendar_info(self, item: dict[str, Any]) -> CalendarInfo:
        calendar_id = self._opaque_id(item["id"])
        name = " ".join(
            str(item.get("summaryOverride") or item.get("summary") or "")
            .replace("\x00", "")
            .split()
        )
        return CalendarInfo(
            calendar_id=calendar_id,
            name=name[:200] or f"Calendar {calendar_id[:8]}",
            is_write_target=calendar_id == self.account.write_calendar_id,
        )

    def _event_record(
        self,
        item: dict[str, Any],
        calendar: CalendarInfo,
        *,
        include_notes: bool,
    ) -> EventRecord:
        start, all_day = self._event_time(item.get("start", {}), field="start")
        end, end_all_day = self._event_time(item.get("end", {}), field="end")
        if all_day != end_all_day:
            raise CalendarServiceError(
                "invalid_event", "A calendar event has incompatible start and end values"
            )
        recurrence_raw = item.get("originalStartTime")
        recurrence_id = None
        if isinstance(recurrence_raw, dict):
            recurrence_id, _ = self._event_time(recurrence_raw, field="recurrence")
        return EventRecord(
            calendar_id=calendar.calendar_id,
            calendar_name=calendar.name,
            uid=str(item.get("iCalUID") or item.get("id") or ""),
            title=str(item.get("summary") or "(without title)")[:300],
            start=start,
            end=end,
            all_day=all_day,
            location=str(item.get("location") or "")[:300],
            notes=str(item.get("description") or "")[:1000] if include_notes else "",
            status=str(item.get("status") or "confirmed").upper()[:40],
            recurrence_id=recurrence_id,
            busy=item.get("transparency") != "transparent",
            floating_time=False,
        )

    @staticmethod
    def _event_time(value: dict[str, Any], *, field: str) -> tuple[date | datetime, bool]:
        try:
            if value.get("date"):
                return date.fromisoformat(str(value["date"])), True
            raw = str(value.get("dateTime") or "")
            if not raw:
                raise ValueError
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError
            return parsed, False
        except (TypeError, ValueError) as error:
            raise CalendarServiceError(
                "invalid_event", f"A calendar event has an invalid {field}"
            ) from error

    def _event_body(self, payload: dict[str, object], *, uid: str) -> dict[str, object]:
        all_day = bool(payload["all_day"])
        if all_day:
            start = {"date": str(payload["start"])}
            end = {"date": str(payload["end"])}
        else:
            start = {"dateTime": str(payload["start"])}
            end = {"dateTime": str(payload["end"])}
        return {
            "id": uid,
            "summary": str(payload["title"]),
            "start": start,
            "end": end,
            "location": str(payload.get("location") or ""),
            "description": str(payload.get("description") or ""),
            "transparency": "opaque",
        }

    def _opaque_id(self, calendar_id: str) -> str:
        material = f"google\0{self.account.account_id}\0{calendar_id}"
        return hashlib.sha256(material.encode()).hexdigest()[:24]

    @staticmethod
    def _calendar_error(error: HttpError, operation: str) -> CalendarServiceError:
        status = error.resp.status
        if status in {401, 403}:
            return CalendarServiceError("auth_failed", "Google Calendar authorization failed")
        if status == 429:
            return CalendarServiceError("rate_limited", "Google Calendar rate-limited the request")
        return CalendarServiceError("google_api_failed", f"Google Calendar {operation} failed")

    @classmethod
    def _execute(cls, request: Any, operation: str) -> dict[str, Any]:
        try:
            return request.execute()
        except HttpError as error:
            raise cls._calendar_error(error, operation) from error
