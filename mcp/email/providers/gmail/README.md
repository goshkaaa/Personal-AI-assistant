# Gmail

1. Enable the Gmail API and create an OAuth client of type **Desktop app**.
2. Save its JSON at `credentials_file`.
3. Add `account.example.json` to the private accounts file.
4. Run `mcp/email/.venv/bin/email-auth --account personal`.

Use a distinct `token_file` for every Gmail account. See the
[official Gmail API quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python).
