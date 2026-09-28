# Email MCP

Один MCP-сервер для нескольких почтовых ящиков. Gmail работает через OAuth и
Gmail API. Yandex, Mail.ru, iCloud и другие совместимые сервисы — через
защищённые IMAP/SMTP-соединения.

## Структура

```text
mcp/email/
├── providers/                  # готовые примеры настроек
│   ├── gmail/
│   ├── yandex/
│   ├── mailru/
│   ├── icloud/
│   └── custom/               # любой другой IMAP/SMTP-сервер
├── src/email_mcp/providers/   # адаптеры Gmail API и IMAP/SMTP
├── accounts.example.json      # полный мультиаккаунтный пример
└── .env.example
```

Папки в `providers/` не содержат пароли. В каждой лежит безопасный JSON-пример,
который можно добавить в массив `accounts`.

## Быстрый старт

### 1. Установите модуль

Из корня репозитория:

```bash
make setup
```

Или только почтовый модуль:

```bash
uv sync --project mcp/email --locked --extra dev --no-editable
cp mcp/email/.env.example mcp/email/.env
```

### 2. Создайте accounts-конфиг

```bash
mkdir -p ~/.config/personal-ai-assistant/secrets
cp mcp/email/accounts.example.json \
  ~/.config/personal-ai-assistant/secrets/email-accounts.json
chmod 700 ~/.config/personal-ai-assistant/secrets
chmod 600 ~/.config/personal-ai-assistant/secrets/email-accounts.json
```

Путь к файлу задаётся в `mcp/email/.env`:

```dotenv
EMAIL_ACCOUNTS_FILE=~/.config/personal-ai-assistant/secrets/email-accounts.json
```

В `email-accounts.json`:

- `id` — короткое уникальное имя ящика;
- `default_account` — ящик, который используется без явного `account_id`;
- `allow_send` — разрешение на реальную отправку из конкретного ящика.

Можно добавить любое число ящиков, включая несколько аккаунтов одного
провайдера. У них должны отличаться `id`, `token_file` или `password_file`.

### 3. Подключите ящики

Gmail — отдельный OAuth-запуск для каждого аккаунта:

```bash
mcp/email/.venv/bin/email-auth --account personal
```

Yandex, Mail.ru, iCloud и другие IMAP/SMTP-ящики — app-specific password, который
вводится без отображения и сохраняется с правами `0600`:

```bash
mcp/email/.venv/bin/email-store-password --account work
```

Не используйте основной пароль от аккаунта. Для IMAP/SMTP нужен отдельный
пароль приложения, созданный в настройках провайдера.

### 4. Проверьте конфигурацию

```bash
mcp/email/.venv/bin/email-config-check
make config
make check
```

`email-config-check` проверяет JSON и показывает аккаунты без вывода секретов.
`make config` создаёт MCP-блок для Hermes, а `make check` прогоняет все проверки.
Сам `email-mcp` — stdio-сервер; его запускает Hermes.

## Выбор аккаунта

`email_list_accounts` возвращает все настроенные ящики. В остальные email-инструменты
передавайте `account_id`. Если его нет, сервер берёт `default_account`.

Каждый результат содержит `account_id` и `provider`, поэтому ID письма не потеряется
между несколькими ящиками.

## Отправка писем

Чтение и черновики доступны после подключения. Для реальной отправки нужны оба
условия:

1. у аккаунта установлено `"allow_send": true`;
2. в конкретном `email_send` или `email_reply` передано `user_confirmed=true`.

## Другой IMAP/SMTP-провайдер

Используйте `"provider": "imap_smtp"` и явно задайте `imap.host`, `smtp.host`, порты и
`security`. Допустимы только `ssl` и `starttls`; незащищённые соединения не
поддерживаются.

Имена IMAP-папок зависят от провайдера. При необходимости переопределите
`imap.inbox`, `imap.drafts` и `imap.sent` в accounts-конфиге.

## Ограничения

- IMAP не задаёт универсальную модель тредов. Для IMAP-ящика `email_get_thread` возвращает выбранное письмо.
- `query` для IMAP ищет по тексту письма. Gmail-адаптер понимает Gmail search syntax.
- Провайдеры, которые запрещают app-password и разрешают только собственный OAuth API, требуют отдельного адаптера.
