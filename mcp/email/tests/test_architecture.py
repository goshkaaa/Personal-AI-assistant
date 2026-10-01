import ast
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "email_mcp"


def _import_paths(source: Path) -> set[str]:
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            imports.add(prefix + (node.module or ""))
    return imports


class EmailArchitectureTests(unittest.TestCase):
    def test_domain_has_no_outward_or_provider_dependencies(self) -> None:
        self._assert_layer_excludes(
            "domain",
            {"application", "infrastructure", "presentation", "providers", "mcp"},
        )

    def test_application_depends_only_on_domain_and_configuration(self) -> None:
        self._assert_layer_excludes(
            "application",
            {"infrastructure", "presentation", "providers", "mcp"},
        )

    def test_infrastructure_does_not_depend_on_application_or_presentation(self) -> None:
        self._assert_layer_excludes("infrastructure", {"application", "presentation", "mcp"})

    def test_presentation_does_not_construct_provider_adapters(self) -> None:
        self._assert_layer_excludes(
            "presentation",
            {"infrastructure", "providers", "composition", "config"},
        )

    def _assert_layer_excludes(self, layer: str, forbidden: set[str]) -> None:
        files = (PACKAGE / layer).glob("*.py")
        for source in files:
            with self.subTest(layer=layer, source=source.name):
                for imported in _import_paths(source):
                    segments = set(imported.lstrip(".").split("."))
                    self.assertFalse(segments & forbidden, f"{source.name} imports {imported}")


if __name__ == "__main__":
    unittest.main()
