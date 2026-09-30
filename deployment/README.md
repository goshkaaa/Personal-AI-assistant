# Deployment

Инструкция для чистой установки и обновления Personal AI Assistant на Linux/macOS.
Команды из этого документа не публикуют repository и не загружают секреты
во внешние сервисы.

## Модель хранения

| Данные | Место | Git |
| --- | --- | --- |
| Source code и безопасные examples | checkout | Да |
| API keys, OAuth tokens, app passwords | `~/.config/personal-ai-assistant/secrets/` | Нет |
| MCP `.env` | `mcp/<service>/.env`, mode `0600` | Нет |
| Hermes config, SOUL, memory | `~/.hermes/` | Нет |
| Telegram sessions и SQLite | `~/.local/share/personal-ai-assistant/` | Нет |
| Generated MCP block | `.local/hermes-mcp.yaml`, mode `0600` | Нет |

Не копируйте private config в `hermes/hermes-agent`: это публичный Git submodule.

## 1. Требования

- обычный непривилегированный user;
- Git;
- Python 3.11–3.13;
- [`uv`](https://docs.astral.sh/uv/);
- Linux с systemd user services для постоянного gateway и workers или другой supervisor.

## 2. Чистая установка

```bash
git clone --recurse-submodules <repository-url> personal-ai-assistant
cd personal-ai-assistant
make setup
```

Если checkout был создан без submodule:

```bash
git submodule update --init --recursive
make setup
```

`make setup` не перезаписывает уже существующие `.env`.

## 3. Приватная конфигурация

Заполните только нужные модули:

- `mcp/telegram/.env`;
- `mcp/email/.env`;
- `mcp/calendar/.env`;
- `mcp/homeassistant/.env`;
- `mcp/obsidian/.env`.

В `.env` лучше хранить пути к private credential files, а не сами long-lived secrets.
Проверьте права:

```bash
chmod 600 mcp/*/.env
chmod 600 ~/.config/personal-ai-assistant/secrets/*
```

Не включайте write до успешной read-only проверки. Для email и calendar write-доступ
включается поаккаунтно; для Home Assistant — через
`MCP_ALLOW_HOME_ASSISTANT_WRITE=true` и существующую approval policy Hermes.

## 4. Accounts и авторизация

### Telegram

```bash
mcp/telegram/.venv/bin/telegram-login
mcp/telegram/.venv/bin/telegram-listener-login
```

Session-файлы должны остаться в runtime-каталоге вне checkout.

### Email

Скопируйте `mcp/email/accounts.example.json` в private secrets directory и укажите
путь через `EMAIL_ACCOUNTS_FILE`.

```bash
mcp/email/.venv/bin/email-auth --account <gmail-account-id>
mcp/email/.venv/bin/email-store-password --account <imap-account-id>
```

### Calendars

Скопируйте `mcp/calendar/accounts.example.json` в private secrets directory и укажите
путь через `CALENDAR_ACCOUNTS_FILE`.

```bash
mcp/calendar/.venv/bin/calendar-auth --account <google-account-id>
mcp/calendar/.venv/bin/calendar-store-password --account <caldav-account-id>
```

До включения calendar write укажите непрозрачный `write_calendar_id`. Создание
и удаление событий используют short-lived prepare/commit proposals и подтверждение.

### Home Assistant

Создайте long-lived token в HA, сохраните его одной строкой в private file с
правами `0600` и укажите только путь через `HOME_ASSISTANT_TOKEN_FILE`.

После запуска проверьте read-only state, registry resolution и history. Внешний reverse
geocoder оставьте выключенным, если нет доверенного endpoint и явного согласия
на передачу координат.

## 5. Подключение MCP

```bash
make config
```

Перенесите entries из `.local/hermes-mcp.yaml` в существующий `mcp_servers` в
`~/.hermes/config.yaml`. Не создавайте второй YAML-ключ `mcp_servers`. Отключите все
модули, которые не были настроены.

Сгенерированный YAML не содержит values из `.env`, но содержит локальные
absolute paths, поэтому он всё равно хранится с правами `0600` и не попадает в Git.

## 6. Preflight

Для release candidate с ещё незакоммиченными изменениями:

```bash
make check
deployment/preflight.py --allow-dirty --source-only
```

Перед реальным deployment или push worktree должен быть чистым:

```bash
make deploy-check
```

Строгий preflight проверяет:

- lint, format, unit и MCP process integration tests;
- secret signatures в tracked/untracked files и истории Git;
- чистый Git worktree и `git diff --check`;
- точный pinned revision Hermes submodule;
- наличие locked MCP environments и executable entrypoints;
- права на `.env` и generated MCP config;
- защиту private `.env` через `.gitignore`.

Preflight ничего не публикует и не перезаписывает runtime-данные.

## 7. Gateway и background services

```bash
.venv/bin/hermes gateway setup
.venv/bin/hermes gateway install
.venv/bin/hermes gateway start
.venv/bin/hermes gateway status
```

На Linux после авторизации Telegram sessions:

```bash
make services
systemctl --user --no-pager status personal-assistant-telegram-listener.service
```

`make services` также установит HA location recorder, если
`HOME_ASSISTANT_LOCATION_ENTITIES` не пуст.

Для user services, которые должны работать без активной SSH-сессии, администратор
может включить linger для service user. Это системная операция и не выполняется
автоматически.

## Обновление

1. Создайте бэкап `~/.hermes`, private secrets и runtime data вне checkout.
2. Обновите код и pinned submodule.
3. Пересоберите locked environments.
4. Выполните preflight до restart.

```bash
git pull --ff-only
git submodule update --init --recursive
make setup
make deploy-check
.venv/bin/hermes gateway restart
```

Если preflight не прошёл, не перезапускайте production service до устранения ошибки.

## Откат

Секреты и runtime data не зависят от Git revision. Для отката верните предыдущий проверенный
commit/tag, повторите `make setup`, `make deploy-check` и только после этого перезапустите gateway.
Не используйте для отката деструктивные Git-команды в checkout с несохранёнными изменениями.
