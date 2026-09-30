#!/usr/bin/env python3
"""Fail closed when a checkout is not ready for a private deployment."""

from __future__ import annotations

import argparse
import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERMES_DIR = ROOT / "hermes" / "hermes-agent"
GENERATED_CONFIG = ROOT / ".local" / "hermes-mcp.yaml"
SERVICES = {
    "calendar": "calendar-mcp",
    "email": "email-mcp",
    "homeassistant": "homeassistant-mcp",
    "obsidian": "obsidian-mcp",
    "telegram": "telegram-mcp",
}


def run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def private_mode(path: Path) -> bool:
    if os.name == "nt":
        return True
    return stat.S_IMODE(path.stat().st_mode) & 0o077 == 0


def gitlink_revision() -> str:
    result = run("git", "ls-files", "--stage", "hermes/hermes-agent")
    fields = result.stdout.strip().split()
    return fields[1] if result.returncode == 0 and len(fields) >= 2 else ""


def collect_errors(
    *, allow_dirty: bool, source_only: bool
) -> tuple[list[str], list[str]]:
    errors = []
    warnings = []

    for command in (("git", "diff", "--check"), ("git", "diff", "--cached", "--check")):
        whitespace = run(*command)
        if whitespace.returncode != 0:
            errors.append(" ".join(command) + " failed")

    status = run("git", "status", "--porcelain", "--untracked-files=all")
    if status.returncode != 0:
        errors.append("could not inspect Git worktree status")
    elif status.stdout.strip():
        message = "Git worktree contains uncommitted tracked or untracked files"
        if allow_dirty:
            warnings.append(message)
        else:
            errors.append(message)

    if not source_only and not (ROOT / ".venv" / "bin" / "hermes").is_file():
        errors.append("Hermes is not installed; run make setup")

    expected_revision = gitlink_revision()
    actual_revision = run("git", "rev-parse", "HEAD", cwd=HERMES_DIR)
    if not expected_revision or actual_revision.returncode != 0:
        errors.append("Hermes submodule is not initialized")
    elif actual_revision.stdout.strip() != expected_revision:
        errors.append("Hermes submodule revision does not match the repository gitlink")

    for service, entrypoint in SERVICES.items():
        directory = ROOT / "mcp" / service
        for required in ("pyproject.toml", "uv.lock", ".env.example"):
            if not (directory / required).is_file():
                errors.append(f"mcp/{service}/{required} is missing")
        if not source_only:
            executable = directory / ".venv" / "bin" / entrypoint
            if not executable.is_file() or not os.access(executable, os.X_OK):
                errors.append(f"mcp/{service} is not installed; run make setup")

        env_file = directory / ".env"
        if env_file.exists() and not private_mode(env_file):
            errors.append(
                f"mcp/{service}/.env must not be accessible by group or others"
            )

        ignored = run(
            "git",
            "check-ignore",
            "--no-index",
            str(env_file.relative_to(ROOT)),
        )
        if ignored.returncode != 0:
            errors.append(f"mcp/{service}/.env is not protected by .gitignore")

    if not source_only:
        if not GENERATED_CONFIG.is_file():
            errors.append(".local/hermes-mcp.yaml is missing; run make config")
        elif not private_mode(GENERATED_CONFIG):
            errors.append(
                ".local/hermes-mcp.yaml must not be accessible by group or others"
            )
        generated_ignored = run(
            "git",
            "check-ignore",
            "--no-index",
            str(GENERATED_CONFIG.relative_to(ROOT)),
        )
        if generated_ignored.returncode != 0:
            errors.append(".local/hermes-mcp.yaml is not protected by .gitignore")

    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow uncommitted source changes while validating a release candidate",
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="validate source without requiring installed runtime environments",
    )
    args = parser.parse_args()
    errors, warnings = collect_errors(
        allow_dirty=args.allow_dirty,
        source_only=args.source_only,
    )

    for warning in warnings:
        print(f"warning: {warning}")
    if errors:
        for error in errors:
            print(f"error: {error}")
        raise SystemExit(1)

    print("Deployment preflight passed. No files were published or deployed.")


if __name__ == "__main__":
    main()
