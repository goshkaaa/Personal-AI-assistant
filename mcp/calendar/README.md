# Calendar MCP

Один MCP-сервер для нескольких календарных аккаунтов. Google Calendar работает
через официальный API и OAuth. iCloud, Yandex, Mail.ru и другие совместимые сервисы —
через CalDAV по HTTPS.

## Структура

```text
mcp/calendar/
├── providers/                    # готовые примеры аккаунтов
│   ├── google/
│   ├── icloud/
│   ├── yandex/
│   ├── mailru/
│   └── custom/                   # любой HTTPS CalDAV-сервер
├── src/calendar_mcp/providers/   # адаптеры Google API и CalDAV
├── accounts.example.json         # полный мультиаккаунтный пример
└── .env.example
```

Файлы в `providers/` не содержат секретов. Каждый `account.example.json` — это
один объект для массива `accounts` в приватном конфиге.

## Быстрый старт

### 1. Установите модуль

Из корня репозитория:

```bash
make setup
```

Или только календарный модуль:

```bash
uv sync --project mcp/calendar --locked --extra dev --no-editable
cp mcp/calendar/.env.example mcp/calendar/.env
```

### 2. Создайте accounts-конфиг

```bash
mkdir -p ~/.config/personal-ai-assistant/secrets
cp mcp/calendar/accounts.example.json \
  ~/.config/personal-ai-assistant/secrets/calendar-accounts.json
chmod 700 ~/.config/personal-ai-assistant/secrets
chmod 600 ~/.config/personal-ai-assistant/secrets/calendar-accounts.json
```

Оставьте в `accounts` только нужные примеры и замените значения-заглушки. Путь
к конфигу задаётся в `mcp/calendar/.env`:

```dotenv
CALENDAR_ACCOUNTS_FILE=~/.config/personal-ai-assistant/secrets/calendar-accounts.json
```

Основные поля:

- `id` — короткий уникальный идентификатор аккаунта;
- `default_account` — аккаунт, используемый без явного `account_id`;
- `timezone` — часовой пояс аккаунта или общий часовой пояс верхнего уровня;
- `allow_write` — локальное разрешение на создание и удаление событий в этом аккаунте;
- `write_calendar_id` — единственный календарь, который разрешено изменять.

Можно подключить сколько угодно аккаунтов, в том числе несколько аккаунтов
одного провайдера. Для каждого Google-аккаунта нужен отдельный `token_file`, а
для каждого CalDAV-аккаунта — отдельный `password_file`.

### 3. Подключите аккаунты

Для Google создайте Desktop OAuth client, сохраните JSON по пути
`credentials_file`, установите файлу права `0600` и выполните авторизацию для
каждого аккаунта:

```bash
mcp/calendar/.venv/bin/calendar-auth --account personal-google
```

Команда напечатает URL. Откройте его в браузере и подтвердите доступ.

Для iCloud, Yandex, Mail.ru и другого CalDAV создайте пароль приложения и сохраните его
без отображения в терминале:

```bash
mcp/calendar/.venv/bin/calendar-store-password --account personal-icloud
mcp/calendar/.venv/bin/calendar-store-password --account work-yandex
```

Не используйте основной пароль аккаунта.

### 4. Проверьте конфигурацию

```bash
mcp/calendar/.venv/bin/calendar-config-check
make config
make check
```

`calendar-config-check` проверяет JSON и показывает только несекретные сведения.
Сам `calendar-mcp` — stdio-сервер; его запускает Hermes.

## Выбор аккаунта

`calendar_list_accounts` возвращает настроенные аккаунты. В остальные
calendar-инструменты передавайте `account_id`. Если его нет, сервер использует
`default_account`.

Каждый ответ с данными календаря содержит `account_id` и `provider`. Идентификаторы
календарей непрозрачны и не раскрывают адреса провайдера.

## Безопасное включение записи

Запись настраивается отдельно для каждого аккаунта:

1. Оставьте `allow_write: false` и `write_calendar_id: ""`.
2. Вызовите `calendar_list_calendars` с нужным `account_id`.
3. Скопируйте непрозрачный `calendar_id` выбранного календаря в
   `write_calendar_id` этого аккаунта.
4. Ещё раз проверьте чтение и только затем установите `allow_write: true`.

Создание события всё равно выполняется в два шага:

1. `calendar_prepare_event` проверяет пересечения и создаёт короткоживущее
   неизменяемое предложение без внешней записи.
2. `calendar_commit_event` запрашивает интерактивное подтверждение и выполняет
   идемпотентную запись ровно в настроенный календарь.

Удаление также выполняется в два шага:

1. Сначала получите `event_id` через `calendar_list_events`, затем вызовите
   `calendar_prepare_delete_event` с тем же аккаунтом, календарём и ограниченным
   диапазоном дат. На этом этапе внешних изменений нет.
2. `calendar_commit_delete_event` ещё раз проверяет write-настройки, показывает
   точное событие и удаляет его только после интерактивного подтверждения.

Повторный вызов commit безопасен и не удалит другое событие. Удаление повторяющихся
событий пока отклоняется, потому что CalDAV-провайдеры не всегда позволяют надёжно
отличить один экземпляр от всей серии. Изменение событий, участников и правил
повторения не поддерживается.

## Поддерживаемые провайдеры

- Google Calendar — нативный API и OAuth;
- iCloud Calendar — преднастроенный CalDAV;
- Yandex Calendar — преднастроенный CalDAV;
- Mail Calendar — преднастроенный CalDAV;
- любой совместимый CalDAV-сервер — `provider: "caldav"` и явный HTTPS URL.

Сервисы без Google Calendar API и без CalDAV (например, Microsoft 365) требуют
отдельного адаптера и OAuth-потока; текущая конфигурация намеренно не маскирует
их под CalDAV.

## Совместимость со старой конфигурацией

Если `CALENDAR_ACCOUNTS_FILE` не задан, продолжают работать прежние переменные
`ICLOUD_USERNAME`, `ICLOUD_APP_PASSWORD_FILE`, `CALENDAR_TIMEZONE`,
`CALENDAR_WRITE_CALENDAR_ID` и `MCP_ALLOW_CALENDAR_WRITE`. Для новых установок
используйте accounts-конфиг.
