# Mail.ru

The `mailru` preset uses encrypted IMAP and SMTP on port 993 and 465. Create a
password for an external application in Mail.ru security settings.

After adding the account object, run:

```bash
mcp/email/.venv/bin/email-store-password --account mailru-personal
```

See [Mail.ru's mail-client documentation](https://help.mail.ru/mail/mailer/popsmtp/).
