# Google Calendar

1. Enable the Google Calendar API and create an OAuth client of type **Desktop app**.
2. Save its downloaded JSON at `credentials_file`.
3. Add `account.example.json` to the private accounts file.
4. Run `mcp/calendar/.venv/bin/calendar-auth --account personal-google` and open
   the printed URL in a browser.

Use a distinct `token_file` for every Google account. See the
[official Google Calendar API quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python).
