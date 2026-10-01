import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from telegram_mcp import listener  # noqa: E402


class ListenerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.message = SimpleNamespace(
            chat=SimpleNamespace(id=42),
            id=100,
            outgoing=False,
            text="hello",
            caption=None,
        )

    @patch("telegram_mcp.listener.task_repository.queue_incoming")
    @patch("telegram_mcp.listener.log_message")
    @patch("telegram_mcp.listener.conversations.is_managed")
    def test_ignores_unmanaged_chat(self, is_managed, log_message, queue_incoming) -> None:
        is_managed.return_value = False

        listener.incoming_message(None, self.message)

        log_message.assert_not_called()
        queue_incoming.assert_not_called()

    @patch("telegram_mcp.listener.task_repository.queue_incoming")
    @patch("telegram_mcp.listener.log_message")
    @patch("telegram_mcp.listener.conversations.is_managed")
    def test_logs_outgoing_message_without_queueing(
        self, is_managed, log_message, queue_incoming
    ) -> None:
        is_managed.return_value = True
        self.message.outgoing = True

        listener.incoming_message(None, self.message)

        log_message.assert_called_once_with(self.message)
        queue_incoming.assert_not_called()

    @patch("telegram_mcp.listener.task_repository.queue_incoming")
    @patch("telegram_mcp.listener.log_message")
    @patch("telegram_mcp.listener.conversations.is_managed")
    def test_logs_and_queues_incoming_message(
        self, is_managed, log_message, queue_incoming
    ) -> None:
        is_managed.return_value = True
        queue_incoming.return_value = True

        listener.incoming_message(None, self.message)

        log_message.assert_called_once_with(self.message)
        queue_incoming.assert_called_once_with(
            chat_id=42,
            message_id=100,
            text="hello",
        )


if __name__ == "__main__":
    unittest.main()
