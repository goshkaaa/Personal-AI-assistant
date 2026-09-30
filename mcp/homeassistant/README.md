# Home Assistant MCP

Чтение любых entities, device/entity/area registry, история, вызов
разрешённых Home Assistant services и опциональная краткосрочная история
геопозиции.

```bash
cp .env.example .env
uv sync --locked --no-editable
.venv/bin/homeassistant-mcp
```

Укажите URL и private token file в `.env`. Вызов services по умолчанию выключен.
Токен читает только MCP-сервер: он не попадает в tool arguments или ответы.

## Universal read-only tools

- `find_entities(query, domain, limit)` — поиск по entity ID, friendly name,
  aliases, device и area; понимает типовые русские и английские запросы.
- `get_entity_state(entity_id)` — текущие state, attributes, device и area.
- `get_device(device_id, name)` — устройство и все связанные entities.
- `get_person_location(person_id)` — zone/state, координаты, точность,
  время обновления, ссылка на карту и адрес от настроенного внутри MCP
  reverse geocoder. Техническое состояние HA `not_home` означает только выход
  за пределы настроенной в HA домашней зоны и не описывает место жительства.
- `get_entity_history(entity_id, start, end, hours, limit)` — история из HA за
  ограниченный период.
- `list_entities(domain, area, device, state, limit)` — фильтр по registry и состоянию;
  `state="unavailable,unknown"` находит недоступные entities.

У этих tools в MCP annotations указан `readOnlyHint=true`. Write-tools
`ha_call_service`, `ha_turn_on`, `ha_turn_off`, `ha_toggle` отделены и не меняют
существующую политику approvals.

Reverse geocoding включается только явно через
`HOME_ASSISTANT_REVERSE_GEOCODING_URL`. MCP отправляет геокодеру только
координаты и никогда не добавляет к запросу Home Assistant token. Для публичного
Nominatim учитывайте его usage policy и укажите пользователям атрибуцию OpenStreetMap.

## История геопозиции

Добавьте разрешённые HA entities в `.env`:

```dotenv
HOME_ASSISTANT_LOCATION_ENTITIES=person.example
HOME_ASSISTANT_LOCATION_INTERVAL_SECONDS=600
HOME_ASSISTANT_LOCATION_RETENTION_HOURS=72
```

Фоновый процес `homeassistant-location-recorder` сохраняет точки в приватную SQLite-базу
и удаляет записи старше заданного срока. MCP tools `ha_get_location`,
`ha_record_location` и `ha_get_location_history` дают боту текущую точку, ссылку на
карту и маршрут за выбранный период.
