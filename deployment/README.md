# Deployment

The repository contains no credentials. Long-lived secrets default to
`~/.config/personal-ai-assistant/secrets`, while sessions and databases default
to `~/.local/share/personal-ai-assistant`.

## 1. Install

Use an unprivileged user on Debian/Ubuntu or macOS:

```bash
git clone --recurse-submodules <repository-url> personal-ai-assistant
cd personal-ai-assistant
make setup
```

## 2. Configure

Fill only the modules you plan to use:

- `mcp/telegram/.env`
- `mcp/gmail/.env`
- `mcp/calendar/.env`
- `mcp/homeassistant/.env`
- `mcp/obsidian/.env`

Keep credentials in private mode-0600 files outside the repository. Then
authorize the interactive integrations:

```bash
mcp/telegram/.venv/bin/telegram-login
mcp/gmail/.venv/bin/gmail-auth
```

## 3. Connect MCP modules

```bash
make config
```

Merge `.local/hermes-mcp.yaml` into `~/.hermes/config.yaml`. Disable modules
that you did not configure.

## 4. Start Hermes

```bash
.venv/bin/hermes gateway setup
.venv/bin/hermes gateway install
.venv/bin/hermes gateway start
.venv/bin/hermes gateway status
```

On a Linux server, install the Telegram background workers after authorizing
both Telegram sessions:

```bash
make services
```

## Update

```bash
git pull --ff-only
git submodule update --init --recursive
make setup
make check
.venv/bin/hermes gateway restart
```
