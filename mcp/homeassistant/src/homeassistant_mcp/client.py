"""Home Assistant REST client and write policy."""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

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

    def find_entities(
        self,
        query: str = "",
        domain: str = "",
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        states = self.request("GET", "/api/states")
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
