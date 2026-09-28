#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SERVICES=(calendar email homeassistant obsidian telegram)
PRIVATE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/personal-ai-assistant/secrets"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/personal-ai-assistant"

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

command -v git >/dev/null 2>&1 || fail "git is required"
command -v uv >/dev/null 2>&1 || fail "uv is required: https://docs.astral.sh/uv/"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "Python 3.11-3.13 is required"
"$PYTHON_BIN" -c 'import sys; raise SystemExit(not ((3, 11) <= sys.version_info < (3, 14)))' \
  || fail "Python 3.11-3.13 is required"

printf '==> Initializing Hermes Agent\n'
git -C "$ROOT_DIR" submodule update --init --recursive

printf '==> Installing Hermes Agent\n'
if [[ ! -x "$ROOT_DIR/.venv/bin/python" ]]; then
  uv venv "$ROOT_DIR/.venv" --python "$PYTHON_BIN"
fi
uv pip install --python "$ROOT_DIR/.venv/bin/python" \
  -e "$ROOT_DIR/hermes/hermes-agent[all]"

for service in "${SERVICES[@]}"; do
  service_dir="$ROOT_DIR/mcp/$service"
  printf '==> Installing %s MCP\n' "$service"
  uv sync --project "$service_dir" --locked --extra dev --no-editable

  if [[ -f "$service_dir/.env.example" && ! -e "$service_dir/.env" ]]; then
    cp "$service_dir/.env.example" "$service_dir/.env"
  fi
  if [[ -f "$service_dir/.env" ]]; then
    chmod 600 "$service_dir/.env"
  fi
done

install -d -m 700 \
  "$ROOT_DIR/.local" \
  "$PRIVATE_DIR" \
  "$DATA_DIR" \
  "$DATA_DIR/telegram"

"$ROOT_DIR/deployment/generate_config.py" >/dev/null

printf '\nReady. Next:\n'
printf '  1. Fill mcp/*/.env and add credentials.\n'
printf '  2. Authorize Telegram and configure email and calendar accounts (see README.md).\n'
printf '  3. Run make check.\n'
printf '  4. Add .local/hermes-mcp.yaml to your Hermes config.\n'
