"""Calendar domain contracts shared by application and adapters."""

from .ports import (
    CalendarClient,
    CalendarClientFactory,
    ConfirmationGateway,
    ConfirmationResult,
    ProposalRecord,
    ProposalRepository,
)

__all__ = [
    "CalendarClient",
    "CalendarClientFactory",
    "ConfirmationGateway",
    "ConfirmationResult",
    "ProposalRecord",
    "ProposalRepository",
]
