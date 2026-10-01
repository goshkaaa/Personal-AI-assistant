"""Composition root for Calendar application services and adapters."""

from functools import cached_property

from .application.accounts import CalendarService
from .application.commit_service import CalendarCommitService
from .application.proposal_service import CalendarProposalService
from .application.queries import CalendarQueryService
from .config import Settings, get_settings
from .infrastructure.client_factory import DefaultCalendarClientFactory
from .infrastructure.proposal_store import ProposalStore, secure_database_permissions


class CalendarContainer:
    """Build one reusable dependency graph per MCP process."""

    @cached_property
    def settings(self) -> Settings:
        return get_settings()

    @cached_property
    def account_service(self) -> CalendarService:
        return CalendarService(self.settings, factory=DefaultCalendarClientFactory())

    @cached_property
    def proposal_store(self) -> ProposalStore:
        return ProposalStore(self.settings.state_db)

    @cached_property
    def query_service(self) -> CalendarQueryService:
        return CalendarQueryService(
            self.settings,
            self.account_service,
            lambda: secure_database_permissions(self.settings.state_db),
        )

    @cached_property
    def proposal_service(self) -> CalendarProposalService:
        return CalendarProposalService(self.settings, self.account_service, self.proposal_store)

    @cached_property
    def commit_service(self) -> CalendarCommitService:
        return CalendarCommitService(self.account_service, self.proposal_store)
