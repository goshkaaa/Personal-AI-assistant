"""MCP tool adapters over injected application services."""

from __future__ import annotations

from typing import Any, Protocol

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from ..application.location_service import LocationService
from ..application.read_service import HomeAssistantReadService
from ..domain.ports import HomeAssistantGateway

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=True,
)
LOCAL_RECORD = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)


class HomeAssistantDependencies(Protocol):
    """Dependencies exposed by the composition root to MCP adapters."""

    gateway: HomeAssistantGateway
    read_service: HomeAssistantReadService
    location_service: LocationService


class HomeAssistantToolRegistry:
    """Registers stable MCP contracts against a process-scoped container."""

    def __init__(self, container: HomeAssistantDependencies) -> None:
        self.container = container

    def register(self, server: MCPServer) -> None:
        container = self.container

        @server.tool(annotations=READ_ONLY)
        def ha_status() -> dict[str, Any]:
            """Check connectivity and authentication with Home Assistant."""
            return container.gateway.status()

        @server.tool(annotations=READ_ONLY)
        def ha_get_state(entity_id: str) -> dict[str, Any]:
            """Get the current state and attributes of one entity."""
            return container.gateway.get_state(entity_id)

        @server.tool(annotations=READ_ONLY)
        def ha_find_entities(
            query: str = "",
            domain: str = "",
            limit: int = 30,
        ) -> list[dict[str, Any]]:
            """Find entities by ID, friendly name, domain, or text."""
            return container.gateway.find_entities(query, domain, limit)

        @server.tool(annotations=WRITE)
        def ha_call_service(
            domain: str,
            service: str,
            entity_id: str = "",
            data_json: str = "{}",
        ) -> dict[str, Any]:
            """Call an allowlisted service when writes are enabled."""
            return container.gateway.call_service(domain, service, entity_id, data_json)

        @server.tool(annotations=WRITE)
        def ha_turn_on(entity_id: str) -> dict[str, Any]:
            """Turn on an entity when writes are enabled."""
            domain = entity_id.split(".", 1)[0]
            return container.gateway.call_service(domain, "turn_on", entity_id)

        @server.tool(annotations=WRITE)
        def ha_turn_off(entity_id: str) -> dict[str, Any]:
            """Turn off an entity when writes are enabled."""
            domain = entity_id.split(".", 1)[0]
            return container.gateway.call_service(domain, "turn_off", entity_id)

        @server.tool(annotations=WRITE)
        def ha_toggle(entity_id: str) -> dict[str, Any]:
            """Toggle an entity when writes are enabled."""
            domain = entity_id.split(".", 1)[0]
            return container.gateway.call_service(domain, "toggle", entity_id)

        @server.tool(annotations=READ_ONLY)
        def ha_get_location(entity_id: str = "") -> dict[str, Any]:
            """Get current HA coordinates, freshness, zone, and map link."""
            return container.location_service.current(entity_id)

        @server.tool(annotations=LOCAL_RECORD)
        def ha_record_location(entity_id: str = "") -> dict[str, Any]:
            """Save current coordinates in the private short-lived history."""
            return container.location_service.record(entity_id)

        @server.tool(annotations=READ_ONLY)
        def ha_get_location_history(
            entity_id: str = "",
            hours: int = 24,
            limit: int = 432,
        ) -> dict[str, Any]:
            """Get chronological points from the bounded private route history."""
            return container.location_service.history(entity_id, hours, limit)

        @server.tool(annotations=READ_ONLY)
        def get_entity_state(entity_id: str) -> dict[str, Any]:
            """Read any HA entity by entity ID or an unambiguous human name."""
            return container.read_service.get_entity_state(entity_id)

        @server.tool(annotations=READ_ONLY)
        def get_device(device_id: str = "", name: str = "") -> dict[str, Any]:
            """Read a device and all related entities by ID or human name."""
            return container.read_service.get_device(device_id, name)

        @server.tool(annotations=READ_ONLY)
        def find_entities(
            query: str,
            domain: str = "",
            limit: int = 20,
        ) -> dict[str, Any]:
            """Resolve text against entity, device, and area registries."""
            return container.read_service.find_entities(query, domain, limit)

        @server.tool(annotations=READ_ONLY)
        def get_person_location(person_id: str) -> dict[str, Any]:
            """Read a person or tracker location by ID or human name.

            ``not_home`` is a technical HA zone state, not a statement about residence,
            and must be omitted from normal location answers.
            """
            return container.read_service.get_person_location(person_id)

        @server.tool(annotations=READ_ONLY)
        def get_entity_history(
            entity_id: str,
            start: str = "",
            end: str = "",
            hours: int = 24,
            limit: int = 500,
            minimal_response: bool = True,
        ) -> dict[str, Any]:
            """Read bounded Home Assistant history for any entity."""
            return container.read_service.get_entity_history(
                entity_id,
                start,
                end,
                hours,
                limit,
                minimal_response,
            )

        @server.tool(annotations=READ_ONLY)
        def list_entities(
            domain: str = "",
            area: str = "",
            device: str = "",
            state: str = "",
            limit: int = 200,
        ) -> dict[str, Any]:
            """List entities filtered by domain, area, device, or state."""
            return container.read_service.list_entities(
                domain,
                area,
                device,
                state,
                limit,
            )


def register_tools(
    server: MCPServer,
    container: HomeAssistantDependencies,
) -> None:
    HomeAssistantToolRegistry(container).register(server)
