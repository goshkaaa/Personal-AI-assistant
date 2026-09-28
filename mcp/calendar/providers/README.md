# Calendar provider examples

Each directory contains one account object. Copy the object into the `accounts`
array in your private `calendar-accounts.json` and replace placeholder values.

- `google`: Google Calendar API with OAuth; no account password.
- `icloud`: iCloud Calendar over CalDAV with an app-specific password.
- `yandex`: Yandex Calendar over CalDAV with an app password.
- `mailru`: Mail Calendar over CalDAV with an external-app password.
- `custom`: any standards-compatible CalDAV server over HTTPS.

The `icloud`, `yandex`, and `mailru` names select reviewed CalDAV endpoints. Use
`caldav` for another provider and set its HTTPS URL explicitly.
