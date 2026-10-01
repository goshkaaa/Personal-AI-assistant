"""Natural-language normalization used by entity resolution."""

import re
from typing import Any

CYRILLIC_TO_LATIN = str.maketrans(
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

STOP_WORDS = {
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

DOMAIN_TERMS = {
    "light": {"light", "lamp", "свет", "ламп"},
    "person": {"person", "people", "человек", "где", "where"},
    "device_tracker": {"phone", "tracker", "телефон", "трекер", "где", "where"},
    "lock": {"lock", "locked", "замок", "заперт"},
    "binary_sensor": {"door", "window", "двер", "окн"},
    "climate": {"thermostat", "climate", "термостат", "климат"},
}

DEVICE_CLASS_TERMS = {
    "battery": {"battery", "charge", "level", "батаре", "заряд"},
    "temperature": {"temperature", "temp", "температур"},
    "door": {"door", "двер"},
    "window": {"window", "окн"},
    "opening": {"open", "closed", "открыт", "закрыт"},
}


class TextSearch:
    """Normalizes Russian/English names and performs tolerant token matching."""

    def __init__(self) -> None:
        self.domain_terms = DOMAIN_TERMS
        self.device_class_terms = DEVICE_CLASS_TERMS
        self.semantic_tokens = self._build_semantic_tokens()

    @staticmethod
    def normalize(value: Any) -> str:
        text = str(value or "").casefold().replace("ё", "е")
        return " ".join(re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).split())

    def searchable(self, *values: Any) -> str:
        original = self.normalize(" ".join(str(value or "") for value in values))
        transliterated = self.normalize(original.translate(CYRILLIC_TO_LATIN))
        return f"{original} {transliterated}".strip()

    def tokens(self, value: Any) -> set[str]:
        return {token for token in self.searchable(value).split() if token not in STOP_WORDS}

    @staticmethod
    def token_matches(needle: str, candidate: str) -> bool:
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
        return common_prefix >= 4 and (common_prefix / min(len(needle), len(candidate)) >= 0.65)

    def contains_term(self, query: str, terms: set[str]) -> bool:
        haystack = self.searchable(query)
        return any(self.normalize(term) in haystack for term in terms)

    def field_matches(self, query: str, field: str) -> bool:
        query_text = self.searchable(query)
        field_text = self.searchable(field)
        if not query_text:
            return True
        if query_text in field_text:
            return True
        query_tokens = self.tokens(query)
        field_tokens = self.tokens(field)
        return bool(query_tokens) and all(
            any(self.token_matches(query_token, field_token) for field_token in field_tokens)
            for query_token in query_tokens
        )

    def _build_semantic_tokens(self) -> set[str]:
        result: set[str] = set()
        for terms in (*self.domain_terms.values(), *self.device_class_terms.values()):
            for term in terms:
                result.update(self.tokens(term))
        return result
