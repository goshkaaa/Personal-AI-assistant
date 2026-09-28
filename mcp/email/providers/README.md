# Provider examples

Each directory contains one account object. Copy the object into the `accounts`
array in your private `email-accounts.json` and replace placeholder values.

- `gmail`: Gmail API with OAuth; no mailbox password.
- `yandex`: Yandex Mail over IMAP/SMTP with an app password.
- `mailru`: Mail.ru over IMAP/SMTP with an app password.
- `icloud`: iCloud Mail over IMAP/SMTP with an app-specific password.
- `custom`: any other provider with explicit encrypted IMAP/SMTP settings.

The Yandex, Mail.ru, and iCloud provider names select reviewed server, port, and
TLS defaults from `email_mcp.providers.presets`. Any value can still be
overridden with explicit `imap` or `smtp` fields in the account object.
