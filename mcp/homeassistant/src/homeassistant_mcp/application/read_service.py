"""Read-only Home Assistant use cases."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from ..domain.models import EntityMatch, EntityRecord, EntityResolution, RegistrySnapshot
from ..domain.ports import HomeAssistantGateway
from .entity_catalog import EntityCatalog
from .entity_matcher import EntityMatcher
from .entity_presenter import EntityPresenter
from .text_search import TextSearch


def _parse_time(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO 8601 date-time") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class HomeAssistantReadService:
    """Coordinates catalog, matching, and gateway operations for read tools."""

    def __init__(
        self,
        gateway: HomeAssistantGateway,
        *,
        catalog: EntityCatalog | None = None,
        matcher: EntityMatcher | None = None,
        presenter: EntityPresenter | None = None,
    ) -> None:
        text = TextSearch()
        self.gateway = gateway
        self.catalog = catalog or EntityCatalog(gateway, text)
        self.matcher = matcher or EntityMatcher(text)
        self.presenter = presenter or EntityPresenter()

    def snapshot(self) -> RegistrySnapshot:
        return self.catalog.snapshot()

    def find_entities(
        self,
        query: str,
        domain: str = "",
        limit: int = 20,
    ) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("query is required")
        domains = {domain.strip().lower()} if domain.strip() else None
        limit = max(1, min(limit, 100))
        snapshot = self.catalog.snapshot()
        ranked = self.matcher.rank(snapshot, query, domains=domains)
        matches = [self.presenter.summary(match.record, match) for match in ranked[:limit]]
        ambiguous = len(ranked) > 1 and ranked[1].score >= ranked[0].score - 20
        return {
            "status": "ok",
            "query": query,
            "match_count": len(matches),
            "ambiguous": ambiguous,
            "registry_available": snapshot.registry_available,
            "matches": matches,
        }

    def get_entity_state(self, entity_id: str) -> dict[str, Any]:
        snapshot = self.catalog.snapshot()
        resolution = self.matcher.resolve(snapshot, entity_id)
        failure = self._resolution_failure(entity_id, resolution)
        if failure is not None:
            return failure
        record = self._resolved_record(resolution)
        return {
            "status": "ok",
            "resolved_from": entity_id,
            **self.presenter.summary(record),
            "attributes": record.attributes,
            "last_changed": record.last_changed,
            "registry": {
                "platform": record.registry.get("platform"),
                "disabled_by": record.registry.get("disabled_by"),
                "hidden_by": record.registry.get("hidden_by"),
            },
        }

    def list_entities(
        self,
        domain: str = "",
        area: str = "",
        device: str = "",
        state: str = "",
        limit: int = 200,
    ) -> dict[str, Any]:
        snapshot = self.catalog.snapshot()
        domain = domain.strip().lower()
        states = {self.matcher.text.normalize(value) for value in state.split(",") if value.strip()}
        limit = max(1, min(limit, 500))
        matches: list[dict[str, Any]] = []
        total = 0
        for record in snapshot.records:
            if domain and record.domain != domain:
                continue
            if area and not self.matcher.text.field_matches(area, record.search_area):
                continue
            if device and not self.matcher.text.field_matches(
                device,
                record.search_device,
            ):
                continue
            if states and self.matcher.text.normalize(record.state) not in states:
                continue
            total += 1
            if len(matches) < limit:
                matches.append(self.presenter.summary(record))
        return {
            "status": "ok",
            "filters": {"domain": domain, "area": area, "device": device, "state": state},
            "match_count": total,
            "returned_count": len(matches),
            "truncated": total > len(matches),
            "registry_available": snapshot.registry_available,
            "entities": matches,
        }

    def get_device(self, device_id: str = "", name: str = "") -> dict[str, Any]:
        query = (device_id or name).strip()
        if not query:
            raise ValueError("device_id or name is required")
        snapshot = self.catalog.snapshot()
        ranked = self._rank_devices(snapshot, query)
        if not ranked:
            return {"status": "not_found", "query": query, "candidates": []}
        ambiguous = len(ranked) > 1 and ranked[1][0] >= ranked[0][0] - 20
        if ambiguous:
            return {
                "status": "ambiguous",
                "query": query,
                "candidates": [
                    {"device_id": item[1], "name": item[2], "match_score": item[0]}
                    for item in ranked[:10]
                ],
            }

        _, resolved_id, resolved_name, device = ranked[0]
        entities = [
            self.presenter.summary(record)
            for record in snapshot.records
            if record.device_id == resolved_id
        ]
        area_id = device.get("area_id")
        area = snapshot.areas.get(str(area_id)) if area_id else None
        return {
            "status": "ok",
            "resolved_from": query,
            "device": {
                "id": resolved_id,
                "name": resolved_name,
                "manufacturer": device.get("manufacturer"),
                "model": device.get("model"),
                "model_id": device.get("model_id"),
                "sw_version": device.get("sw_version"),
                "hw_version": device.get("hw_version"),
                "area": ({"id": area_id, "name": area.get("name")} if area_id and area else None),
                "disabled_by": device.get("disabled_by"),
            },
            "entity_count": len(entities),
            "entities": entities,
        }

    def get_person_location(self, person_id: str) -> dict[str, Any]:
        snapshot = self.catalog.snapshot()
        prefer_person = not self.matcher.text.contains_term(
            person_id,
            {"phone", "tracker", "телефон", "трекер"},
        )
        ranked = self.matcher.rank(
            snapshot,
            person_id,
            domains={"person", "device_tracker"},
            domain_boosts={"person": 180} if prefer_person else {"device_tracker": 180},
        )
        resolution = self._resolution_from_matches(ranked)
        failure = self._resolution_failure(person_id, resolution)
        if failure is not None:
            return failure
        record = self._resolved_record(resolution)
        return self._location_response(person_id, record)

    def get_entity_history(
        self,
        entity_id: str,
        start: str = "",
        end: str = "",
        hours: int = 24,
        limit: int = 500,
        minimal_response: bool = True,
    ) -> dict[str, Any]:
        resolution = self.matcher.resolve(self.catalog.snapshot(), entity_id)
        failure = self._resolution_failure(entity_id, resolution)
        if failure is not None:
            return failure
        record = self._resolved_record(resolution)

        end_time = _parse_time(end, "end") if end.strip() else datetime.now(UTC)
        hours = max(1, min(hours, 24 * 31))
        start_time = (
            _parse_time(start, "start") if start.strip() else end_time - timedelta(hours=hours)
        )
        if start_time >= end_time:
            raise ValueError("start must be earlier than end")
        if end_time - start_time > timedelta(days=31):
            raise ValueError("history range cannot exceed 31 days")
        limit = max(1, min(limit, 2000))
        history = self.gateway.get_history(
            record.entity_id,
            start_time,
            end_time,
            minimal_response=minimal_response,
        )
        points = []
        for item in history[:limit]:
            if not isinstance(item, dict):
                continue
            point = {
                "state": item.get("state"),
                "last_changed": item.get("last_changed"),
                "last_updated": item.get("last_updated"),
            }
            if item.get("attributes"):
                point["attributes"] = item["attributes"]
            points.append(point)
        return {
            "status": "ok",
            "entity_id": record.entity_id,
            "name": record.name,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "point_count": len(points),
            "truncated": len(history) > len(points),
            "points": points,
        }

    def _rank_devices(
        self,
        snapshot: RegistrySnapshot,
        query: str,
    ) -> list[tuple[int, str, str, dict[str, Any]]]:
        ranked = []
        text = self.matcher.text
        for candidate_id, device in snapshot.devices.items():
            candidate_name = device.get("name_by_user") or device.get("name") or candidate_id
            aliases = device.get("aliases") if isinstance(device.get("aliases"), list) else []
            search = text.searchable(candidate_id, candidate_name, *aliases)
            if text.normalize(query) == text.normalize(candidate_id):
                score = 1000
            elif text.normalize(query) == text.normalize(candidate_name):
                score = 800
            elif text.searchable(query) in search:
                score = 300
            else:
                score = sum(
                    60
                    for token in text.tokens(query)
                    if any(text.token_matches(token, item) for item in search.split())
                )
            if score:
                ranked.append((score, candidate_id, str(candidate_name), device))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return ranked

    def _location_response(
        self,
        query: str,
        record: EntityRecord,
    ) -> dict[str, Any]:
        attributes = record.attributes
        latitude = self._coordinate_or_none(attributes.get("latitude"), -90, 90)
        longitude = self._coordinate_or_none(attributes.get("longitude"), -180, 180)
        gps_accuracy = self._coordinate_or_none(
            attributes.get("gps_accuracy"),
            0,
            math.inf,
        )
        address = attributes.get("formatted_address") or attributes.get("address")
        address_details = None
        reverse_geocoding = None
        if not address and latitude is not None and longitude is not None:
            try:
                geocoded = self.gateway.reverse_geocode(latitude, longitude)
            except RuntimeError:
                geocoded = None
            if geocoded:
                address = geocoded.get("display_name")
                address_details = geocoded.get("address")
                reverse_geocoding = "configured MCP geocoder"

        raw_state = record.state
        zone = (
            raw_state
            if raw_state
            and raw_state
            not in {
                "not_home",
                "unknown",
                "unavailable",
            }
            else None
        )
        result = {
            "status": "ok",
            "resolved_from": query,
            "entity_id": record.entity_id,
            "name": record.name,
            "state": raw_state,
            "ha_state": raw_state,
            "zone": zone,
            "outside_configured_home_zone": raw_state == "not_home",
            "state_interpretation": (
                "not_home only means outside Home Assistant's configured home zone; "
                "it does not describe the person's residence. Do not mention this "
                "technical state in a normal location answer unless the user asks "
                "specifically about Home Assistant zones"
                if raw_state == "not_home"
                else None
            ),
            "latitude": latitude,
            "longitude": longitude,
            "gps_accuracy": gps_accuracy,
            "last_updated": record.last_updated,
            "source": attributes.get("source"),
            "address": address,
            "address_details": address_details,
            "reverse_geocoding": reverse_geocoding,
        }
        if latitude is not None and longitude is not None:
            result["map_url"] = (
                "https://www.openstreetmap.org/"
                f"?mlat={latitude:.6f}&mlon={longitude:.6f}"
                f"#map=16/{latitude:.6f}/{longitude:.6f}"
            )
        return result

    def _resolution_failure(
        self,
        query: str,
        resolution: EntityResolution,
    ) -> dict[str, Any] | None:
        if resolution.record is None:
            return {"status": "not_found", "query": query, "candidates": []}
        if resolution.ambiguous:
            return {
                "status": "ambiguous",
                "query": query,
                "candidates": [
                    self.presenter.summary(match.record, match) for match in resolution.matches[:10]
                ],
            }
        return None

    @staticmethod
    def _resolution_from_matches(matches: list[EntityMatch]) -> EntityResolution:
        if not matches:
            return EntityResolution(None, (), False)
        ambiguous = len(matches) > 1 and matches[1].score >= matches[0].score - 20
        return EntityResolution(matches[0].record, tuple(matches), ambiguous)

    @staticmethod
    def _resolved_record(resolution: EntityResolution) -> EntityRecord:
        if resolution.record is None:  # pragma: no cover - guarded by caller
            raise RuntimeError("entity resolution unexpectedly produced no record")
        return resolution.record

    @staticmethod
    def _coordinate_or_none(
        value: Any,
        minimum: float,
        maximum: float,
    ) -> float | None:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return result if math.isfinite(result) and minimum <= result <= maximum else None
