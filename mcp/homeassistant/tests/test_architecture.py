import ast
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "homeassistant_mcp"
sys.path.insert(0, str(PACKAGE.parent))

from homeassistant_mcp.composition import HomeAssistantContainer  # noqa: E402
from homeassistant_mcp.config import HomeAssistantSettings  # noqa: E402


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            imports.add(f"{prefix}{node.module or ''}")
    return imports


class DependencyRuleTests(unittest.TestCase):
    def assert_layer_avoids(self, layer: str, forbidden: tuple[str, ...]) -> None:
        for path in (PACKAGE / layer).glob("*.py"):
            imports = imported_modules(path)
            violations = sorted(
                module for module in imports if any(name in module for name in forbidden)
            )
            self.assertEqual(violations, [], f"{path.name} crosses a layer boundary")

    def test_domain_has_no_outward_dependencies(self):
        self.assert_layer_avoids(
            "domain",
            ("application", "infrastructure", "presentation", "mcp"),
        )

    def test_application_does_not_depend_on_adapters(self):
        self.assert_layer_avoids(
            "application",
            ("infrastructure", "presentation", "mcp"),
        )

    def test_presentation_does_not_assemble_infrastructure(self):
        self.assert_layer_avoids(
            "presentation",
            ("composition", "infrastructure"),
        )


class CompositionTests(unittest.TestCase):
    def test_process_container_reuses_gateway_and_read_service(self):
        container = HomeAssistantContainer()
        container.__dict__["settings"] = HomeAssistantSettings(
            url="http://homeassistant.test",
            token_file=Path("unused"),
            token_from_environment="synthetic-token",
            allow_write=False,
            timeout_seconds=15,
        )

        self.assertIs(container.gateway, container.gateway)
        self.assertIs(container.read_service, container.read_service)
        self.assertIs(container.read_service.gateway, container.gateway)


if __name__ == "__main__":
    unittest.main()
