# Custom CalDAV provider

Use this account type for a standards-compatible CalDAV service. Set the
provider to `caldav` and specify its base `https://` URL. Plain HTTP and URLs
with embedded credentials are rejected.

After adding the account object, store its app password securely:

```bash
mcp/calendar/.venv/bin/calendar-store-password --account custom-work
```
