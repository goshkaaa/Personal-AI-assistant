---
name: expense-tracker
description: Load for expenses, spending, budgets, or purchase logs.
---

# Expense Tracker

Use for recording and analyzing personal spending.

Extract when available:
- amount;
- currency;
- category;
- date;
- merchant or description;
- optional context.

Preserve the exact amount and currency.

Do not invent missing values.

For short entries such as "839 carsharing", infer only what is obvious and record it without unnecessary questions.

When the user asks for analysis, aggregate by useful dimensions such as:
- category;
- day;
- week;
- month;
- recurring spending.

Distinguish actual recorded expenses from estimates or planned spending.

Avoid duplicate entries.
