# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Home Assistant

- Added registry-aware read-only tools for arbitrary entities, devices, people,
  locations, availability, and bounded history.
- Added natural-language matching across friendly names, entity IDs, device
  registry, area registry, Russian morphology, and transliteration.
- Marked read and write tools explicitly with MCP annotations while preserving
  the existing write allowlist and approval policy.
- Added an optional 10-minute location recorder with private SQLite storage and
  a configurable retention window that defaults to 72 hours.
- Added optional reverse geocoding inside the MCP process; it remains disabled
  until a trusted HTTPS endpoint is explicitly configured.
- Clarified `not_home` as a Home Assistant zone state rather than a statement
  about residence, and improved address-level reverse-geocoding requests.
- Omitted the technical home-zone status from ordinary person-location answers.

### Calendar

- Added confirmed event deletion with the same prepare/commit safety model used
  for event creation.

### Deployment

- Reworked the Russian and English project documentation around the current MCP
  feature set and production setup.
- Added a strict deployment preflight that checks installation, permissions,
  generated configuration, Git state, and the pinned Hermes revision without
  publishing or deploying anything.

## 0.3.0 - 2026-09-28

### Calendar

- Added multi-account routing with stable account IDs and a configurable default calendar
  account.
- Added Google Calendar OAuth/API support alongside the existing CalDAV implementation.
- Added provider presets and examples for Google Calendar, iCloud, Yandex, Mail.ru, and custom
  CalDAV.
- Added per-account write policy while preserving short-lived proposals, idempotent commits,
  and interactive confirmation.
- Added account discovery and account metadata to provider-backed results.
- Kept the legacy single-iCloud environment variables as a migration fallback.

### Email

- Added multi-account routing with stable account IDs and a configurable default mailbox.
- Kept the Gmail OAuth adapter and added an encrypted IMAP/SMTP adapter for standards-based
  providers.
- Added per-account send policy, app-password files, account discovery, and account metadata on
  every result.
- Renamed the module and entry point to the provider-neutral `mcp/email` and `email-mcp` names.
- Added provider directories and built-in connection presets for Gmail, Yandex, Mail.ru, and
  iCloud.
- Kept the legacy single-Gmail environment variables as a migration fallback.

## 0.2.1 - 2026-09-26

### Privacy

- Rebuilt the public Git history from a clean root commit.
- Replaced personal author and committer metadata with a generic no-reply
  identity.
- Removed personal profile names, public server addresses, private hostnames,
  absolute server home paths, and profile-specific service instructions from
  the reachable repository history.
- Pointed the Hermes submodule at the official upstream repository rather than
  a personal fork.
- Added repository-wide regression tests for personal email domains, public
  IPv4 addresses, absolute user home paths, tailnet hostnames, literal profile
  paths, and profile-specific gateway unit names.

### Included from 0.2.0

- Published 16 reusable, profile-independent Hermes skills for travel,
  planning, shopping, communication, projects, household tasks, recurring
  reviews, and VkusVill workflows.
- Added installation guidance and privacy tests for the public skill library.
- Fixed generated systemd user units so `WorkingDirectory` and `ExecStart`
  contain valid absolute paths without literal JSON quotes.

### Upgrade notes

- Clone the repository again because the public Git history was intentionally
  replaced.
- No application configuration or MCP API migration is required.
