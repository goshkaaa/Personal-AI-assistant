"""Backward-compatible imports for the Home Assistant infrastructure adapter."""

from .infrastructure.home_assistant import (
    ALLOWED_DOMAINS,
    BLOCKED_SERVICES,
    HomeAssistantClient,
)

__all__ = ["ALLOWED_DOMAINS", "BLOCKED_SERVICES", "HomeAssistantClient"]
