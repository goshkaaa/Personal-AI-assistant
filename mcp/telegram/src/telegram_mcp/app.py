"""Application composition root and transport startup."""

import asyncio
import os
from urllib.parse import urlsplit

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from .auth import StaticTokenVerifier, build_auth_settings
from .config import PRIVATE_DIR, env_path, private_path
from .tasks.database import database
from .tasks.tools import register_task_tools
from .tools import register_telegram_tools

DEFAULT_RESOURCE_URL = "http://127.0.0.1:8765/mcp"
DEFAULT_ISSUER_URL = "http://127.0.0.1:8765"


def create_server() -> MCPServer:
    """Compose a server from independent domain tool modules."""
    database.initialize()
    resource_url = os.environ.get("MCP_RESOURCE_URL", DEFAULT_RESOURCE_URL)
    issuer_url = os.environ.get("MCP_ISSUER_URL", DEFAULT_ISSUER_URL)
    token_file = private_path(env_path("MCP_TOKEN_FILE", PRIVATE_DIR / "telegram-mcp-token"))

    server = MCPServer(
        name="telegram",
        token_verifier=StaticTokenVerifier(token_file, resource_url),
        auth=build_auth_settings(issuer_url, resource_url),
        instructions=(
            "Personal Telegram tools. "
            "Use search/read tools to resolve contacts and inspect context. "
            "Sending a message marks the conversation as managed so incoming "
            "replies can be tracked and surfaced to the owner."
        ),
    )
    register_telegram_tools(server)
    register_task_tools(server)
    return server


def build_transport_security(resource_url: str) -> TransportSecuritySettings:
    """Build strict host/origin allowlists for streamable HTTP."""
    resource = urlsplit(resource_url)
    default_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    if resource.hostname:
        resource_host = resource.hostname
        if ":" in resource_host:
            resource_host = f"[{resource_host}]"
        default_hosts.append(f"{resource_host}:{resource.port}" if resource.port else resource_host)

    allowed_hosts = [
        value.strip()
        for value in os.environ.get("MCP_ALLOWED_HOSTS", ",".join(default_hosts)).split(",")
        if value.strip()
    ]
    default_origins = [
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
    ]
    if resource.scheme and resource.netloc:
        default_origins.append(f"{resource.scheme}://{resource.netloc}")
    allowed_origins = [
        value.strip()
        for value in os.environ.get("MCP_ALLOWED_ORIGINS", ",".join(default_origins)).split(",")
        if value.strip()
    ]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


def main() -> None:
    server = create_server()
    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()

    if transport == "streamable-http":
        resource_url = os.environ.get("MCP_RESOURCE_URL", DEFAULT_RESOURCE_URL)
        asyncio.run(
            server.run_streamable_http_async(
                host=os.environ.get("MCP_HOST", "127.0.0.1"),
                port=int(os.environ.get("MCP_PORT", "8765")),
                streamable_http_path=os.environ.get("MCP_PATH", "/mcp"),
                transport_security=build_transport_security(resource_url),
            )
        )
        return

    if transport != "stdio":
        raise ValueError("MCP_TRANSPORT must be 'stdio' or 'streamable-http'")
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
