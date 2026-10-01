"""Map domain entities to stable MCP response dictionaries."""

from typing import Any

from ..domain.models import EntityMatch, EntityRecord

PUBLIC_ATTRIBUTE_KEYS = (
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


class EntityPresenter:
    """Centralizes the public entity DTO contract."""

    @staticmethod
    def public_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
        return {key: attributes[key] for key in PUBLIC_ATTRIBUTE_KEYS if key in attributes}

    def summary(
        self,
        record: EntityRecord,
        match: EntityMatch | None = None,
    ) -> dict[str, Any]:
        state = record.state
        if state in {"unavailable", "unknown"}:
            availability = state
        elif state is None:
            availability = "not_loaded"
        else:
            availability = "available"
        result = {
            "entity_id": record.entity_id,
            "name": record.name,
            "domain": record.domain,
            "state": state,
            "availability": availability,
            "device_class": record.device_class,
            "device": (
                {"id": record.device_id, "name": record.device_name} if record.device_id else None
            ),
            "area": ({"id": record.area_id, "name": record.area_name} if record.area_id else None),
            "last_updated": record.last_updated,
            "attributes": self.public_attributes(record.attributes),
        }
        if match is not None:
            result["match_score"] = match.score
            result["match_reasons"] = list(match.reasons)
        return result
