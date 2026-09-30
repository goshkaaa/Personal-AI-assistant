"""Home Assistant MCP tool registration."""

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .client import HomeAssistantClient
from .discovery import HomeAssistantReadService
from .location import LocationService

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


def register_tools(server: MCPServer) -> None:
    @server.tool(annotations=READ_ONLY)
    def ha_status() -> dict[str, Any]:
        """Check connectivity and authentication with Home Assistant."""
        return HomeAssistantClient.from_env().status()

    @server.tool(annotations=READ_ONLY)
    def ha_get_state(entity_id: str) -> dict[str, Any]:
        """Get the current state and attributes of one entity."""
        return HomeAssistantClient.from_env().get_state(entity_id)

    @server.tool(annotations=READ_ONLY)
    def ha_find_entities(
        query: str = "",
        domain: str = "",
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Find entities by ID, friendly name, domain, or text."""
        return HomeAssistantClient.from_env().find_entities(query, domain, limit)

    @server.tool(annotations=WRITE)
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

    @server.tool(annotations=WRITE)
    def ha_turn_on(entity_id: str) -> dict[str, Any]:
        """Turn on an entity when writes are enabled."""
        domain = entity_id.split(".", 1)[0]
        return HomeAssistantClient.from_env().call_service(domain, "turn_on", entity_id)

    @server.tool(annotations=WRITE)
    def ha_turn_off(entity_id: str) -> dict[str, Any]:
        """Turn off an entity when writes are enabled."""
        domain = entity_id.split(".", 1)[0]
        return HomeAssistantClient.from_env().call_service(domain, "turn_off", entity_id)

    @server.tool(annotations=WRITE)
    def ha_toggle(entity_id: str) -> dict[str, Any]:
        """Toggle an entity when writes are enabled."""
        domain = entity_id.split(".", 1)[0]
        return HomeAssistantClient.from_env().call_service(domain, "toggle", entity_id)

    @server.tool(annotations=READ_ONLY)
    def ha_get_location(entity_id: str = "") -> dict[str, Any]:
        """Get a person's current HA coordinates, freshness, zone, and map link.

        Omit entity_id when exactly one tracked person is configured.
        """
        return LocationService.from_env().current(entity_id)

    @server.tool(annotations=LOCAL_RECORD)
    def ha_record_location(entity_id: str = "") -> dict[str, Any]:
        """Save a person's current HA coordinates in the private short-lived history."""
        return LocationService.from_env().record(entity_id)

    @server.tool(annotations=READ_ONLY)
    def ha_get_location_history(
        entity_id: str = "",
        hours: int = 24,
        limit: int = 432,
    ) -> dict[str, Any]:
        """Get chronological location points for a route or movement map.

        History never exceeds the configured retention window (72 hours by default).
        """
        return LocationService.from_env().history(entity_id, hours, limit)

    @server.tool(annotations=READ_ONLY)
    def get_entity_state(entity_id: str) -> dict[str, Any]:
        """Read any HA entity by entity_id or an unambiguous human name.

        Returns the complete current state and attributes plus device and area context.
        If several entities are equally plausible, returns candidates with status=ambiguous.
        """
        return HomeAssistantReadService.from_env().get_entity_state(entity_id)

    @server.tool(annotations=READ_ONLY)
    def get_device(device_id: str = "", name: str = "") -> dict[str, Any]:
        """Read an HA device and all of its related entities by ID or human name."""
        return HomeAssistantReadService.from_env().get_device(device_id, name)

    @server.tool(annotations=READ_ONLY)
    def find_entities(query: str, domain: str = "", limit: int = 20) -> dict[str, Any]:
        """Resolve natural-language text against entity, device, and area registries.

        Understands names, aliases, entity IDs, common Russian/English device terms,
        and relationships between areas, devices, and entities.
        """
        return HomeAssistantReadService.from_env().find_entities(query, domain, limit)

    @server.tool(annotations=READ_ONLY)
    def get_person_location(person_id: str) -> dict[str, Any]:
        """Read a person.* or device_tracker.* location by ID or human name.

        Returns zone/state, coordinates, GPS accuracy, freshness, a map URL, and an address
        from HA or the configured MCP geocoder. The HA state ``not_home`` means only that
        the entity is outside HA's configured home zone; it says nothing about residence.
        Omit this technical state from normal location answers unless the user asks about
        Home Assistant zones specifically.
        """
        return HomeAssistantReadService.from_env().get_person_location(person_id)

    @server.tool(annotations=READ_ONLY)
    def get_entity_history(
        entity_id: str,
        start: str = "",
        end: str = "",
        hours: int = 24,
        limit: int = 500,
        minimal_response: bool = True,
    ) -> dict[str, Any]:
        """Read bounded HA history for any entity.

        start/end accept ISO 8601 date-times. If start is omitted, hours before end is used.
        The maximum range is 31 days and the maximum returned point count is 2000.
        """
        return HomeAssistantReadService.from_env().get_entity_history(
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
        """List HA entities, optionally filtered by domain, area, device, or state.

        Use state="unavailable,unknown" to find entities that are currently unavailable.
        """
        return HomeAssistantReadService.from_env().list_entities(
            domain,
            area,
            device,
            state,
            limit,
        )
