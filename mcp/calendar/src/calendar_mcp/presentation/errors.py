"""Stable public error mapping for Calendar MCP tools."""

from ..config import ConfigurationError
from ..logic import InputError
from ..models import CalendarServiceError


def public_error(exc: Exception) -> dict[str, object]:
    if isinstance(exc, CalendarServiceError):
        return {"status": "error", "code": exc.code, "message": exc.message}
    if isinstance(exc, ConfigurationError):
        return {"status": "not_configured", "code": "configuration", "message": str(exc)}
    if isinstance(exc, InputError):
        return {"status": "invalid_input", "code": "validation", "message": str(exc)}
    return {
        "status": "error",
        "code": "internal_error",
        "message": f"Calendar operation failed ({type(exc).__name__})",
    }
