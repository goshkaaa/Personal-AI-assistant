# Yandex Mail

The `yandex` preset uses encrypted IMAP on port 993 and encrypted SMTP on port
465. Enable access by mail clients in Yandex settings and create an app password.

After adding the account object, run:

```bash
mcp/email/.venv/bin/email-store-password --account yandex-personal
```

See [Yandex's mail-client documentation](https://yandex.com/support/yandex-360/customers/mail/en/mail-clients/others.html).
