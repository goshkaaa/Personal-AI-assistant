# ЮKassa MCP

Официальный удалённый MCP ЮKassa подключается к Hermes напрямую по Streamable HTTP:

```text
https://mcp.yookassa.ru
```

Локальный сервер, отдельное Python-окружение и ключи обычного API не нужны.
Для авторизации используется отдельный MCP-токен магазина.

## Подключение

1. Выпустите MCP-токен в личном кабинете ЮKassa: **Интеграция → Доступы к магазину**.
2. Сохраните `YOOKASSA_MCP_TOKEN=<токен>` в приватном `.env` нужного профиля Hermes
   (`~/.hermes/.env` или `~/.hermes/profiles/<profile>/.env`) с правами `0600`.
   Hermes сам загружает этот файл и подставляет переменную в HTTP-заголовок.
3. Выполните `make config` и перенесите entry `yookassa` из `.local/hermes-mcp.yaml`
   в существующий `mcp_servers` этого профиля. После настройки токена включите
   `enabled: true`. Генератор оставляет ЮKassa выключенной до настройки секрета.

```yaml
mcp_servers:
  yookassa:
    url: "https://mcp.yookassa.ru"
    headers:
      Authorization: "Bearer ${YOOKASSA_MCP_TOKEN}"
    enabled: true
    trust: untrusted
    connect_timeout: 30
```

Откройте новую сессию Hermes или перезапустите gateway нужного профиля.
Попросите ассистента показать инструменты ЮKassa, затем список платежей за нужный
период. Это проверяет подключение без создания платежа.

Не помещайте фактическое значение токена в `mcp.yaml`, generated config, skills
или Git. Токен привязан к магазину; для перехода с тестового магазина на настоящий
замените токен в приватном `.env` и перезапустите соответствующий Hermes.

## Возможности

| Инструмент | Действие |
| --- | --- |
| `create_payment` | Создать одностадийный платёж и получить ссылку на оплату |
| `get_payment` | Проверить платёж по ID |
| `get_payments` | Получить список платежей с фильтрами |
| `create_invoice` | Выставить счёт |
| `get_invoice` | Проверить счёт по ID |
| `get_refund` | Проверить возврат по ID |
| `get_refunds` | Получить список возвратов с фильтрами |

Имена в таблице проверены через `tools/list`; в документации ЮKassa списки
называются `get_payments_list` и `get_refunds_list`. При вызове используются
фактические имена и схемы, которые Hermes получает от сервера через `tools/list`.
В тестовом магазине счета недоступны. MCP не создаёт возвраты и не передаёт
данные для фискальных чеков. Сумма и валюта должны быть указаны пользователем
или взяты из проверенного источника; создание платежа само по себе не означает
успешную оплату — её проверяют через `get_payment`.

Интеграция использует `trust: untrusted`: Hermes применяет свою approval policy
к инструментам записи и инструментам без `readOnlyHint: true`. Оплата проходит
на странице ЮKassa по ссылке, которую возвращает MCP.

Если магазин использует субаккаунты, добавьте заголовок `Mcp-Param-Gateway-Id`
с идентификатором, выданным ЮKassa. Для обычного магазина он не нужен.

Официальные источники: [подключение и токены](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mcp-server/configuration),
[справочник инструментов](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mcp-server/tools),
[сценарии использования](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mcp-server/scenarios).
