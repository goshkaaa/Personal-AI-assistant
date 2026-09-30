.DEFAULT_GOAL := help

.PHONY: help setup check config services deploy-check

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target>\n\n"} /^[a-zA-Z_-]+:.*## / {printf "  %-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Install Hermes and all local MCP modules
	./deployment/setup.sh

check: ## Run formatting, lint, bytecode, and unit checks
	./scripts/check.sh

config: ## Generate the Hermes MCP configuration block
	./deployment/generate_config.py

services: ## Install Telegram workers as systemd user services
	./deployment/install_user_services.py

deploy-check: check ## Run strict deployment safety and readiness checks
	./deployment/preflight.py
