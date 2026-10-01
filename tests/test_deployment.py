import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from deployment import preflight
from deployment.install_user_services import unit

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "deployment" / "generate_config.py"
PREFLIGHT = ROOT / "deployment" / "preflight.py"
LOCAL_SERVICES = ("calendar", "email", "homeassistant", "obsidian", "telegram")


class DeploymentIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.output = Path(self.temporary.name) / "hermes-mcp.yaml"
        self.private_marker = "integration-secret-value"
        environment = os.environ.copy()
        environment["MCP_CONFIG_OUTPUT"] = str(self.output)
        environment["TG_API_HASH"] = self.private_marker
        subprocess.run(
            [sys.executable, str(GENERATOR)],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        self.config = self.output.read_text(encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_generated_config_points_to_installed_servers_and_env_files(self) -> None:
        for service in LOCAL_SERVICES:
            command_name = f"{service}-mcp"
            command = ROOT / "mcp" / service / ".venv" / "bin" / command_name
            env_file = ROOT / "mcp" / service / ".env"
            self.assertIn(str(command), self.config)
            self.assertIn(str(env_file), self.config)

        self.assertEqual(self.config.count("MCP_ENV_FILE:"), len(LOCAL_SERVICES))
        self.assertIn("https://mcp.vkusvill.ru/mcp", self.config)

    def test_generated_config_is_private_and_contains_no_env_values(self) -> None:
        self.assertNotIn(self.private_marker, self.config)
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o600)

    def test_systemd_paths_are_absolute_without_literal_quotes(self) -> None:
        rendered = unit("telegram-listener")
        working_directory = ROOT / "mcp" / "telegram"
        executable = working_directory / ".venv" / "bin" / "telegram-listener"

        self.assertIn(f"WorkingDirectory={working_directory}\n", rendered)
        self.assertIn(f"ExecStart={executable}\n", rendered)

    def test_preflight_accepts_a_source_release_candidate(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PREFLIGHT), "--allow-dirty", "--source-only"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("No files were published or deployed", result.stdout)

    def test_source_preflight_accepts_an_uninitialized_hermes_submodule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(preflight, "HERMES_DIR", Path(tmp)):
                errors, warnings = preflight.collect_errors(
                    allow_dirty=True,
                    source_only=True,
                )

        self.assertNotIn("Hermes submodule is not initialized", errors)
        self.assertTrue(
            any("Hermes submodule is not initialized" in warning for warning in warnings)
        )


if __name__ == "__main__":
    unittest.main()
