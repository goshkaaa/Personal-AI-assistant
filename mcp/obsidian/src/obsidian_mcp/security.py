"""Input validation shared by Obsidian tools."""

import re

SECRET_MARKERS = (
    "api_key=",
    "api-key:",
    "api key:",
    "access_token=",
    "refresh_token=",
    "client_secret",
    "authorization: bearer",
    "bot_token=",
    "password=",
    "passwd=",
    "tg_api_hash=",
)
SECRET_PATTERNS = (
    r"\bsk-[A-Za-z0-9_-]{20,}\b",
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
    r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
    r"\bAIza[0-9A-Za-z_-]{30,}\b",
    r"\b[0-9]{8,12}:[A-Za-z0-9_-]{30,}\b",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
)


def safe_title(title: str) -> str:
    title = str(title).strip()
    if not title:
        raise ValueError("Title cannot be empty")
    title = re.sub(r'[\\/:*?"<>|]', "-", title)
    title = re.sub(r"\s+", " ", title).strip(" .")
    if not title:
        raise ValueError("Invalid title")
    return title[:150]


def reject_secrets(text: str) -> None:
    lowered = text.lower()
    if any(marker in lowered for marker in SECRET_MARKERS) or any(
        re.search(pattern, text) for pattern in SECRET_PATTERNS
    ):
        raise ValueError(
            "Content appears to contain a secret. Secrets must not be stored in Obsidian."
        )
