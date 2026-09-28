#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for service in calendar gmail homeassistant obsidian telegram; do
  service_dir="$ROOT_DIR/mcp/$service"
  ruff="$service_dir/.venv/bin/ruff"
  python="$service_dir/.venv/bin/python"

  if [[ ! -x "$ruff" || ! -x "$python" ]]; then
    printf 'error: mcp/%s is not installed; run make setup first\n' "$service" >&2
    exit 1
  fi

  printf '==> Checking mcp/%s\n' "$service"
  "$ruff" check "$service_dir"
  "$ruff" format --check "$service_dir"
  "$python" -m compileall -q "$service_dir/src"

  if [[ -d "$service_dir/tests" ]]; then
    "$python" -m unittest discover -s "$service_dir/tests" -v
  fi
done

printf '==> Running integration tests\n'
"$ROOT_DIR/mcp/gmail/.venv/bin/python" -m unittest discover \
  -s "$ROOT_DIR/tests" -v

printf '==> Checking deployment scripts\n'
"$ROOT_DIR/mcp/gmail/.venv/bin/ruff" check "$ROOT_DIR/deployment"
"$ROOT_DIR/mcp/gmail/.venv/bin/ruff" format --check "$ROOT_DIR/deployment"
bash -n "$ROOT_DIR"/deployment/*.sh "$ROOT_DIR"/scripts/*.sh

printf '==> Scanning tracked files for secrets\n'
"$ROOT_DIR/scripts/secret-scan.sh"

printf '==> All checks passed\n'
