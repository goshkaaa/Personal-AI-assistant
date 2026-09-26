"""Home Assistant MCP tool registration."""

from typing import Any

from mcp.server.mcpserver import MCPServer

from .client import HomeAssistantClient


def register_tools(server: MCPServer) -> None:
    @server.tool()
    def ha_status() -> dict[str, Any]:
        """Check connectivity and authentication with Home Assistant."""
        return HomeAssistantClient.from_env().status()

    @server.tool()
    def ha_get_state(entity_id: str) -> dict[str, Any]:
        """Get the current state and attributes of one entity."""
        return HomeAssistantClient.from_env().get_state(entity_id)

    @server.tool()
    def ha_find_entities(
        query: str = "",
        domain: str = "",
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Find entities by ID, friendly name, domain, or text."""
        return HomeAssistantClient.from_env().find_entities(query, domain, limit)

    @server.tool()
    def ha_call_service(
        domain: str,
        service: str,
        entity_id: str = "",
        data_json: str = "{}",
    ) -> dict[str, Any]:
        """Call an allowlisted service when writes are enabled."""
        return HomeAssistantClient.from_env().call_service(
            domain,
            service,
            entity_id,
            data_json,
        )

    @server.tool()
    def ha_turn_on(entity_id: str) -> dict[str, Any]:
        """Turn on an entity when writes are enabled."""
        domain = entity_id.split(".", 1)[0]
        return HomeAssistantClient.from_env().call_service(domain, "turn_on", entity_id)

    @server.tool()
    def ha_turn_off(entity_id: str) -> dict[str, Any]:
        """Turn off an entity when writes are enabled."""
        domain = entity_id.split(".", 1)[0]
        return HomeAssistantClient.from_env().call_service(domain, "turn_off", entity_id)

    @server.tool()
    def ha_toggle(entity_id: str) -> dict[str, Any]:
        """Toggle an entity when writes are enabled."""
        domain = entity_id.split(".", 1)[0]
        return HomeAssistantClient.from_env().call_service(domain, "toggle", entity_id)
