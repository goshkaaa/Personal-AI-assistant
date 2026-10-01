"""Thin MCP tool adapters over injected calendar application services."""

from __future__ import annotations

from typing import Protocol

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations

from ..application.commit_service import CalendarCommitService
from ..application.proposal_service import CalendarProposalService
from ..application.queries import CalendarQueryService
from .confirmation import McpConfirmationGateway
from .errors import public_error

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
PREPARE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)
COMMIT = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
DELETE_COMMIT = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=True,
    openWorldHint=True,
)


class CalendarDependencies(Protocol):
    query_service: CalendarQueryService
    proposal_service: CalendarProposalService
    commit_service: CalendarCommitService


class CalendarToolRegistry:
    """Expose the stable Calendar tool contract without business logic."""

    def __init__(self, dependencies: CalendarDependencies) -> None:
        self.dependencies = dependencies

    def register(self, server: MCPServer) -> None:
        server.tool(annotations=READ_ONLY)(self.calendar_status)
        server.tool(annotations=READ_ONLY)(self.calendar_list_accounts)
        server.tool(annotations=READ_ONLY)(self.calendar_list_calendars)
        server.tool(annotations=READ_ONLY)(self.calendar_list_events)
        server.tool(annotations=READ_ONLY)(self.calendar_find_free_slots)
        server.tool(annotations=PREPARE)(self.calendar_prepare_delete_event)
        server.tool(annotations=PREPARE)(self.calendar_prepare_event)
        server.tool(annotations=COMMIT)(self.calendar_commit_event)
        server.tool(annotations=DELETE_COMMIT)(self.calendar_commit_delete_event)

    def calendar_status(self, account_id: str | None = None) -> dict[str, object]:
        """Show local calendar configuration without connecting or exposing secrets."""
        try:
            return self.dependencies.query_service.status(account_id)
        except Exception as exc:
            return public_error(exc)

    def calendar_list_accounts(self) -> dict[str, object]:
        """List configured calendar accounts and their non-secret local status."""
        try:
            return self.dependencies.query_service.list_accounts()
        except Exception as exc:
            return public_error(exc)

    async def calendar_list_calendars(
        self,
        account_id: str | None = None,
    ) -> dict[str, object]:
        """List calendars and opaque ids for one account."""
        try:
            return await self.dependencies.query_service.list_calendars(account_id)
        except Exception as exc:
            return public_error(exc)

    async def calendar_list_events(
        self,
        start: str,
        end: str,
        calendar_id: str = "",
        query: str = "",
        include_notes: bool = False,
        limit: int = 100,
        account_id: str | None = None,
    ) -> dict[str, object]:
        """List events in a closed, bounded range for one account."""
        try:
            return await self.dependencies.query_service.list_events(
                start,
                end,
                calendar_id,
                query,
                include_notes,
                limit,
                account_id,
            )
        except Exception as exc:
            return public_error(exc)

    async def calendar_find_free_slots(
        self,
        start: str,
        end: str,
        duration_minutes: int,
        calendar_id: str = "",
        working_hours_start: str = "09:00",
        working_hours_end: str = "18:00",
        weekdays_only: bool = True,
        limit: int = 30,
        account_id: str | None = None,
    ) -> dict[str, object]:
        """Find free intervals in one account, merging busy events."""
        try:
            return await self.dependencies.query_service.find_free_slots(
                start,
                end,
                duration_minutes,
                calendar_id,
                working_hours_start,
                working_hours_end,
                weekdays_only,
                limit,
                account_id,
            )
        except Exception as exc:
            return public_error(exc)

    async def calendar_prepare_delete_event(
        self,
        event_id: str,
        start: str,
        end: str,
        calendar_id: str = "",
        account_id: str | None = None,
    ) -> dict[str, object]:
        """Prepare deletion of one exact event; this does not delete it."""
        try:
            return await self.dependencies.proposal_service.prepare_delete_event(
                event_id,
                start,
                end,
                calendar_id,
                account_id,
            )
        except Exception as exc:
            return public_error(exc)

    async def calendar_prepare_event(
        self,
        title: str,
        start: str,
        end: str,
        all_day: bool = False,
        location: str = "",
        description: str = "",
        account_id: str | None = None,
    ) -> dict[str, object]:
        """Prepare, but do not create, an event."""
        try:
            return await self.dependencies.proposal_service.prepare_event(
                title,
                start,
                end,
                all_day,
                location,
                description,
                account_id,
            )
        except Exception as exc:
            return public_error(exc)

    async def calendar_commit_event(
        self,
        proposal_id: str,
        ctx: Context,
    ) -> dict[str, object]:
        """Create one prepared event after policy checks and human approval."""
        try:
            return await self.dependencies.commit_service.commit_event(
                proposal_id,
                McpConfirmationGateway(ctx),
            )
        except Exception as exc:
            return public_error(exc)

    async def calendar_commit_delete_event(
        self,
        proposal_id: str,
        ctx: Context,
    ) -> dict[str, object]:
        """Permanently delete one prepared event after human approval."""
        try:
            return await self.dependencies.commit_service.commit_delete_event(
                proposal_id,
                McpConfirmationGateway(ctx),
            )
        except Exception as exc:
            return public_error(exc)


def register_tools(server: MCPServer, dependencies: CalendarDependencies) -> None:
    CalendarToolRegistry(dependencies).register(server)
