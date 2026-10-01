"""Explainable natural-language entity ranking."""

from __future__ import annotations

from ..domain.models import (
    EntityMatch,
    EntityRecord,
    EntityResolution,
    RegistrySnapshot,
)
from .text_search import TextSearch


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


class EntityMatcher:
    """Ranks HA entities without depending on transport or MCP concerns."""

    def __init__(self, text: TextSearch | None = None) -> None:
        self.text = text or TextSearch()

    def rank(
        self,
        snapshot: RegistrySnapshot,
        query: str,
        *,
        domains: set[str] | None = None,
        domain_boosts: dict[str, int] | None = None,
    ) -> list[EntityMatch]:
        query = query.strip()
        normalized_query = self.text.normalize(query)
        search_query = self.text.searchable(query)
        query_tokens = self.text.tokens(query)
        hinted_domains = {
            domain
            for domain, terms in self.text.domain_terms.items()
            if self.text.contains_term(query, terms)
        }
        hinted_classes = {
            device_class
            for device_class, terms in self.text.device_class_terms.items()
            if self.text.contains_term(query, terms)
        }
        identity_tokens = {
            token
            for token in query_tokens
            if not any(
                self.text.token_matches(token, semantic) for semantic in self.text.semantic_tokens
            )
        }
        matched_area_ids = self._matched_area_ids(snapshot, query_tokens)

        ranked: list[EntityMatch] = []
        for record in snapshot.records:
            if not self._eligible(
                record,
                domains=domains,
                matched_area_ids=matched_area_ids,
                hinted_domains=hinted_domains,
                hinted_classes=hinted_classes,
            ):
                continue
            score, reasons = self._score(
                record,
                normalized_query=normalized_query,
                search_query=search_query,
                query_tokens=query_tokens,
                identity_tokens=identity_tokens,
                hinted_domains=hinted_domains,
                hinted_classes=hinted_classes,
                domain_boosts=domain_boosts or {},
            )
            if score > 0:
                ranked.append(EntityMatch(score, record, tuple(dict.fromkeys(reasons))))

        ranked.sort(key=lambda match: (-match.score, match.record.entity_id))
        return ranked

    def resolve(
        self,
        snapshot: RegistrySnapshot,
        query: str,
        *,
        domains: set[str] | None = None,
    ) -> EntityResolution:
        matches = tuple(self.rank(snapshot, query, domains=domains))
        if not matches:
            return EntityResolution(None, (), False)
        ambiguous = len(matches) > 1 and matches[1].score >= matches[0].score - 20
        return EntityResolution(matches[0].record, matches, ambiguous)

    def _matched_area_ids(
        self,
        snapshot: RegistrySnapshot,
        query_tokens: set[str],
    ) -> set[str]:
        return {
            area_id
            for area_id, area in snapshot.areas.items()
            if any(
                self.text.token_matches(query_token, area_token)
                for query_token in query_tokens
                for area_token in self.text.tokens(
                    " ".join(
                        [
                            str(area.get("name") or ""),
                            *[str(value) for value in _as_list(area.get("aliases"))],
                        ]
                    )
                )
            )
        }

    @staticmethod
    def _eligible(
        record: EntityRecord,
        *,
        domains: set[str] | None,
        matched_area_ids: set[str],
        hinted_domains: set[str],
        hinted_classes: set[str],
    ) -> bool:
        if domains and record.domain not in domains:
            return False
        if matched_area_ids and record.area_id not in matched_area_ids:
            return False
        if hinted_classes:
            return bool(
                record.device_class in hinted_classes
                or ("battery" in hinted_classes and "battery_level" in record.attributes)
                or record.domain in hinted_domains
            )
        return not hinted_domains or record.domain in hinted_domains

    def _score(
        self,
        record: EntityRecord,
        *,
        normalized_query: str,
        search_query: str,
        query_tokens: set[str],
        identity_tokens: set[str],
        hinted_domains: set[str],
        hinted_classes: set[str],
        domain_boosts: dict[str, int],
    ) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []
        object_id = record.entity_id.partition(".")[2]
        normalized_name = self.text.normalize(record.name)

        if normalized_query == self.text.normalize(record.entity_id):
            score += 1000
            reasons.append("exact entity_id")
        elif normalized_query == self.text.normalize(object_id):
            score += 850
            reasons.append("exact object_id")
        if normalized_query and normalized_query == normalized_name:
            score += 800
            reasons.append("exact name")
        elif search_query and search_query in record.search_entity:
            score += 260
            reasons.append("name phrase")

        matched_entity = self._matched_tokens(query_tokens, record.search_entity)
        matched_device = self._matched_tokens(query_tokens, record.search_device)
        matched_area = self._matched_tokens(query_tokens, record.search_area)
        if matched_entity:
            score += matched_entity * 70
            reasons.append("entity name")
        if matched_device:
            score += matched_device * 55
            reasons.append("device name")
        if matched_area:
            score += matched_area * 90
            reasons.append("area")

        matched_identity = self._matched_tokens(
            identity_tokens,
            f"{record.search_entity} {record.search_device}",
        )
        if matched_identity:
            score += matched_identity * 180
            reasons.append("specific name")
        if record.domain in hinted_domains:
            score += 130
            reasons.append(f"domain {record.domain}")
        if record.device_class in hinted_classes:
            score += 190
            reasons.append(f"device_class {record.device_class}")
        if "battery" in hinted_classes and "battery_level" in record.attributes:
            score += 150
            reasons.append("battery attribute")
        if record.domain in domain_boosts:
            score += domain_boosts[record.domain]
            reasons.append(f"preferred domain {record.domain}")
        if record.state is not None:
            score += 40
            reasons.append("loaded state")
        if record.registry.get("disabled_by"):
            score -= 250
        return score, reasons

    def _matched_tokens(self, query_tokens: set[str], searchable: str) -> int:
        candidates = searchable.split()
        return sum(
            1
            for token in query_tokens
            if any(self.text.token_matches(token, candidate) for candidate in candidates)
        )
