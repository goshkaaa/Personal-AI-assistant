# iCloud Calendar

The `icloud` preset connects to `https://caldav.icloud.com/`. Create an Apple
app-specific password; do not use the primary Apple Account password.

After adding the account object, store the password securely:

```bash
mcp/calendar/.venv/bin/calendar-store-password --account personal-icloud
```

See [Apple's app-specific password documentation](https://support.apple.com/102654).
