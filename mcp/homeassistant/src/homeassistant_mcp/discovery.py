"""Registry-aware, read-only Home Assistant discovery and state access."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from .client import HomeAssistantClient

_CYRILLIC_TO_LATIN = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "i",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "kh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
)

_STOP_WORDS = {
    "a",
    "the",
    "v",
    "vo",
    "where",
    "what",
    "which",
    "is",
    "are",
    "li",
    "moi",
    "my",
    "show",
    "find",
    "в",
    "во",
    "включен",
    "включена",
    "выключен",
    "выключена",
    "где",
    "дай",
    "какая",
    "какое",
    "какой",
    "какие",
    "ли",
    "мой",
    "моя",
    "моё",
    "найди",
    "покажи",
    "сейчас",
    "у",
    "что",
}

_DOMAIN_TERMS = {
    "light": {"light", "lamp", "свет", "ламп"},
    "person": {"person", "people", "человек", "где", "where"},
    "device_tracker": {"phone", "tracker", "телефон", "трекер", "где", "where"},
    "lock": {"lock", "locked", "замок", "заперт"},
    "binary_sensor": {"door", "window", "двер", "окн"},
    "climate": {"thermostat", "climate", "термостат", "климат"},
}

_DEVICE_CLASS_TERMS = {
    "battery": {"battery", "charge", "level", "батаре", "заряд"},
    "temperature": {"temperature", "temp", "температур"},
    "door": {"door", "двер"},
    "window": {"window", "окн"},
    "opening": {"open", "closed", "открыт", "закрыт"},
}


def _normalize(value: Any) -> str:
    text = str(value or "").casefold().replace("ё", "е")
    return " ".join(re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).split())


def _searchable(*values: Any) -> str:
    original = _normalize(" ".join(str(value or "") for value in values))
    transliterated = _normalize(original.translate(_CYRILLIC_TO_LATIN))
    return f"{original} {transliterated}".strip()


def _tokens(value: Any) -> set[str]:
    return {token for token in _searchable(value).split() if token not in _STOP_WORDS}


def _token_matches(needle: str, candidate: str) -> bool:
    if needle == candidate:
        return True
    if min(len(needle), len(candidate)) < 4:
        return False
    if needle.startswith(candidate) or candidate.startswith(needle):
        return True
    common_prefix = 0
    for left, right in zip(needle, candidate, strict=False):
        if left != right:
            break
        common_prefix += 1
    return common_prefix >= 4 and common_prefix / min(len(needle), len(candidate)) >= 0.65


def _contains_term(query: str, terms: set[str]) -> bool:
    haystack = _searchable(query)
    return any(_normalize(term) in haystack for term in terms)


def _field_matches(query: str, field: str) -> bool:
    query_text = _searchable(query)
    field_text = _searchable(field)
    if not query_text:
        return True
    if query_text in field_text:
        return True
    query_tokens = _tokens(query)
    field_tokens = _tokens(field)
    return bool(query_tokens) and all(
        any(_token_matches(query_token, field_token) for field_token in field_tokens)
        for query_token in query_tokens
    )


def _semantic_tokens() -> set[str]:
    result = set()
    for terms in (*_DOMAIN_TERMS.values(), *_DEVICE_CLASS_TERMS.values()):
        for term in terms:
            result.update(_tokens(term))
    return result


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _public_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "device_class",
        "unit_of_measurement",
        "battery_level",
        "latitude",
        "longitude",
        "gps_accuracy",
        "source",
        "temperature",
        "current_temperature",
    )
    return {key: attributes[key] for key in keys if key in attributes}


def _parse_time(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO 8601 date-time") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class HomeAssistantReadService:
    """Read-only service that combines live states with HA registries."""

    def __init__(self, client: HomeAssistantClient) -> None:
        self.client = client

    @classmethod
    def from_env(cls) -> "HomeAssistantReadService":
        return cls(HomeAssistantClient.from_env())

    def snapshot(self) -> dict[str, Any]:
        states = self.client.list_states()
        registry_available = True
        try:
            registries = self.client.get_registries()
        except RuntimeError:
            registries = {"entities": [], "devices": [], "areas": []}
            registry_available = False

        return self._build_snapshot(states, registries, registry_available)

    def _build_snapshot(
        self,
        states: list[dict[str, Any]],
        registries: dict[str, list[dict[str, Any]]],
        registry_available: bool,
    ) -> dict[str, Any]:
        state_by_id = {
            str(item.get("entity_id")): item
            for item in states
            if isinstance(item, dict) and item.get("entity_id")
        }
        entity_registry = {
            str(item.get("entity_id")): item
            for item in _as_list(registries.get("entities"))
            if isinstance(item, dict) and item.get("entity_id")
        }
        devices = {
            str(item.get("id")): item
            for item in _as_list(registries.get("devices"))
            if isinstance(item, dict) and item.get("id")
        }
        areas = {
            str(item.get("area_id") or item.get("id")): item
            for item in _as_list(registries.get("areas"))
            if isinstance(item, dict) and (item.get("area_id") or item.get("id"))
        }

        records = []
        for entity_id in sorted(set(state_by_id) | set(entity_registry)):
            state = state_by_id.get(entity_id) or {}
            registry = entity_registry.get(entity_id) or {}
            attributes = state.get("attributes") or {}
            device_id = registry.get("device_id") or attributes.get("device_id")
            device = devices.get(str(device_id)) if device_id else None
            area_id = registry.get("area_id") or (device or {}).get("area_id")
            area = areas.get(str(area_id)) if area_id else None
            name = (
                registry.get("name")
                or attributes.get("friendly_name")
                or registry.get("original_name")
                or entity_id
            )
            device_name = (device or {}).get("name_by_user") or (device or {}).get("name") or ""
            area_name = (area or {}).get("name") or ""
            aliases = [
                *[str(value) for value in _as_list(registry.get("aliases"))],
                *[str(value) for value in _as_list((device or {}).get("aliases"))],
                *[str(value) for value in _as_list((area or {}).get("aliases"))],
            ]
            domain = entity_id.partition(".")[0]
            device_class = attributes.get("device_class") or registry.get("device_class")
            record = {
                "entity_id": entity_id,
                "domain": domain,
                "name": str(name),
                "original_name": registry.get("original_name"),
                "aliases": aliases,
                "state": state.get("state"),
                "last_changed": state.get("last_changed"),
                "last_updated": state.get("last_updated"),
                "attributes": attributes,
                "registry": registry,
                "device_id": str(device_id) if device_id else None,
                "device_name": str(device_name) if device_name else None,
                "area_id": str(area_id) if area_id else None,
                "area_name": str(area_name) if area_name else None,
                "device_class": device_class,
            }
            record["search_entity"] = _searchable(
                entity_id,
                name,
                registry.get("original_name"),
                *aliases,
            )
            record["search_device"] = _searchable(device_name)
            record["search_area"] = _searchable(area_name, *((area or {}).get("aliases") or []))
            records.append(record)

        return {
            "records": records,
            "devices": devices,
            "areas": areas,
            "registry_available": registry_available,
        }

    def _rank_entities(
        self,
        snapshot: dict[str, Any],
        query: str,
        *,
        domains: set[str] | None = None,
        domain_boosts: dict[str, int] | None = None,
    ) -> list[tuple[int, dict[str, Any], list[str]]]:
        query = query.strip()
        normalized_query = _normalize(query)
        search_query = _searchable(query)
        query_tokens = _tokens(query)
        hinted_domains = {
            domain for domain, terms in _DOMAIN_TERMS.items() if _contains_term(query, terms)
        }
        hinted_classes = {
            device_class
            for device_class, terms in _DEVICE_CLASS_TERMS.items()
            if _contains_term(query, terms)
        }
        semantic_tokens = _semantic_tokens()
        identity_tokens = {
            token
            for token in query_tokens
            if not any(_token_matches(token, semantic) for semantic in semantic_tokens)
        }
        matched_area_ids = {
            str(area_id)
            for area_id, area in snapshot["areas"].items()
            if any(
                _token_matches(query_token, area_token)
                for query_token in query_tokens
                for area_token in _tokens(
                    " ".join(
                        [
                            str(area.get("name") or ""),
                            *[str(value) for value in _as_list(area.get("aliases"))],
                        ]
                    )
                )
            )
        }

        ranked = []
        for record in snapshot["records"]:
            if domains and record["domain"] not in domains:
                continue
            if matched_area_ids and record.get("area_id") not in matched_area_ids:
                continue
            if hinted_classes:
                has_hinted_class = record.get("device_class") in hinted_classes
                has_battery_attribute = (
                    "battery" in hinted_classes and "battery_level" in record["attributes"]
                )
                has_hinted_domain = record["domain"] in hinted_domains
                if not has_hinted_class and not has_battery_attribute and not has_hinted_domain:
                    continue
            elif hinted_domains and record["domain"] not in hinted_domains:
                continue
            score = 0
            reasons = []
            entity_id = record["entity_id"]
            object_id = entity_id.partition(".")[2]
            normalized_name = _normalize(record["name"])

            if normalized_query == _normalize(entity_id):
                score += 1000
                reasons.append("exact entity_id")
            elif normalized_query == _normalize(object_id):
                score += 850
                reasons.append("exact object_id")
            if normalized_query and normalized_query == normalized_name:
                score += 800
                reasons.append("exact name")
            elif search_query and search_query in record["search_entity"]:
                score += 260
                reasons.append("name phrase")

            matched_entity = sum(
                1
                for token in query_tokens
                if any(_token_matches(token, item) for item in record["search_entity"].split())
            )
            matched_device = sum(
                1
                for token in query_tokens
                if any(_token_matches(token, item) for item in record["search_device"].split())
            )
            matched_area = sum(
                1
                for token in query_tokens
                if any(_token_matches(token, item) for item in record["search_area"].split())
            )
            if matched_entity:
                score += matched_entity * 70
                reasons.append("entity name")
            if matched_device:
                score += matched_device * 55
                reasons.append("device name")
            if matched_area:
                score += matched_area * 90
                reasons.append("area")
            matched_identity = sum(
                1
                for token in identity_tokens
                if any(
                    _token_matches(token, item)
                    for item in (record["search_entity"] + " " + record["search_device"]).split()
                )
            )
            if matched_identity:
                score += matched_identity * 180
                reasons.append("specific name")
            if record["domain"] in hinted_domains:
                score += 130
                reasons.append(f"domain {record['domain']}")
            if record.get("device_class") in hinted_classes:
                score += 190
                reasons.append(f"device_class {record['device_class']}")
            if "battery" in hinted_classes and "battery_level" in record["attributes"]:
                score += 150
                reasons.append("battery attribute")
            if domain_boosts and record["domain"] in domain_boosts:
                score += domain_boosts[record["domain"]]
                reasons.append(f"preferred domain {record['domain']}")
            if record.get("state") is not None:
                score += 40
                reasons.append("loaded state")
            if record["registry"].get("disabled_by"):
                score -= 250

            if score > 0:
                ranked.append((score, record, list(dict.fromkeys(reasons))))

        ranked.sort(key=lambda item: (-item[0], item[1]["entity_id"]))
        return ranked

    def _resolve_entity(
        self,
        snapshot: dict[str, Any],
        query: str,
        *,
        domains: set[str] | None = None,
    ) -> tuple[dict[str, Any] | None, list[tuple[int, dict[str, Any], list[str]]], bool]:
        ranked = self._rank_entities(snapshot, query, domains=domains)
        if not ranked:
            return None, [], False
        top = ranked[0]
        ambiguous = len(ranked) > 1 and ranked[1][0] >= top[0] - 20
        return top[1], ranked, ambiguous

    def _summary(
        self,
        record: dict[str, Any],
        *,
        score: int | None = None,
        reasons: list[str] | None = None,
    ) -> dict[str, Any]:
        state = record.get("state")
        if state in {"unavailable", "unknown"}:
            availability = state
        elif state is None:
            availability = "not_loaded"
        else:
            availability = "available"
        result = {
            "entity_id": record["entity_id"],
            "name": record["name"],
            "domain": record["domain"],
            "state": state,
            "availability": availability,
            "device_class": record.get("device_class"),
            "device": (
                {"id": record["device_id"], "name": record["device_name"]}
                if record.get("device_id")
                else None
            ),
            "area": (
                {"id": record["area_id"], "name": record["area_name"]}
                if record.get("area_id")
                else None
            ),
            "last_updated": record.get("last_updated"),
            "attributes": _public_attributes(record.get("attributes") or {}),
        }
        if score is not None:
            result["match_score"] = score
            result["match_reasons"] = reasons or []
        return result

    def find_entities(self, query: str, domain: str = "", limit: int = 20) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("query is required")
        domains = {domain.strip().lower()} if domain.strip() else None
        limit = max(1, min(limit, 100))
        snapshot = self.snapshot()
        ranked = self._rank_entities(snapshot, query, domains=domains)
        matches = [
            self._summary(record, score=score, reasons=reasons)
            for score, record, reasons in ranked[:limit]
        ]
        ambiguous = len(ranked) > 1 and ranked[1][0] >= ranked[0][0] - 20
        return {
            "status": "ok",
            "query": query,
            "match_count": len(matches),
            "ambiguous": ambiguous,
            "registry_available": snapshot["registry_available"],
            "matches": matches,
        }

    def get_entity_state(self, entity_id: str) -> dict[str, Any]:
        snapshot = self.snapshot()
        record, ranked, ambiguous = self._resolve_entity(snapshot, entity_id)
        if record is None:
            return {"status": "not_found", "query": entity_id, "candidates": []}
        if ambiguous:
            return {
                "status": "ambiguous",
                "query": entity_id,
                "candidates": [
                    self._summary(item, score=score, reasons=reasons)
                    for score, item, reasons in ranked[:10]
                ],
            }
        return {
            "status": "ok",
            "resolved_from": entity_id,
            **self._summary(record),
            "attributes": record["attributes"],
            "last_changed": record.get("last_changed"),
            "registry": {
                "platform": record["registry"].get("platform"),
                "disabled_by": record["registry"].get("disabled_by"),
                "hidden_by": record["registry"].get("hidden_by"),
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
        snapshot = self.snapshot()
        domain = domain.strip().lower()
        area_search = _searchable(area)
        device_search = _searchable(device)
        states = {_normalize(value) for value in state.split(",") if value.strip()}
        limit = max(1, min(limit, 500))
        matches = []
        total = 0
        for record in snapshot["records"]:
            if domain and record["domain"] != domain:
                continue
            if area_search and not _field_matches(area, record["search_area"]):
                continue
            if device_search and not _field_matches(device, record["search_device"]):
                continue
            if states and _normalize(record.get("state")) not in states:
                continue
            total += 1
            if len(matches) < limit:
                matches.append(self._summary(record))
        return {
            "status": "ok",
            "filters": {"domain": domain, "area": area, "device": device, "state": state},
            "match_count": total,
            "returned_count": len(matches),
            "truncated": total > len(matches),
            "registry_available": snapshot["registry_available"],
            "entities": matches,
        }

    def get_device(self, device_id: str = "", name: str = "") -> dict[str, Any]:
        query = (device_id or name).strip()
        if not query:
            raise ValueError("device_id or name is required")
        snapshot = self.snapshot()
        ranked = []
        for candidate_id, device in snapshot["devices"].items():
            candidate_name = device.get("name_by_user") or device.get("name") or candidate_id
            search = _searchable(candidate_id, candidate_name, *(_as_list(device.get("aliases"))))
            score = 0
            if _normalize(query) == _normalize(candidate_id):
                score = 1000
            elif _normalize(query) == _normalize(candidate_name):
                score = 800
            elif _searchable(query) in search:
                score = 300
            else:
                score = sum(
                    60
                    for token in _tokens(query)
                    if any(_token_matches(token, item) for item in search.split())
                )
            if score:
                ranked.append((score, candidate_id, candidate_name, device))
        ranked.sort(key=lambda item: (-item[0], item[1]))
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
            self._summary(record)
            for record in snapshot["records"]
            if record.get("device_id") == resolved_id
        ]
        area_id = device.get("area_id")
        area = snapshot["areas"].get(str(area_id)) if area_id else None
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
        snapshot = self.snapshot()
        prefer_person = not _contains_term(
            person_id,
            {"phone", "tracker", "телефон", "трекер"},
        )
        ranked = self._rank_entities(
            snapshot,
            person_id,
            domains={"person", "device_tracker"},
            domain_boosts={"person": 180} if prefer_person else {"device_tracker": 180},
        )
        record = ranked[0][1] if ranked else None
        ambiguous = len(ranked) > 1 and ranked[1][0] >= ranked[0][0] - 20
        if record is None:
            return {"status": "not_found", "query": person_id, "candidates": []}
        if ambiguous:
            return {
                "status": "ambiguous",
                "query": person_id,
                "candidates": [
                    self._summary(item, score=score, reasons=reasons)
                    for score, item, reasons in ranked[:10]
                ],
            }

        attributes = record["attributes"]
        latitude = self._coordinate_or_none(attributes.get("latitude"), -90, 90)
        longitude = self._coordinate_or_none(attributes.get("longitude"), -180, 180)
        gps_accuracy = self._coordinate_or_none(attributes.get("gps_accuracy"), 0, math.inf)
        address = attributes.get("formatted_address") or attributes.get("address")
        address_details = None
        reverse_geocoding = None
        if not address and latitude is not None and longitude is not None:
            try:
                geocoded = self.client.reverse_geocode(latitude, longitude)
            except RuntimeError:
                geocoded = None
            if geocoded:
                address = geocoded.get("display_name")
                address_details = geocoded.get("address")
                reverse_geocoding = "configured MCP geocoder"
        raw_state = record.get("state")
        reserved_states = {"not_home", "unknown", "unavailable"}
        zone = raw_state if raw_state and raw_state not in reserved_states else None
        result = {
            "status": "ok",
            "resolved_from": person_id,
            "entity_id": record["entity_id"],
            "name": record["name"],
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
            "last_updated": record.get("last_updated"),
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

    @staticmethod
    def _coordinate_or_none(value: Any, minimum: float, maximum: float) -> float | None:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return result if math.isfinite(result) and minimum <= result <= maximum else None

    def get_entity_history(
        self,
        entity_id: str,
        start: str = "",
        end: str = "",
        hours: int = 24,
        limit: int = 500,
        minimal_response: bool = True,
    ) -> dict[str, Any]:
        snapshot = self.snapshot()
        record, ranked, ambiguous = self._resolve_entity(snapshot, entity_id)
        if record is None:
            return {"status": "not_found", "query": entity_id, "candidates": []}
        if ambiguous:
            return {
                "status": "ambiguous",
                "query": entity_id,
                "candidates": [
                    self._summary(item, score=score, reasons=reasons)
                    for score, item, reasons in ranked[:10]
                ],
            }

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
        history = self.client.get_history(
            record["entity_id"],
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
            "entity_id": record["entity_id"],
            "name": record["name"],
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "point_count": len(points),
            "truncated": len(history) > len(points),
            "points": points,
        }
