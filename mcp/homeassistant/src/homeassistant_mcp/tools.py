"""Backward-compatible imports for the MCP presentation layer."""

from mcp.server.mcpserver import MCPServer

from .composition import HomeAssistantContainer
from .presentation.mcp_tools import (
    LOCAL_RECORD,
    READ_ONLY,
    WRITE,
    HomeAssistantDependencies,
    HomeAssistantToolRegistry,
)
from .presentation.mcp_tools import register_tools as _register_tools


def register_tools(
    server: MCPServer,
    container: HomeAssistantDependencies | None = None,
) -> None:
    """Register tools while preserving the original optional-container API."""
    _register_tools(server, container or HomeAssistantContainer())


__all__ = [
    "LOCAL_RECORD",
    "READ_ONLY",
    "WRITE",
    "HomeAssistantDependencies",
    "HomeAssistantToolRegistry",
    "register_tools",
]
