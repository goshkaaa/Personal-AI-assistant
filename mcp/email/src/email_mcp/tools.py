"""Backward-compatible email tool registration facade."""

from mcp.server.mcpserver import MCPServer

from .application.service import EmailService
from .composition import EmailContainer
from .presentation.mcp_tools import register_email_tools as _register_email_tools


def register_email_tools(mcp: MCPServer, service: EmailService | None = None) -> None:
    """Register tools, retaining the old one-argument import contract."""
    _register_email_tools(mcp, service if service is not None else EmailContainer().service)
