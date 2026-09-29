import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from obsidian_mcp.config import ObsidianSettings  # noqa: E402
from obsidian_mcp.server import create_server  # noqa: E402
from obsidian_mcp.service import ObsidianVault  # noqa: E402


class ObsidianVaultTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        settings = ObsidianSettings(Path(self.temporary.name).resolve(), "hermes")
        self.vault = ObsidianVault(settings)

    def tearDown(self):
        self.temporary.cleanup()

    def test_create_does_not_overwrite_existing_note(self):
        created = self.vault.create("Roadmap", "first")
        repeated = self.vault.create("Roadmap", "second")
        content = (self.vault.path / "Roadmap.md").read_text(encoding="utf-8")

        self.assertTrue(created["created"])
        self.assertTrue(repeated["exists"])
        self.assertIn("first", content)
        self.assertNotIn("second", content)

    def test_concurrent_create_has_one_winner(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda value: self.vault.create("Race", value), range(8)))

        self.assertEqual(sum(result["created"] for result in results), 1)
        self.assertEqual((self.vault.path / "Race.md").stat().st_mode & 0o777, 0o600)

    def test_title_is_confined_to_vault(self):
        self.assertEqual(self.vault.note_path("../../outside").parent, self.vault.path)

    def test_common_secret_content_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "secret"):
            self.vault.create("Unsafe", "access_token=synthetic")

    def test_high_confidence_token_shape_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "secret"):
            self.vault.create("Unsafe", "sk-" + "x" * 24)

    def test_public_tool_contract(self):
        server = create_server()
        self.assertEqual(
            set(server._tool_manager._tools),
            {
                "obsidian_create_note",
                "obsidian_get_note",
                "obsidian_list_notes",
                "obsidian_send_note",
                "obsidian_update_note",
            },
        )


if __name__ == "__main__":
    unittest.main()
