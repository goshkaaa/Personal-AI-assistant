# Telegram Userbot MCP

Telegram-юзербот с MCP-инструментами и фоновым воркером для долгих диалогов.

```bash
cp .env.example .env
uv sync --locked --no-editable
.venv/bin/telegram-login
.venv/bin/telegram-listener-login
.venv/bin/telegram-mcp
```

Фоновые процессы:

```bash
.venv/bin/telegram-listener
.venv/bin/telegram-worker
.venv/bin/telegram-notifier
```

Структура пакета:

```text
src/telegram_mcp/
├── app.py       сборка MCP-сервера
├── client.py    создание Pyrogram-клиента
├── service.py   Telegram-операции
├── tools.py     тонкий MCP-слой
└── tasks/       БД, очереди, worker и уведомления
```

Сессии и база по умолчанию лежат в
`~/.local/share/personal-ai-assistant/telegram`, вне checkout.
