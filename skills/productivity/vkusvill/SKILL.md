---
name: vkusvill
description: "ВкусВилл: рецепты и товары через MCP. Не web_search."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [vkusvill, shopping, recipes, grocery]
    related_skills: [shopping, expense-tracker]
---

# VKusVill — рецепты, товары, корзина

Работа с ВкусВиллом **только** через MCP-инструменты `mcp__vkusvill__*`. Не используй `web_search` для поиска товаров или рецептов — обращайся к MCP.

## Инструменты

| Задача | Инструмент |
|--------|------------|
| Поиск рецептов | `mcp__vkusvill__vkusvill_recipes` |
| Поиск товаров | `mcp__vkusvill__vkusvill_products_search` |
| Создание корзины | `mcp__vkusvill__vkusvill_cart_link_create` |
| Аналоги товара | `mcp__vkusvill__vkusvill_product_analogs` |
| Детали товара | `mcp__vkusvill__vkusvill_product_details` |
| По штрихкоду | `mcp__vkusvill__vkusvill_product_barcode` |
| Акции | `mcp__vkusvill__vkusvill_products_discount` |
| Магазины | `mcp__vkusvill__vkusvill_shops` |

## Процедура: подбор рецептов → корзина

1. **Поиск рецептов** — `vkusvill_recipes` с обязательными параметрами: `sort`, `page`, `q`, `id_category_filter`, `id_complexity_filter`, `id_cooking_method_filter`, `id_cooking_time_filter`, `id_feature_filter`, `id_exclude_allergens_filter` (массив, может быть пустым).
   - `id_cooking_time_filter`: 397967 = до 20 мин, 305736 = до 40 мин
   - `id_complexity_filter`: 393 = Легкий, 394 = Средний, 395 = Профи
   - `id_category_filter`: 2277 = На ужин, 2273 = На обед

2. **Извлечение ингредиентов** — из каждого рецепта беру `ingredients[].name` и `ingredients[].quantity`.

3. **Поиск товаров** — `vkusvill_products_search` по названию каждого ингредиента. Беру первый подходящий результат (id, name, price.current).

4. **Подсчёт стоимости** — суммирую цены всех найденных товаров, указываю примерную стоимость.

5. **Ожидание выбора** — после показа вариантов жду, какой рецепт выбрал пользователь.

6. **Сбор корзины** — `vkusvill_cart_link_create` с массивом товаров (id и quantity из рецепта).

## Важные правила

- **Всегда MCP, никогда web_search** — этот skill работает с ВкусВиллом только через MCP.
- **Стоимость — примерная** — цены в ответе MCP актуальны на момент запроса, но могут меняться. Указывай «примерно».
- **Один инструмент = один запрос** — не пытаться искать всё в одном вызове.
- **Нули в фильтрах** — все `id_*_filter` обязательны; передавай 0 для «без фильтра» и `[]` для `id_exclude_allergens_filter`.
- **Результат recipes приходит как `items`** — не `recipes`, не `results`. Ключ `data.items`.
- **Результат products_search — `data.items`** — массив с `id`, `name`, `price.current`, `unit`.
- **Товары на кг** — филе курицы и т.п. продаются за кг; для одной порции нужна доля (0.3-0.5 кг).
- **Скидки** — `price.old` и `price.discount_percent` показывают текущую скидку.

## Питфоллы

- Не забыть инициализировать все обязательные фильтры в `vkusvill_recipes` — пропущенный параметр = ошибка 422.
- Не перепутать `data.recipes` с `data.items` — рецепты приходят в `data.items`.
- Не собирать корзину без явного выбора пользователя.
- Не указывать точную цену как финальную — она меняется.
- **Двойной JSON в рецептах** — поле `result` возвращается как строка с экранированным JSON. Нужно парсить дважды: `json.loads(json.loads(raw)['result'])`.
- **Поле `cooking_time` — объект** — время готовки в `cooking_time.name` (строка), не в `cooking_time_minutes`. Для фильтрации используй `id_cooking_time_filter` (397967 = до 20 мин, 305736 = до 40 мин).
