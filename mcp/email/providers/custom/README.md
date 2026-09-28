# Custom IMAP/SMTP provider

Use this example when there is no named preset. Copy the account object and
replace the IMAP/SMTP hosts, ports, TLS modes, and mailbox names with values
from the provider's documentation.

Only `ssl` and `starttls` connections are accepted. Store the app password with:

```bash
mcp/email/.venv/bin/email-store-password --account custom-work
```
