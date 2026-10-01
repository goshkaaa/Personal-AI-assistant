import ast
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "calendar_mcp"
sys.path.insert(0, str(PACKAGE.parent))

from calendar_mcp.composition import CalendarContainer  # noqa: E402
from calendar_mcp.config import CalDavAccountSettings, Settings  # noqa: E402


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(f"{'.' * node.level}{node.module or ''}")
    return imports


class DependencyRuleTests(unittest.TestCase):
    def assert_layer_avoids(self, layer: str, forbidden: tuple[str, ...]) -> None:
        for path in (PACKAGE / layer).glob("*.py"):
            violations = sorted(
                module
                for module in imported_modules(path)
                if any(name in module for name in forbidden)
            )
            self.assertEqual(violations, [], f"{path.name} crosses a layer boundary")

    def test_application_does_not_depend_on_adapters(self):
        self.assert_layer_avoids("application", ("infrastructure", "presentation", "mcp"))

    def test_presentation_does_not_assemble_infrastructure(self):
        self.assert_layer_avoids("presentation", ("composition", "infrastructure"))


class CompositionTests(unittest.TestCase):
    def test_container_reuses_services_and_store(self):
        with tempfile.TemporaryDirectory() as temporary:
            account = CalDavAccountSettings(
                account_id="default",
                label="Test",
                username="test",
                password_file=Path("unused"),
                url="https://calendar.example/",
                timezone_name="UTC",
            )
            container = CalendarContainer()
            container.__dict__["settings"] = Settings(
                accounts=(account,),
                default_account_id="default",
                proposal_ttl_seconds=600,
                state_db=Path(temporary) / "calendar.sqlite3",
                timeout_seconds=25,
                max_range_days=90,
                max_results=200,
            )

            self.assertIs(container.account_service, container.account_service)
            self.assertIs(container.query_service, container.query_service)
            self.assertIs(container.query_service.accounts, container.account_service)


if __name__ == "__main__":
    unittest.main()
