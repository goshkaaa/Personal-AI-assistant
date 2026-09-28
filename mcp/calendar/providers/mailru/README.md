# Mail Calendar

The `mailru` preset connects to `https://calendar.mail.ru/`. Use the complete
mailbox address as the username and create a password for an external app.

After adding the account object, store the password securely:

```bash
mcp/calendar/.venv/bin/calendar-store-password --account personal-mailru
```

See [Mail's official CalDAV synchronization settings](https://help.mail.ru/calendar-help/synchronization/about/).
