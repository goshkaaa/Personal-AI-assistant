---
name: date-time-reasoning
description: Load for dates, deadlines, schedules, or relative time.
---

# Date & Time Reasoning

Use this skill whenever dates, times, deadlines, schedules, time zones, or relative expressions matter.

## Core rules

Never guess the current date or time.

Use the current date and timezone supplied by the runtime/system context.

When the exact current time matters, verify it using an available time or terminal tool.

Resolve relative expressions such as:
- today
- tomorrow
- yesterday
- this weekend
- next week
- next Tuesday
- in three days
- by the end of the month
- this evening

into concrete calendar dates before planning around them.

Always verify that the weekday matches the calendar date.

Never silently change a user-provided date.

If the user gives contradictory information, such as a weekday that does not match the date, point out the conflict and ask which one they mean when the distinction matters.

## Time zones

Distinguish between:
- the user's timezone;
- the destination or event timezone;
- UTC when relevant.

For travel, calls, events, reminders, bookings, and deadlines, explicitly reason about the relevant timezone.

Do not silently assume two locations use the same timezone.

## Missing information

Do not invent:
- year;
- month;
- day;
- time;
- timezone;
- duration.

Infer them only when they follow unambiguously from the conversation or runtime context.

Ask only when the missing information prevents useful progress.

## Actions

Before creating, changing, booking, or scheduling anything:

1. resolve relative dates;
2. verify weekday/date consistency;
3. verify timezone;
4. verify start and end times;
5. preserve the user's original intent.

For consequential actions, show the resolved date and time before confirmation.

## Combining skills

This skill may be used together with other skills.

Examples:
- travel + dates -> `travel-concierge` + `date-time-reasoning`
- appointment + dates -> `appointments` + `date-time-reasoning`
- event planning -> `event-planner` + `date-time-reasoning`
- calendar administration -> `personal-admin` + `date-time-reasoning`
