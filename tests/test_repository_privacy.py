from __future__ import annotations

import ipaddress
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EMAIL = re.compile(r"[a-z0-9._%+-]+@([a-z0-9.-]+\.[a-z]{2,})", re.I)
IPV4 = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
ABSOLUTE_HOME = re.compile(r"(?i)(?:/home|/users)/[a-z0-9._-]+")
TAILNET_HOST = re.compile(r"(?i)\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.ts\.net\b")
PROFILE_PATH = re.compile(r"\.hermes/profiles/([a-z0-9._<>-]+)", re.I)
PROFILE_UNIT = re.compile(r"hermes-gateway-(?!<profile>)[a-z0-9_-]+\.service", re.I)
SAFE_EMAIL_DOMAINS = {"example.com", "users.noreply.github.com"}


def repository_text_files() -> list[tuple[Path, str]]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        text=False,
    )
    files: list[tuple[Path, str]] = []
    for raw_path in output.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(raw_path.decode())
        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        files.append((relative, text))
    return files


class RepositoryPrivacyTests(unittest.TestCase):
    def test_no_personal_email_domains(self) -> None:
        for path, text in repository_text_files():
            for domain in EMAIL.findall(text):
                with self.subTest(file=str(path), domain=domain):
                    self.assertIn(domain.lower(), SAFE_EMAIL_DOMAINS)

    def test_no_public_ipv4_addresses(self) -> None:
        for path, text in repository_text_files():
            for candidate in IPV4.findall(text):
                address = ipaddress.ip_address(candidate)
                with self.subTest(file=str(path), value=candidate):
                    self.assertFalse(address.is_global)

    def test_no_absolute_user_homes_or_private_hosts(self) -> None:
        patterns = (ABSOLUTE_HOME, TAILNET_HOST, PROFILE_UNIT)
        for path, text in repository_text_files():
            for pattern in patterns:
                with self.subTest(file=str(path), pattern=pattern.pattern):
                    self.assertIsNone(pattern.search(text))
            for profile in PROFILE_PATH.findall(text):
                with self.subTest(file=str(path), profile=profile):
                    self.assertIn(profile, {"default", "<profile>"})


if __name__ == "__main__":
    unittest.main()
