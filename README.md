# Personal AI Assistant

[English version](README.en.md)

Это мой личный ИИ-агент, настроенный под мои задачи и сервисы. Я публикую его
как есть в надежде, что кому-то пригодится весь проект, его архитектура или
отдельные MCP-модули.

Проект построен поверх [Hermes Agent](https://github.com/NousResearch/hermes-agent).
Здесь находятся воспроизводимый deployment, Telegram-юзербот и небольшие MCP
для Gmail, Apple Calendar, Home Assistant, Obsidian и ВкусВилла.

Это первая версия всего проекта. Структура и интерфейсы ещё могут меняться,
но чистая установка, безопасное хранение секретов и автоматические проверки
уже готовы.

## Что умеет

- Telegram: искать чаты, читать, отправлять и продолжать диалоги;
- Gmail: искать письма и треды, создавать обычные и reply-черновики,
  отправлять новые письма и ответы после явного подтверждения;
- Apple Calendar: читать события, искать свободное время и создавать события
  через двухэтапное подтверждение;
- Home Assistant: читать состояния и вызывать только разрешённые services;
- Obsidian: создавать, читать, искать и дополнять Markdown-заметки;
- ВкусВилл: искать товары через официальный удалённый MCP.

Каждый MCP устанавливается отдельно и не зависит от остальных. Deployment
пока ориентирован на Hermes и мой набор сервисов: это гибкая личная сборка,
а не универсальный фреймворк или готовый SaaS.

## Универсальные skills

Обезличенные пользовательские skills для путешествий, планирования,
покупок, коммуникации, проектов и других общих задач опубликованы в
[`skills/`](skills/README.md). Публичные skills, уже входящие в Hermes, здесь
не дублируются и доступны через закреплённый submodule.

## Где лежат личные данные

В Git нет моих токенов, сессий, OAuth-файлов, персональных skills или
промптов. Каталог `skills/` содержит только универсальные обезличенные skills.

- Hermes хранит секреты в `~/.hermes/.env`, настройки в
  `~/.hermes/config.yaml`, а пользовательские skills в `~/.hermes/skills/`;
- секреты MCP по умолчанию лежат в
  `~/.config/personal-ai-assistant/secrets/`;
- Telegram-сессии и локальные базы лежат в
  `~/.local/share/personal-ai-assistant/`;
- файлы `.env` внутри `mcp/*` содержат только локальные настройки и
  игнорируются Git.

Каталог `hermes/hermes-agent` — Git submodule. YAML, prompts и skills внутри
него являются публичными файлами Hermes; корневой репозиторий хранит только
URL и commit submodule. Не кладите свои настройки и skills внутрь этого
каталога — используйте `~/.hermes/`.

## Установка с нуля

Нужны Linux или macOS, Git, Python 3.11–3.13 и
[uv](https://docs.astral.sh/uv/). Для постоянной работы на сервере удобнее
Debian/Ubuntu с обычным непривилегированным пользователем.

```bash
git clone --recurse-submodules <repository-url> personal-ai-assistant
cd personal-ai-assistant
make setup
```

Если репозиторий уже был клонирован без submodule:

```bash
git submodule update --init --recursive
make setup
```

`make setup` создаёт окружение Hermes в `.venv`, отдельное окружение для
каждого MCP, локальные `.env` из безопасных примеров и приватные каталоги для
данных. Существующие настройки команда не перезаписывает.

## 1. Настройте Hermes

Запустите мастер и выберите провайдера и модель:

```bash
.venv/bin/hermes setup
```

Мастер сам положит API-ключ в `~/.hermes/.env`, а обычные настройки — в
`~/.hermes/config.yaml`. Не переносите эти значения в репозиторий.

Проверьте базовый чат до подключения интеграций:

```bash
.venv/bin/hermes --tui
```

Если Hermes отвечает, переходите к нужным MCP. Настраивать все сразу не
обязательно.

## 2. Настройте нужные MCP

### Telegram userbot

Это не Telegram-бот Hermes Gateway. Userbot работает от обычного Telegram
аккаунта и даёт агенту доступ к вашим диалогам.

1. Создайте приложение на [my.telegram.org](https://my.telegram.org/) и
   получите `api_id` и `api_hash`.
2. Заполните `TG_API_ID` и `TG_API_HASH` в `mcp/telegram/.env`.
3. Авторизуйте основную и фоновую сессии:

```bash
mcp/telegram/.venv/bin/telegram-login
mcp/telegram/.venv/bin/telegram-listener-login
```

Telegram попросит номер, код и пароль 2FA, если он включён. Session-файлы
будут созданы вне репозитория. Подробнее: [mcp/telegram/README.md](mcp/telegram/README.md).

### Gmail

1. В Google Cloud включите Gmail API и создайте OAuth client типа
   **Desktop app**.
2. Скачанный JSON сохраните как
   `~/.config/personal-ai-assistant/secrets/gmail-credentials.json`.
3. Запустите OAuth:

```bash
mcp/gmail/.venv/bin/gmail-auth
```

На удалённом сервере заранее откройте SSH port forwarding для callback-порта
`8766`, затем откройте выданную ссылку в локальном браузере.

Чтение и черновики доступны сразу после OAuth. Реальная отправка остаётся
выключенной, пока в `mcp/gmail/.env` не установлено
`MCP_ALLOW_EMAIL_SEND=true`; каждый send/reply дополнительно требует явного
подтверждения вызова. Подробнее: [mcp/gmail/README.md](mcp/gmail/README.md).

### Apple Calendar

1. Создайте отдельный app-specific password на
   [account.apple.com](https://account.apple.com/); основной пароль Apple не
   используется.
2. Укажите Apple Account email и timezone в `mcp/calendar/.env`.
3. Сохраните пароль безопасным интерактивным помощником:

```bash
mcp/calendar/.venv/bin/python mcp/calendar/scripts/configure_icloud.py
```

Сначала оставьте `MCP_ALLOW_CALENDAR_WRITE=false`. После проверки чтения
получите ID нужного календаря, запишите его в `CALENDAR_WRITE_CALENDAR_ID` и
только затем включайте запись. Подробнее: [mcp/calendar/README.md](mcp/calendar/README.md).

### Home Assistant

1. Создайте Long-Lived Access Token в профиле Home Assistant.
2. Сохраните его одной строкой в
   `~/.config/personal-ai-assistant/secrets/home-assistant-token` и выполните
   `chmod 600` для файла.
3. Укажите `HOME_ASSISTANT_URL` в `mcp/homeassistant/.env`.

Запись по умолчанию выключена. Включайте
`MCP_ALLOW_HOME_ASSISTANT_WRITE=true` только после проверки read-only tools.
Подробнее: [mcp/homeassistant/README.md](mcp/homeassistant/README.md).

### Obsidian

Укажите абсолютный или home-relative путь к vault:

```dotenv
OBSIDIAN_VAULT_PATH=~/Obsidian
```

Модуль не выходит за пределы vault и отклоняет текст, похожий на credential.
Подробнее: [mcp/obsidian/README.md](mcp/obsidian/README.md).

### ВкусВилл

Это удалённый MCP без локальной установки. Его адрес уже есть в генерируемой
конфигурации. Создание корзины не подтверждает покупку или оплату.

## 3. Подключите MCP к Hermes

Сгенерируйте блок с абсолютными путями текущей установки:

```bash
make config
```

Команда создаст `.local/hermes-mcp.yaml`. Перенесите блок `mcp_servers` в
`~/.hermes/config.yaml`. Если такой блок уже существует, добавьте внутрь него
только нужные серверы, не создавая второй ключ `mcp_servers`.

После изменения конфигурации перезапустите Hermes и проверьте список tools.
Неиспользуемые MCP можно удалить из config или выставить им `enabled: false`.

## 4. Запустите интерфейс

Для работы только из терминала достаточно:

```bash
.venv/bin/hermes --tui
```

Для общения с Hermes через Telegram-бота или другую messaging-платформу
настройте отдельный Hermes Gateway:

```bash
.venv/bin/hermes gateway setup
.venv/bin/hermes gateway install
.venv/bin/hermes gateway start
.venv/bin/hermes gateway status
```

Gateway Telegram и Telegram userbot MCP — разные интеграции: gateway принимает
ваши сообщения боту, а userbot работает с диалогами обычного аккаунта.

## 5. Фоновые Telegram-задачи

На Linux с systemd user services после обеих Telegram-авторизаций:

```bash
make services
```

Будут запущены listener, conversation worker и dispatcher уведомлений. Worker
может автономно отвечать в прикреплённых к задаче чатах, поэтому сначала
проверьте конфигурацию вручную. На macOS эти процессы можно запускать командами
из [Telegram README](mcp/telegram/README.md) или оформить через свой supervisor.

## Проверка и обновление

Перед первым запуском и перед push:

```bash
make check
```

Проверка запускает линтеры, форматирование, unit- и интеграционные тесты, а
также поиск типичных секретов в текущих tracked-файлах и истории Git.

Обновление сервера:

```bash
git pull --ff-only
git submodule update --init --recursive
make setup
make check
.venv/bin/hermes gateway restart
```

## Если нужен только один MCP

Каждый локальный модуль самостоятелен. Например, для Obsidian:

```bash
cd mcp/obsidian
cp .env.example .env
uv sync --locked --no-editable
.venv/bin/obsidian-mcp
```

Аналогично запускаются `calendar-mcp`, `gmail-mcp`, `homeassistant-mcp` и
`telegram-mcp`.

## Структура

```text
deployment/    установка, генерация config и systemd user services
mcp/           независимые MCP-модули
scripts/       единая проверка проекта и secret scan
skills/        универсальные обезличенные Hermes skills
hermes/        закреплённый Git submodule Hermes Agent
```

Подробности серверного запуска находятся в
[deployment/README.md](deployment/README.md).

## История изменений

Текущая версия проекта — `v0.2.1`. Список изменений между релизами находится
в [CHANGELOG.md](CHANGELOG.md).

## Лицензия

[MIT](LICENSE)
