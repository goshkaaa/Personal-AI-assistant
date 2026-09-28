# Personal AI Assistant

[Русская версия](README.md)

This is my personal AI agent, configured around the services and workflows I
use. I am publishing the first version in case the complete setup, its
architecture, or individual MCP servers are useful to someone else.

The project is built on [Hermes Agent](https://github.com/NousResearch/hermes-agent)
and adds small, independent integrations for Telegram, email, calendars,
Home Assistant, Obsidian, and VkusVill.

## Integrations

| Service | Capabilities |
| --- | --- |
| Telegram | Search and read chats, send and reply, run background conversation tasks |
| Email | Multiple Gmail, Yandex, Mail.ru, iCloud, and custom IMAP/SMTP accounts |
| Calendars | Multiple Google, iCloud, Yandex, Mail.ru, and custom CalDAV accounts |
| Home Assistant | Read states and call explicitly allowed services |
| Obsidian | Create, read, search, and update Markdown notes |
| VkusVill | Search products through the official remote MCP |

Every local MCP can be installed and enabled independently. This is a flexible
personal setup, not a universal framework or hosted product.

## Reusable skills

Sanitized, profile-independent skills for travel, planning, shopping,
communication, projects, and other common tasks are published in
[`skills/`](skills/README.md). Public skills already bundled with Hermes are
not duplicated here and remain available through the pinned submodule.

## Quick start

Requirements: Linux or macOS, Git, Python 3.11–3.13, and
[uv](https://docs.astral.sh/uv/).

```bash
git clone --recurse-submodules <repository-url> personal-ai-assistant
cd personal-ai-assistant
make setup
```

Configure Hermes:

```bash
.venv/bin/hermes setup
.venv/bin/hermes --tui
```

Copy the generated MCP block from `.local/hermes-mcp.yaml` into the intended
Hermes profile at `~/.hermes/config.yaml`. Configure only the integrations you
need in `mcp/*/.env`.

Detailed setup instructions for credentials, OAuth, Telegram authorization,
the Hermes gateway, and systemd services are available in the
[Russian README](README.md) and [deployment guide](deployment/README.md).

## Security model

- No personal credentials, sessions, prompts, or personal skills are stored in
  Git. The `skills/` directory contains only reusable, sanitized skills.
- Long-lived secrets default to `~/.config/personal-ai-assistant/secrets`.
- Sessions and databases default to `~/.local/share/personal-ai-assistant`.
- Email, calendar, and Home Assistant writes are disabled by default.
- The repository check scans tracked and new worktree files plus Git history for common secrets.

Hermes is pinned as a Git submodule. Keep personal Hermes configuration and
skills in `~/.hermes`, never inside the submodule directory.

## Development

```bash
make check     # lint, formatting, unit and process-level integration tests
make config    # regenerate the Hermes MCP configuration block
make services  # install Telegram systemd user services on Linux
```

The integration suite starts every local MCP as a separate process, performs a
real stdio protocol handshake, checks its public tool contract, and exercises
an Obsidian tool call without using real credentials.

## Structure

```text
deployment/    setup, config generation, and systemd user services
mcp/           independent MCP integrations
scripts/       project checks and secret scanning
tests/         process-level integration tests
skills/        reusable, sanitized Hermes skills
hermes/        pinned Hermes Agent submodule
```

## Status

The current project release is `v0.2.1`. See [CHANGELOG.md](CHANGELOG.md) for
release notes and upgrade guidance. Interfaces and structure may still change.

## License

[MIT](LICENSE)
