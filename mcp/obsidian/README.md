# Obsidian MCP

Создание, чтение и поиск Markdown-заметок в Obsidian vault.

```bash
cp .env.example .env
uv sync --locked --no-editable
.venv/bin/obsidian-mcp
```

Путь к vault задаётся через `OBSIDIAN_VAULT_PATH`. Модуль не даёт выйти за пределы vault и отклоняет
похожий на токен текст.
