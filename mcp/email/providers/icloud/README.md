# iCloud Mail

The `icloud` preset uses encrypted IMAP on port 993 and SMTP with STARTTLS on
port 587. Create an app-specific password in Apple Account settings.

After adding the account object, run:

```bash
mcp/email/.venv/bin/email-store-password --account icloud-personal
```

See [Apple's mail-server settings](https://support.apple.com/en-us/102525).
