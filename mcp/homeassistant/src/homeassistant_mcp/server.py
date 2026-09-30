"""Home Assistant MCP application."""

from mcp.server.mcpserver import MCPServer

from .tools import register_tools


def create_server() -> MCPServer:
    server = MCPServer(
        name="homeassistant",
        instructions=(
            "This MCP is the only normal interface for Home Assistant. Read-only tools "
            "get_entity_state, get_device, find_entities, get_person_location, "
            "get_entity_history, and list_entities may be used without confirmation. "
            "Resolve a natural-language name with find_entities and registry context; ask "
            "only when the result is genuinely ambiguous. Never use shell, terminal, curl, "
            "Python, or a separate web tool to query Home Assistant or reverse-geocode its "
            "coordinates. get_person_location performs configured reverse geocoding inside "
            "this MCP. Never phrase the Home Assistant state not_home as 'not at home' or "
            "'не дома': it only means outside HA's configured home zone and says nothing "
            "about the person's residence. For location questions, prefer the resolved "
            "address or named zone, then coordinates and map link. Do not guess an address. "
            "Service calls and ha_turn_* tools are write actions and retain the "
            "configured confirmation and write policy. Use the local ha_get_location_history "
            "only when a stored movement route is requested."
        ),
    )
    register_tools(server)
    return server


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
