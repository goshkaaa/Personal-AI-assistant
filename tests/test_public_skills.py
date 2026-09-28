from __future__ import annotations

import ipaddress
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "skills"

EXPECTED_SKILLS = {
    "appointments",
    "communication",
    "cronjob-management",
    "date-time-reasoning",
    "decision-support",
    "document-manager",
    "event-planner",
    "expense-tracker",
    "home-concierge",
    "personal-admin",
    "productivity/vkusvill",
    "project-manager",
    "research-compare",
    "shopping",
    "travel-concierge",
    "weekly-review",
}

PRIVATE_MARKERS = (
    "/home/",
    "/users/",
    ".ts.net",
    "cloud.nuxt.network",
)


class PublicSkillsTests(unittest.TestCase):
    def manifests(self) -> dict[str, Path]:
        return {
            str(path.parent.relative_to(SKILLS_ROOT)): path
            for path in SKILLS_ROOT.rglob("SKILL.md")
        }

    def test_expected_public_skill_set(self) -> None:
        self.assertEqual(set(self.manifests()), EXPECTED_SKILLS)

    def test_manifests_have_required_frontmatter(self) -> None:
        for relative, path in self.manifests().items():
            with self.subTest(skill=relative):
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---\n"))
                self.assertRegex(text, r"(?m)^name:\s*\S+")
                self.assertRegex(text, r"(?m)^description:\s*\S+")

    def test_skill_tree_has_no_private_markers(self) -> None:
        for path in SKILLS_ROOT.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8").lower()
            for marker in PRIVATE_MARKERS:
                with self.subTest(file=str(path.relative_to(ROOT)), marker=marker):
                    self.assertNotIn(marker, text)

    def test_skill_tree_has_no_embedded_email_addresses(self) -> None:
        email = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", re.I)
        for path in SKILLS_ROOT.rglob("*"):
            if path.is_file():
                self.assertIsNone(
                    email.search(path.read_text(encoding="utf-8")),
                    str(path.relative_to(ROOT)),
                )

    def test_skill_tree_has_no_ipv4_addresses(self) -> None:
        ipv4 = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
        for path in SKILLS_ROOT.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for candidate in ipv4.findall(text):
                with self.subTest(file=str(path.relative_to(ROOT)), value=candidate):
                    ipaddress.ip_address(candidate)
                    self.fail("IPv4 addresses are not allowed in public skills")


if __name__ == "__main__":
    unittest.main()
