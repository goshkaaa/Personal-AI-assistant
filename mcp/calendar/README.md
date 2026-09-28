# Apple Calendar MCP

CalDAV-модуль для iCloud Calendar: события, свободные окна и создание событий с
подтверждением.

```bash
cp .env.example .env
uv sync --locked --no-editable
.venv/bin/python scripts/configure_icloud.py
.venv/bin/calendar-mcp
```

Нужен app-specific password от Apple. Запись в календарь по умолчанию выключена в `.env`.
