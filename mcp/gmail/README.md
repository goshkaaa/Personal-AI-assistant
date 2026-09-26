# Gmail MCP

Поиск и чтение писем, треды, новые письма, ответы и черновики. Отправка по
умолчанию выключена: для неё нужны `MCP_ALLOW_EMAIL_SEND=true` и явное
подтверждение в конкретном вызове инструмента.

```bash
cp .env.example .env
uv sync --locked --no-editable
# положить OAuth desktop credentials по пути из GMAIL_CREDENTIALS_FILE
.venv/bin/gmail-auth
.venv/bin/gmail-mcp
```

По умолчанию OAuth-файлы лежат в
`~/.config/personal-ai-assistant/secrets/`, вне checkout.
