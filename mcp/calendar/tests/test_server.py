import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

SRC = Path(__file__).resolve().parents[1] / "src"
PROVIDER_EXAMPLES = Path(__file__).resolve().parents[1] / "providers"
sys.path.insert(0, str(SRC))

from calendar_mcp.config import (  # noqa: E402
    CALDAV_URLS,
    CalDavAccountSettings,
    GoogleAccountSettings,
    Settings,
)
from calendar_mcp.logic import BusyInterval, find_free_intervals  # noqa: E402
from calendar_mcp.models import CalendarInfo  # noqa: E402
from calendar_mcp.proposals import ProposalStore  # noqa: E402
from calendar_mcp.providers.google import GoogleCalendarService  # noqa: E402
from calendar_mcp.server import mcp  # noqa: E402
from calendar_mcp.service import CalendarService  # noqa: E402


class CalendarServerTests(unittest.TestCase):
    def test_public_tool_contract(self) -> None:
        self.assertEqual(
            set(mcp._tool_manager._tools),
            {
                "calendar_commit_event",
                "calendar_find_free_slots",
                "calendar_list_accounts",
                "calendar_list_calendars",
                "calendar_list_events",
                "calendar_prepare_event",
                "calendar_status",
            },
        )

    def test_multiple_provider_accounts_are_loaded_and_routed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_file = root / "accounts.json"
            config_file.write_text(
                json.dumps(
                    {
                        "default_account": "personal",
                        "timezone": "UTC",
                        "accounts": [
                            {
                                "id": "personal",
                                "provider": "google",
                                "label": "Personal",
                                "credentials_file": "google-client.json",
                                "token_file": "google-token.json",
                            },
                            {
                                "id": "work",
                                "provider": "yandex",
                                "label": "Work",
                                "username": "me@example.com",
                                "password_file": "work-password",
                                "allow_write": True,
                                "write_calendar_id": "calendar-1",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            settings = Settings.from_file(config_file)

        self.assertEqual(settings.default_account_id, "personal")
        self.assertIsInstance(settings.account(), GoogleAccountSettings)
        work = settings.account("work")
        self.assertIsInstance(work, CalDavAccountSettings)
        self.assertEqual(work.url, CALDAV_URLS["yandex"])
        self.assertTrue(work.write_enabled)

        work_client = MagicMock()
        work_client.list_calendars.return_value = [
            CalendarInfo("calendar-1", "Work", is_write_target=True)
        ]
        service = CalendarService(settings, clients={"work": work_client})
        account, calendars = service.list_calendars("work")

        self.assertEqual(account.account_id, "work")
        self.assertEqual(calendars[0].calendar_id, "calendar-1")
        work_client.list_calendars.assert_called_once_with()

    def test_checked_in_provider_examples_are_valid(self) -> None:
        expected_types = {
            "google": GoogleAccountSettings,
            "icloud": CalDavAccountSettings,
            "yandex": CalDavAccountSettings,
            "mailru": CalDavAccountSettings,
            "custom": CalDavAccountSettings,
        }
        for provider, expected_type in expected_types.items():
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as temporary:
                account = json.loads(
                    (PROVIDER_EXAMPLES / provider / "account.example.json").read_text(
                        encoding="utf-8"
                    )
                )
                config_file = Path(temporary) / "accounts.json"
                config_file.write_text(
                    json.dumps({"timezone": "UTC", "accounts": [account]}),
                    encoding="utf-8",
                )

                configured = Settings.from_file(config_file).account()

                self.assertIsInstance(configured, expected_type)
                self.assertEqual(configured.provider, account["provider"])
                if provider in CALDAV_URLS:
                    self.assertEqual(configured.url, CALDAV_URLS[provider])

    def test_google_adapter_maps_events_without_leaking_calendar_ids(self) -> None:
        account = GoogleAccountSettings(
            account_id="personal",
            label="Personal",
            credentials_file=Path("credentials.json"),
            token_file=Path("token.json"),
            timezone_name="UTC",
        )
        settings = self._settings(account)
        adapter = GoogleCalendarService(settings, account, service=MagicMock())
        provider_calendar_id = "me@example.com"
        info = adapter._calendar_info({"id": provider_calendar_id, "summary": "Personal"})
        event = adapter._event_record(
            {
                "id": "provider-event-id",
                "iCalUID": "ical-uid",
                "summary": "Planning",
                "start": {"dateTime": "2026-09-28T10:00:00+03:00"},
                "end": {"dateTime": "2026-09-28T11:00:00+03:00"},
                "status": "confirmed",
            },
            info,
            include_notes=False,
        )

        self.assertNotEqual(info.calendar_id, provider_calendar_id)
        self.assertEqual(len(info.calendar_id), 24)
        self.assertEqual(event.start, datetime.fromisoformat("2026-09-28T10:00:00+03:00"))
        self.assertEqual(event.calendar_id, info.calendar_id)

    def test_free_slots_handle_busy_intervals_across_multiple_days(self) -> None:
        slots = find_free_intervals(
            datetime(2026, 9, 29, 8, tzinfo=UTC),
            datetime(2026, 10, 1, 19, tzinfo=UTC),
            [
                BusyInterval(
                    datetime(2026, 9, 29, 10, tzinfo=UTC),
                    datetime(2026, 9, 29, 11, tzinfo=UTC),
                ),
                BusyInterval(
                    datetime(2026, 9, 30, 17, tzinfo=UTC),
                    datetime(2026, 10, 1, 10, tzinfo=UTC),
                ),
            ],
            timezone=ZoneInfo("UTC"),
            duration_minutes=60,
            working_hours_start="09:00",
            working_hours_end="18:00",
            weekdays_only=True,
            limit=10,
        )

        self.assertEqual(
            [(slot["start"], slot["end"]) for slot in slots],
            [
                ("2026-09-29T09:00:00+00:00", "2026-09-29T10:00:00+00:00"),
                ("2026-09-29T11:00:00+00:00", "2026-09-29T18:00:00+00:00"),
                ("2026-09-30T09:00:00+00:00", "2026-09-30T17:00:00+00:00"),
                ("2026-10-01T10:00:00+00:00", "2026-10-01T18:00:00+00:00"),
            ],
        )

    def test_existing_proposal_database_is_migrated_to_account_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "calendar.sqlite3"
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.executescript(
                    """
                    CREATE TABLE proposals (
                        proposal_id TEXT PRIMARY KEY,
                        uid TEXT NOT NULL UNIQUE,
                        calendar_id TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        expires_at INTEGER NOT NULL,
                        committed_at INTEGER,
                        receipt_json TEXT
                    );
                    CREATE TABLE write_audit (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at INTEGER NOT NULL,
                        action TEXT NOT NULL,
                        calendar_id TEXT NOT NULL,
                        uid_hash TEXT NOT NULL,
                        result TEXT NOT NULL
                    );
                    """
                )

            store = ProposalStore(database)
            proposal = store.create(
                account_id="work",
                calendar_id="calendar-1",
                uid="event-id",
                payload={"title": "Planning"},
                ttl_seconds=600,
            )

            self.assertEqual(proposal.account_id, "work")
            with closing(sqlite3.connect(database)) as connection:
                proposal_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(proposals)")
                }
                audit_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(write_audit)")
                }
            self.assertIn("account_id", proposal_columns)
            self.assertIn("account_id", audit_columns)

    @staticmethod
    def _settings(account: GoogleAccountSettings) -> Settings:
        return Settings(
            accounts=(account,),
            default_account_id=account.account_id,
            proposal_ttl_seconds=600,
            state_db=Path("calendar.sqlite3"),
            timeout_seconds=25,
            max_range_days=90,
            max_results=200,
        )


if __name__ == "__main__":
    unittest.main()
