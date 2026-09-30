# Personal AI Assistant

[English version](README.en.md)

Self-hosted ИИ-ассистент на базе
[Hermes Agent](https://github.com/NousResearch/hermes-agent) с набором независимых
MCP-модулей для Telegram, почты, календарей, Home Assistant и Obsidian.

Проект можно запустить целиком или взять только нужный MCP. Секреты,
сессии, локальные базы и персональные промпты в Git не хранятся.

## Возможности

| Интеграция | Что умеет |
| --- | --- |
| Telegram | Искать и читать чаты, отправлять сообщения, запускать фоновые задачи по диалогам |
| Email | Несколько Gmail/IMAP/SMTP-аккаунтов, поиск и чтение, drafts/replies, отправка с подтверждением |
| Calendars | Google Calendar и CalDAV, несколько аккаунтов, события, free slots, создание и удаление через prepare/confirm workflow |
| Home Assistant | Универсальное read-only чтение entities/devices/history, поиск по имени и area, геопозиция, отдельные write-tools |
| Obsidian | Создавать, читать, искать и дополнять Markdown-заметки в рамках одного vault |
| ВкусВилл | Искать товары и рецепты через удалённый MCP |

Для типичных сценариев есть обезличенные reusable skills в
[`skills/`](skills/README.md).

## Как это устроено

- Hermes закреплён как Git submodule в `hermes/hermes-agent`.
- Каждый локальный MCP имеет свои `pyproject.toml`, `uv.lock`, `.venv` и `.env`.
- Долгоживущие secrets по умолчанию лежат в
  `~/.config/personal-ai-assistant/secrets/`.
- Runtime-данные и SQLite-базы лежат в
  `~/.local/share/personal-ai-assistant/`.
- Read-only и write-операции разделены. Почта, календари и Home Assistant
  не получают write-доступ неявно.

## Быстрый старт

Требования: Linux или macOS, Git, Python 3.11–3.13 и
[`uv`](https://docs.astral.sh/uv/).

```bash
git clone --recurse-submodules <repository-url> personal-ai-assistant
cd personal-ai-assistant
make setup
```

`make setup` создаёт окружение Hermes, устанавливает каждый MCP в свою `.venv`,
копирует безопасные `.env.example` и создаёт приватные каталоги. Существующие
`.env` не перезаписываются.

Затем настройте Hermes и только нужные интеграции:

```bash
.venv/bin/hermes setup

# Примеры интерактивной авторизации
mcp/telegram/.venv/bin/telegram-login
mcp/email/.venv/bin/email-auth --account <account-id>
mcp/calendar/.venv/bin/calendar-auth --account <account-id>

make config
make check
```

`make config` создаст приватный `.local/hermes-mcp.yaml` с абсолютными
путями. Перенесите нужные entries в `~/.hermes/config.yaml` и отключите
ненастроенные MCP.

Подробная настройка credentials, OAuth, accounts и server deployment описана
в [deployment guide](deployment/README.md) и README каждого MCP.

## Home Assistant: универсальное чтение

Home Assistant MCP использует REST API для state/history и WebSocket API для
entity, device и area registry. Благодаря этому Hermes может разрешать
человеческие запросы без shell-команд:

- «где Иван» → `person.*` или `device_tracker.*`;
- «какая температура дома» → temperature sensors;
- «включен ли свет в ванной» → `light.*` в нужной area;
- «какие устройства недоступны» → entities с `unavailable/unknown`.

Read-only tools помечены MCP annotation `readOnlyHint=true` и не требуют
подтверждения. Включение света, работа с locks/covers, запуск services
и другие write-операции остаются отдельными tools. Глобально отключать
approvals не нужно.

Токен Home Assistant читает только MCP-процесс. Модель не получает token в
arguments и не должна читать `.env`.

Для геопозиции техническое состояние HA `not_home` означает только нахождение
вне настроенной домашней зоны Home Assistant. Оно не описывает место жительства;
в обычном вопросе о местоположении бот не упоминает этот статус и отвечает
найденным адресом или именованной зоной, а затем координатами и картой.

### Краткая история геопозиции

Если телефон уже передаёт координаты в HA, опциональный recorder может
сохранять точки каждые 10 минут и автоматически удалять записи старше 72 часов:

```dotenv
HOME_ASSISTANT_LOCATION_ENTITIES=person.example
HOME_ASSISTANT_LOCATION_INTERVAL_SECONDS=600
HOME_ASSISTANT_LOCATION_RETENTION_HOURS=72
```

База хранится вне Git с правами `0600`. Включайте функцию только для людей,
которые согласились делиться геопозицией. Внешний reverse geocoding по умолчанию
выключен, чтобы не передавать точные координаты третьей стороне.

## Запуск

Локальный чат:

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

На Linux можно добавить systemd user services для Telegram workers и для HA location
recorder, если он настроен:

```bash
make services
```

## Безопасность перед deployment

Никогда не добавляйте в Git:

- `.env`, Hermes config/SOUL/memory и generated `.local/`;
- API keys, OAuth tokens, app passwords, HA tokens;
- Telegram session-файлы;
- SQLite-базы, logs, backups и точные геоданные;
- личные server addresses, absolute home paths и entity IDs.

Перед каждым deployment и push:

```bash
make deploy-check
```

Команда запускает formatting/lint, unit- и process-level integration tests, MCP stdio
handshake, secret scan текущего worktree и истории Git, а также operational preflight.

## Обновление

```bash
git pull --ff-only
git submodule update --init --recursive
make setup
make deploy-check
.venv/bin/hermes gateway restart
```

Перед обновлением сделайте резервную копию приватных config/data вне checkout.

## Структура

```text
deployment/    setup, config generation, preflight и systemd user services
mcp/           независимые MCP-интеграции
scripts/       project checks и secret scanning
tests/         process-level integration тесты
skills/        reusable обезличенные Hermes skills
hermes/        закреплённый Hermes Agent submodule
```

## Разработка

```bash
make check          # все тесты и secret scan
make config         # сгенерировать локальный MCP config
make services       # установить background user services
make deploy-check   # полная предрелизная проверка
```

Актуальные изменения описаны в [CHANGELOG.md](CHANGELOG.md).

## Лицензия

[MIT](LICENSE)
