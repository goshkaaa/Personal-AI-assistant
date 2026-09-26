---
name: cronjob-management
description: "Use when scheduling reminders via Hermes cronjob_manage."
tags: [cronjob, reminders, scheduling, automation]
---

# Cronjob Management

## Tool

Hermes `cronjob_manage` (cronjob plugin). Actions: create, list, update, pause, resume, remove, run.

## Procedure

1. **List existing** — `action: list` to check for duplicates before creating.
2. **Create** — `action: create` with `name`, `prompt`, `schedule`, `deliver`.
3. **Verify** — Confirm via `action: list` that job has correct `next_run_at`.

## Schedule Formats

| Format | Example | Use |
|---|---|---|
| One-shot ISO | `2026-09-28T09:00:00` | Specific date/time |
| One-shot relative | `in 30m`, `in 2h` | "Remind me in N minutes" |
| Interval | `every 15m`, `every 2h` | Recurring |
| Natural day/time | `every monday 9am` | Weekly |
| Daily | `every day at 9am` | Daily |
| Cron | `0 9 * * *` | Advanced |

## Delivery

| Target | Goes To |
|---|---|
| `origin` | Origin chat (default) |
| `local` | Local files only |
| `all` | All home channels |
| `telegram:<id>` | Specific chat |

## Pitfalls

1. **Single job only.** `cronjob_manage` does NOT accept a `jobs` array. Each job = one tool call. When N reminders are needed, make N sequential calls. Do not attempt batch creation — it silently fails with "schedule is required".

2. **Future times only.** One-shot ISO times must be in the future. If a requested reminder time has already passed, skip cron and inform the user.

3. **Self-contained prompts.** Jobs run in fresh sessions with zero chat context. Embed ALL specifics in the prompt: what, when, where, timezone, required actions. Never reference "today" or "your class" — spell it out.

4. **Duplicates.** Always `list` first when scheduling recurring reminders (e.g., weekly classes). Near-duplicates cause double-fires. Use `update` to adjust existing jobs.

5. **`run` needs `job_id`.** `run` fires an existing job immediately (by ID). `create` makes a new one. Never mix them.