# Home Assistant MCP

Чтение состояний и вызов разрешённых Home Assistant services.

```bash
cp .env.example .env
uv sync --locked --no-editable
.venv/bin/homeassistant-mcp
```

Укажите URL и private token file в `.env`. Вызов services по умолчанию выключен.
