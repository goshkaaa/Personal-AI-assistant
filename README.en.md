# Personal AI Assistant

[Russian version](README.md)

A self-hosted assistant built on
[Hermes Agent](https://github.com/NousResearch/hermes-agent), with independent MCP
integrations for Telegram, email, calendars, Home Assistant, and Obsidian.

The complete stack can be deployed together, or each MCP can be installed on its
own. Credentials, sessions, databases, personal prompts, and generated
configuration are intentionally kept outside Git.

## Integrations

| Integration | Capabilities |
| --- | --- |
| Telegram | Search and read chats, send messages, and run background conversation tasks |
| Email | Multiple Gmail and IMAP/SMTP accounts, search/read, drafts/replies, confirmed sending |
| Calendars | Multiple Google Calendar and CalDAV accounts, events, free slots, confirmed create/delete workflows |
| Home Assistant | Universal entity/device/history reads, registry-aware natural-language lookup, location, and separate write tools |
| Obsidian | Create, read, search, and update Markdown notes inside one vault |
| VkusVill | Product and recipe search through a remote MCP |

Reusable, profile-independent workflows live in [`skills/`](skills/README.md).

## Architecture and security

- Hermes is pinned as the `hermes/hermes-agent` Git submodule.
- Every local MCP has an independent locked environment and configuration.
- Long-lived credentials default to `~/.config/personal-ai-assistant/secrets/`.
- Runtime databases and sessions default to
  `~/.local/share/personal-ai-assistant/`.
- Read and write operations are separate. Email, calendar, and Home Assistant
  writes are never enabled implicitly.
- `.env`, generated `.local/` files, sessions, databases, logs, backups, exact
  location data, and personal server/entity identifiers must not be committed.

## Quick start

Requirements: Linux or macOS, Git, Python 3.11–3.13, and
[`uv`](https://docs.astral.sh/uv/).

```bash
git clone --recurse-submodules <repository-url> personal-ai-assistant
cd personal-ai-assistant
make setup
.venv/bin/hermes setup
```

Configure only the integrations you need. Example authorization commands:

```bash
mcp/telegram/.venv/bin/telegram-login
mcp/email/.venv/bin/email-auth --account <account-id>
mcp/calendar/.venv/bin/calendar-auth --account <account-id>

make config
make check
```

Merge the required entries from the private `.local/hermes-mcp.yaml` into
`~/.hermes/config.yaml`. Disable every MCP that has not been configured.

See [deployment/README.md](deployment/README.md) and the README in each MCP
directory for account, OAuth, credential, and production setup details.

## Home Assistant

The Home Assistant MCP combines the REST state/history API with entity, device,
and area registries from the WebSocket API. Read-only tools can:

- resolve human names and room descriptions to HA entities;
- return full state and attributes for any entity;
- inspect devices and their related entities;
- read person or phone location;
- query bounded history;
- list entities by domain, area, device, or availability.

Read-only tools carry `readOnlyHint=true`. Service calls, device control, locks,
covers, scripts, and automations remain separate write tools governed by the
existing approval and allowlist policy. The HA token is read only inside the MCP
process and is never passed in model-visible tool arguments.

For location responses, HA's technical `not_home` state only means that the
entity is outside the configured Home Assistant home zone. It does not describe
the person's residence. For an ordinary location question the assistant omits
that technical state and prefers the resolved address or a named non-home zone.

An optional local recorder can retain consented location points for a maximum of
72 hours. External reverse geocoding is disabled by default so precise coordinates
are not disclosed to a third party.

## Running

Local chat:

```bash
.venv/bin/hermes --tui
```

Messaging gateway:

```bash
.venv/bin/hermes gateway setup
.venv/bin/hermes gateway install
.venv/bin/hermes gateway start
.venv/bin/hermes gateway status
```

On Linux, install optional Telegram workers and the configured HA location
recorder as systemd user services:

```bash
make services
```

## Deployment preflight

Run this before every deployment or push:

```bash
make deploy-check
```

It runs formatting and lint checks, unit tests, process-level MCP handshakes,
repository and Git-history secret scans, and an operational deployment preflight.
It does not publish or deploy anything.

## Updating

```bash
git pull --ff-only
git submodule update --init --recursive
make setup
make deploy-check
.venv/bin/hermes gateway restart
```

Back up private configuration and runtime data outside the checkout before an
upgrade.

## Project structure

```text
deployment/    setup, config generation, preflight, and systemd user services
mcp/           independent MCP integrations
scripts/       project checks and secret scanning
tests/         process-level integration tests
skills/        reusable sanitized Hermes skills
hermes/        pinned Hermes Agent submodule
```

## License

[MIT](LICENSE)
