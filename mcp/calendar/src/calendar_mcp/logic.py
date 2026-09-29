"""Pure date/time validation and free-slot calculations."""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class InputError(ValueError):
    """Invalid calendar input that is safe to show to the caller."""


@dataclass(frozen=True)
class NormalizedTimes:
    start: date | datetime
    end: date | datetime
    all_day: bool

    def as_payload(self) -> dict[str, object]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "all_day": self.all_day,
        }


@dataclass(frozen=True)
class BusyInterval:
    start: datetime
    end: datetime


def clean_text(value: str, *, field: str, maximum: int, required: bool = False) -> str:
    text = str(value).replace("\x00", "").strip()
    if required and not text:
        raise InputError(f"{field} cannot be empty")
    if len(text) > maximum:
        raise InputError(f"{field} is longer than {maximum} characters")
    return text


def parse_datetime(value: str, *, field: str) -> datetime:
    raw = str(value).strip()
    if not raw or DATE_RE.fullmatch(raw):
        raise InputError(f"{field} must be an ISO 8601 date-time with an explicit offset")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError(f"{field} is not a valid ISO 8601 date-time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InputError(f"{field} must include a UTC offset, for example +03:00")
    return parsed


def parse_boundary(value: str, *, field: str, timezone: ZoneInfo) -> datetime:
    raw = str(value).strip()
    if DATE_RE.fullmatch(raw):
        return datetime.combine(date.fromisoformat(raw), time.min, tzinfo=timezone)
    return parse_datetime(raw, field=field)


def parse_range(
    start: str,
    end: str,
    *,
    timezone: ZoneInfo,
    max_days: int,
) -> tuple[datetime, datetime]:
    start_dt = parse_boundary(start, field="start", timezone=timezone)
    end_dt = parse_boundary(end, field="end", timezone=timezone)
    if end_dt <= start_dt:
        raise InputError("end must be later than start")
    if end_dt.astimezone(UTC) - start_dt.astimezone(UTC) > timedelta(days=max_days):
        raise InputError(f"date range cannot exceed {max_days} days")
    return start_dt, end_dt


def normalize_event_times(start: str, end: str, *, all_day: bool) -> NormalizedTimes:
    start_raw = str(start).strip()
    end_raw = str(end).strip()
    if all_day:
        if not DATE_RE.fullmatch(start_raw) or not DATE_RE.fullmatch(end_raw):
            raise InputError("all-day start and end must be dates in YYYY-MM-DD format")
        start_value = date.fromisoformat(start_raw)
        end_value = date.fromisoformat(end_raw)
    else:
        start_value = parse_datetime(start_raw, field="start")
        end_value = parse_datetime(end_raw, field="end")

    if end_value <= start_value:
        raise InputError("end must be later than start; all-day end is exclusive")
    return NormalizedTimes(start=start_value, end=end_value, all_day=all_day)


def as_interval(
    start: date | datetime,
    end: date | datetime,
    *,
    timezone: ZoneInfo,
) -> BusyInterval:
    if isinstance(start, datetime):
        start_dt = start if start.tzinfo else start.replace(tzinfo=timezone)
    else:
        start_dt = datetime.combine(start, time.min, tzinfo=timezone)

    if isinstance(end, datetime):
        end_dt = end if end.tzinfo else end.replace(tzinfo=timezone)
    else:
        end_dt = datetime.combine(end, time.min, tzinfo=timezone)
    return BusyInterval(start_dt.astimezone(UTC), end_dt.astimezone(UTC))


def merge_busy(intervals: Iterable[BusyInterval]) -> list[BusyInterval]:
    ordered = sorted(intervals, key=lambda item: item.start)
    merged: list[BusyInterval] = []
    for current in ordered:
        if current.end <= current.start:
            continue
        if not merged or current.start > merged[-1].end:
            merged.append(current)
        else:
            previous = merged[-1]
            merged[-1] = BusyInterval(previous.start, max(previous.end, current.end))
    return merged


def parse_clock(value: str, *, field: str) -> time:
    raw = str(value).strip()
    if not TIME_RE.fullmatch(raw):
        raise InputError(f"{field} must use HH:MM in 24-hour time")
    hour, minute = (int(part) for part in raw.split(":"))
    return time(hour, minute)


def find_free_intervals(
    range_start: datetime,
    range_end: datetime,
    busy: Iterable[BusyInterval],
    *,
    timezone: ZoneInfo,
    duration_minutes: int,
    working_hours_start: str,
    working_hours_end: str,
    weekdays_only: bool,
    limit: int,
) -> list[dict[str, object]]:
    minimum, day_start_clock, day_end_clock = _free_search_constraints(
        duration_minutes,
        working_hours_start,
        working_hours_end,
        limit,
    )

    merged = merge_busy(busy)
    start_local = range_start.astimezone(timezone)
    end_local = range_end.astimezone(timezone)
    current_date = start_local.date()
    final_date = end_local.date()
    results: list[dict[str, object]] = []
    busy_index = 0

    while current_date <= final_date and len(results) < limit:
        if not weekdays_only or current_date.weekday() < 5:
            work_start = datetime.combine(current_date, day_start_clock, tzinfo=timezone)
            work_end = datetime.combine(current_date, day_end_clock, tzinfo=timezone)
            window_start = max(work_start, start_local).astimezone(UTC)
            window_end = min(work_end, end_local).astimezone(UTC)

            if window_end - window_start >= minimum:
                while busy_index < len(merged) and merged[busy_index].end <= window_start:
                    busy_index += 1
                for free in _free_gaps(window_start, window_end, merged, busy_index):
                    if free.end - free.start >= minimum:
                        results.append(_free_slot(free.start, free.end, timezone))
                        if len(results) >= limit:
                            break
        current_date += timedelta(days=1)
    return results


def _free_search_constraints(
    duration_minutes: int,
    working_hours_start: str,
    working_hours_end: str,
    limit: int,
) -> tuple[timedelta, time, time]:
    if not 1 <= duration_minutes <= 24 * 60:
        raise InputError("duration_minutes must be between 1 and 1440")
    if not 1 <= limit <= 100:
        raise InputError("limit must be between 1 and 100")

    day_start = parse_clock(working_hours_start, field="working_hours_start")
    day_end = parse_clock(working_hours_end, field="working_hours_end")
    if day_end <= day_start:
        raise InputError("working_hours_end must be later than working_hours_start")
    return timedelta(minutes=duration_minutes), day_start, day_end


def _free_gaps(
    window_start: datetime,
    window_end: datetime,
    busy: list[BusyInterval],
    start_index: int,
) -> Iterator[BusyInterval]:
    cursor = window_start
    for index in range(start_index, len(busy)):
        interval = busy[index]
        if interval.start >= window_end:
            break
        clipped_start = max(interval.start, window_start)
        if clipped_start > cursor:
            yield BusyInterval(cursor, clipped_start)
        cursor = max(cursor, min(interval.end, window_end))
    if cursor < window_end:
        yield BusyInterval(cursor, window_end)


def _free_slot(start: datetime, end: datetime, timezone: ZoneInfo) -> dict[str, object]:
    return {
        "start": start.astimezone(timezone).isoformat(),
        "end": end.astimezone(timezone).isoformat(),
        "available_minutes": int((end - start).total_seconds() // 60),
    }
