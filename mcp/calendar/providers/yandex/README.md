# Yandex Calendar

The `yandex` preset connects to `https://caldav.yandex.ru/`. Create an app
password for Calendar in Yandex ID.

After adding the account object, store the password securely:

```bash
mcp/calendar/.venv/bin/calendar-store-password --account work-yandex
```

See [Yandex's CalDAV synchronization documentation](https://yandex.com/support/yandex-360/customers/calendar/web/en/sync/sync-desktop).
