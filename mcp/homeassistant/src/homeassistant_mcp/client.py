"""Home Assistant API client and write policy."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from .config import HomeAssistantSettings

ALLOWED_DOMAINS = {
    "button",
    "climate",
    "cover",
    "fan",
    "input_boolean",
    "light",
    "media_player",
    "number",
    "scene",
    "script",
    "select",
    "switch",
    "vacuum",
}
BLOCKED_SERVICES = {"reload", "restart", "stop"}


class HomeAssistantClient:
    def __init__(self, settings: HomeAssistantSettings) -> None:
        self.settings = settings

    @classmethod
    def from_env(cls) -> "HomeAssistantClient":
        return cls(HomeAssistantSettings.from_env())

    def status(self) -> dict[str, Any]:
        return self.request("GET", "/api/")

    def get_state(self, entity_id: str) -> dict[str, Any]:
        return self.request("GET", "/api/states/" + urllib.parse.quote(entity_id, safe="._"))

    def list_states(self) -> list[dict[str, Any]]:
        result = self.request("GET", "/api/states")
        if not isinstance(result, list):
            raise RuntimeError("Home Assistant returned an invalid states response")
        return result

    def get_history(
        self,
        entity_id: str,
        start: datetime,
        end: datetime,
        *,
        minimal_response: bool = True,
    ) -> list[dict[str, Any]]:
        start_value = start.isoformat()
        query = urllib.parse.urlencode(
            {
                "filter_entity_id": entity_id,
                "end_time": end.isoformat(),
                "minimal_response": str(minimal_response).lower(),
            }
        )
        path = "/api/history/period/" + urllib.parse.quote(start_value, safe=":+-TZ") + "?" + query
        result = self.request("GET", path)
        if not isinstance(result, list):
            raise RuntimeError("Home Assistant returned an invalid history response")
        if not result:
            return []
        first = result[0]
        if not isinstance(first, list):
            raise RuntimeError("Home Assistant returned an invalid history response")
        return first

    def get_registries(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch registry data over HA's authenticated WebSocket API."""
        commands = {
            "entities": "config/entity_registry/list",
            "devices": "config/device_registry/list",
            "areas": "config/area_registry/list",
        }
        results = self.websocket_commands(list(commands.values()))
        registries: dict[str, list[dict[str, Any]]] = {}
        for name, command_type in commands.items():
            value = results.get(command_type, [])
            registries[name] = value if isinstance(value, list) else []
        return registries

    def reverse_geocode(self, latitude: float, longitude: float) -> dict[str, Any] | None:
        """Resolve coordinates inside MCP without exposing the HA token to the geocoder."""
        base_url = self.settings.reverse_geocoding_url
        if not base_url:
            return None
        separator = "&" if urllib.parse.urlsplit(base_url).query else "?"
        url = (
            base_url
            + separator
            + urllib.parse.urlencode(
                {
                    "format": "jsonv2",
                    "lat": f"{latitude:.7f}",
                    "lon": f"{longitude:.7f}",
                    "addressdetails": "1",
                    "layer": "address",
                    "zoom": "18",
                    "accept-language": self.settings.reverse_geocoding_language,
                }
            )
        )
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": "personal-ai-assistant-homeassistant-mcp/0.1",
            },
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.settings.timeout_seconds,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError("Reverse geocoding is unavailable") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Reverse geocoder returned an invalid response")
        address = payload.get("address") if isinstance(payload.get("address"), dict) else {}
        return {
            "display_name": payload.get("display_name"),
            "attribution": payload.get("licence") or "OpenStreetMap contributors",
            "address": {
                key: address.get(key)
                for key in (
                    "house_number",
                    "road",
                    "suburb",
                    "city_district",
                    "city",
                    "town",
                    "state",
                    "postcode",
                    "country",
                )
                if address.get(key)
            },
        }

    def find_entities(
        self,
        query: str = "",
        domain: str = "",
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        states = self.list_states()
        query = query.strip().lower()
        domain = domain.strip().lower()
        limit = max(1, min(limit, 100))
        result = []

        for item in states:
            entity_id = item.get("entity_id", "")
            item_domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
            name = str((item.get("attributes") or {}).get("friendly_name", ""))
            if domain and item_domain != domain:
                continue
            if query and query not in f"{entity_id} {name}".lower():
                continue
            result.append({"entity_id": entity_id, "name": name, "state": item.get("state")})
            if len(result) >= limit:
                break
        return result

    def websocket_commands(self, command_types: list[str]) -> dict[str, Any]:
        """Run read-only registry commands in one authenticated WebSocket session."""
        if not self.settings.url:
            raise RuntimeError("HOME_ASSISTANT_URL is not configured")

        parsed = urllib.parse.urlsplit(self.settings.url)
        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        ws_path = parsed.path.rstrip("/") + "/api/websocket"
        ws_url = urllib.parse.urlunsplit((ws_scheme, parsed.netloc, ws_path, "", ""))

        try:
            with connect(
                ws_url,
                open_timeout=self.settings.timeout_seconds,
                close_timeout=self.settings.timeout_seconds,
            ) as socket:
                hello = self._receive_websocket_json(socket)
                if hello.get("type") != "auth_required":
                    raise RuntimeError("Home Assistant WebSocket authentication was not requested")

                socket.send(
                    json.dumps(
                        {
                            "type": "auth",
                            "access_token": self.settings.read_token(),
                        }
                    )
                )
                authenticated = self._receive_websocket_json(socket)
                if authenticated.get("type") != "auth_ok":
                    raise RuntimeError("Home Assistant WebSocket authentication failed")

                results: dict[str, Any] = {}
                for command_id, command_type in enumerate(command_types, start=1):
                    socket.send(json.dumps({"id": command_id, "type": command_type}))
                    response = self._receive_websocket_json(socket)
                    if response.get("id") != command_id or response.get("type") != "result":
                        raise RuntimeError(
                            "Home Assistant returned an unexpected WebSocket response"
                        )
                    if not response.get("success"):
                        error = response.get("error") or {}
                        code = str(error.get("code") or "unknown_error")
                        raise RuntimeError(
                            f"Home Assistant rejected registry command {command_type}: {code}"
                        )
                    results[command_type] = response.get("result")
                return results
        except (OSError, TimeoutError, WebSocketException) as exc:
            raise RuntimeError("Home Assistant WebSocket is unreachable") from exc

    @staticmethod
    def _receive_websocket_json(socket: Any) -> dict[str, Any]:
        raw = socket.recv(timeout=30)
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            message = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Home Assistant returned invalid WebSocket JSON") from exc
        if not isinstance(message, dict):
            raise RuntimeError("Home Assistant returned an invalid WebSocket message")
        return message

    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: str = "",
        data_json: str = "{}",
    ) -> dict[str, Any]:
        if not self.settings.allow_write:
            raise RuntimeError(
                "Home Assistant writes are disabled; set MCP_ALLOW_HOME_ASSISTANT_WRITE=true"
            )

        domain = domain.strip()
        service = service.strip()
        if domain not in ALLOWED_DOMAINS:
            raise ValueError(f"Domain is not allowed: {domain}")
        if service in BLOCKED_SERVICES:
            raise ValueError(f"Service is blocked: {service}")

        try:
            data = json.loads(data_json or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("data_json must contain valid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("data_json must contain a JSON object")
        if entity_id:
            data["entity_id"] = entity_id

        path = "/api/services/" + urllib.parse.quote(domain) + "/" + urllib.parse.quote(service)
        return self.request("POST", path, data)

    def request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
    ) -> Any:
        if not self.settings.url:
            raise RuntimeError("HOME_ASSISTANT_URL is not configured")

        body = json.dumps(data).encode("utf-8") if data is not None else None
        request = urllib.request.Request(
            self.settings.url + path,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.settings.read_token()}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.settings.timeout_seconds,
            ) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read(512).decode("utf-8", errors="replace")
            raise RuntimeError(f"Home Assistant HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("Home Assistant is unreachable") from exc
