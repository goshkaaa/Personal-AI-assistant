"""Confirmed and idempotent calendar write use cases."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

from ..config import CalendarAccountSettings, ConfigurationError
from ..domain.ports import (
    CalendarClient,
    ConfirmationGateway,
    ConfirmationResult,
    ProposalRecord,
    ProposalRepository,
)
from ..logic import clean_text
from ..models import CalendarServiceError
from .accounts import CalendarService


class CalendarCommitService:
    """Validate, confirm, and execute prepared calendar writes."""

    def __init__(
        self,
        accounts: CalendarService,
        proposals: ProposalRepository,
    ) -> None:
        self.accounts = accounts
        self.proposals = proposals

    async def commit_event(
        self,
        proposal_id: str,
        confirmation: ConfirmationGateway,
    ) -> dict[str, object]:
        proposal = self._proposal(proposal_id)
        if isinstance(proposal, dict):
            return proposal
        guard = self._guard(proposal, expected_action="create", completed_status="created")
        if guard is not None:
            return guard
        target = self._write_target(proposal)
        if isinstance(target, dict):
            return target
        account, client = target
        confirmation_failure = await self._confirmation_failure(confirmation, proposal)
        if confirmation_failure is not None:
            return confirmation_failure

        try:
            uid, recovered = await asyncio.to_thread(
                client.create_event,
                proposal.payload,
                uid=proposal.uid,
            )
        except Exception as exc:
            self.proposals.record_failure(
                account_id=proposal.account_id,
                calendar_id=proposal.calendar_id,
                uid=proposal.uid,
                result=self._error_code(exc),
            )
            raise

        receipt: dict[str, object] = {
            "account_id": account.account_id,
            "provider": account.provider,
            "calendar_id": proposal.calendar_id,
            "uid": uid,
            "created_at": datetime.now(UTC).isoformat(),
            "recovered_existing": recovered,
        }
        self.proposals.mark_committed(
            proposal.proposal_id,
            account_id=proposal.account_id,
            calendar_id=proposal.calendar_id,
            uid=uid,
            receipt=receipt,
            result="recovered_existing" if recovered else "created",
        )
        return {"status": "created", "idempotent_replay": recovered, "receipt": receipt}

    async def commit_delete_event(
        self,
        proposal_id: str,
        confirmation: ConfirmationGateway,
    ) -> dict[str, object]:
        proposal = self._proposal(proposal_id)
        if isinstance(proposal, dict):
            return proposal
        guard = self._guard(proposal, expected_action="delete", completed_status="deleted")
        if guard is not None:
            return guard
        target = self._write_target(proposal)
        if isinstance(target, dict):
            return target
        account, client = target
        confirmation_failure = await self._confirmation_failure(confirmation, proposal)
        if confirmation_failure is not None:
            return confirmation_failure

        try:
            deleted = await asyncio.to_thread(
                client.delete_event,
                proposal.calendar_id,
                proposal.target_ref,
            )
        except Exception as exc:
            self.proposals.record_failure(
                action="delete",
                account_id=proposal.account_id,
                calendar_id=proposal.calendar_id,
                uid=proposal.target_ref,
                result=self._error_code(exc),
            )
            raise

        receipt: dict[str, object] = {
            "account_id": account.account_id,
            "provider": account.provider,
            "calendar_id": proposal.calendar_id,
            "event_id": proposal.payload["event_id"],
            "deleted_at": datetime.now(UTC).isoformat(),
            "already_absent": not deleted,
        }
        self.proposals.mark_committed(
            proposal.proposal_id,
            action="delete",
            account_id=proposal.account_id,
            calendar_id=proposal.calendar_id,
            uid=proposal.target_ref,
            receipt=receipt,
            result="deleted" if deleted else "already_absent",
        )
        return {"status": "deleted", "idempotent_replay": not deleted, "receipt": receipt}

    def _proposal(self, proposal_id: str) -> ProposalRecord | dict[str, object]:
        proposal_id = clean_text(proposal_id, field="proposal_id", maximum=128, required=True)
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            return {
                "status": "not_found",
                "message": "Calendar proposal was not found or has already been purged",
            }
        return proposal

    @staticmethod
    def _guard(
        proposal: ProposalRecord,
        *,
        expected_action: str,
        completed_status: str,
    ) -> dict[str, object] | None:
        if proposal.action != expected_action:
            noun = "creation" if expected_action == "create" else "deletion"
            return {
                "status": "rejected",
                "message": f"This proposal is not an event-{noun} proposal",
            }
        if proposal.receipt is not None:
            return {
                "status": completed_status,
                "idempotent_replay": True,
                "receipt": proposal.receipt,
            }
        if proposal.expires_at < int(time.time()):
            return {
                "status": "expired",
                "message": "Calendar proposal expired; prepare it again from current data",
            }
        return None

    def _write_target(
        self,
        proposal: ProposalRecord,
    ) -> tuple[CalendarAccountSettings, CalendarClient] | dict[str, object]:
        account, client = self.accounts.resolve(proposal.account_id)
        if not account.write_enabled:
            return {
                "status": "disabled",
                "message": f"Calendar writes are disabled for account {account.account_id!r}",
            }
        if not account.write_calendar_id:
            raise ConfigurationError(
                f"write_calendar_id is not configured for account {account.account_id!r}"
            )
        if proposal.calendar_id != account.write_calendar_id:
            return {
                "status": "rejected",
                "message": "Proposal target does not match the account's writable calendar",
            }
        return account, client

    @staticmethod
    async def _confirmation_failure(
        confirmation: ConfirmationGateway,
        proposal: ProposalRecord,
    ) -> dict[str, object] | None:
        decision = await confirmation.confirm(proposal)
        outcome = "deleted" if proposal.action == "delete" else "created"
        if decision is ConfirmationResult.UNAVAILABLE:
            return {
                "status": "confirmation_unavailable",
                "message": f"Interactive confirmation was unavailable; nothing was {outcome}",
            }
        if decision is ConfirmationResult.DECLINED:
            return {
                "status": "declined",
                "message": f"User did not approve the event; nothing was {outcome}",
            }
        return None

    @staticmethod
    def _error_code(exc: Exception) -> str:
        return str(exc.code if isinstance(exc, CalendarServiceError) else type(exc).__name__)
