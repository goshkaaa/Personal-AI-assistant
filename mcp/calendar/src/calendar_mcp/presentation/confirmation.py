"""Interactive MCP elicitation adapter for calendar write confirmation."""

from __future__ import annotations

import json

from mcp.server.mcpserver import Context
from pydantic import BaseModel

from ..domain.ports import ConfirmationResult, ProposalRecord


class EmptyConfirmation(BaseModel):
    """The client confirms elicitation as an empty accepted form."""


class McpConfirmationGateway:
    def __init__(self, context: Context) -> None:
        self.context = context

    async def confirm(self, proposal: ProposalRecord) -> ConfirmationResult:
        try:
            decision = await self.context.elicit(
                confirmation_message(proposal),
                schema=EmptyConfirmation,
            )
        except Exception:
            return ConfirmationResult.UNAVAILABLE
        if decision.action == "accept":
            return ConfirmationResult.ACCEPTED
        return ConfirmationResult.DECLINED


def confirmation_message(proposal: ProposalRecord) -> str:
    payload = proposal.payload
    if proposal.action == "delete":
        return "\n".join(
            [
                "Удалить это событие из календаря без возможности отмены?",
                f"Аккаунт: {_quoted(proposal.account_id)}",
                f"Календарь: {_quoted(payload['calendar_name'])}",
                f"Название: {_quoted(payload['title'])}",
                f"Начало: {_quoted(payload['start'])}",
                f"Конец: {_quoted(payload['end'])}",
                f"Весь день: {'да' if payload['all_day'] else 'нет'}",
                "После подтверждения событие будет удалено без возможности отмены.",
            ]
        )
    lines = [
        "Создать это событие в календаре?",
        f"Аккаунт: {_quoted(proposal.account_id)}",
        f"Календарь: {_quoted(payload['calendar_name'])}",
        f"Название: {_quoted(payload['title'])}",
        f"Начало: {_quoted(payload['start'])}",
        f"Конец: {_quoted(payload['end'])}",
        f"Весь день: {'да' if payload['all_day'] else 'нет'}",
        f"Часовой пояс: {_quoted(payload['timezone'])}",
    ]
    if payload.get("location"):
        lines.append(f"Место: {_quoted(payload['location'])}")
    if payload.get("description"):
        lines.append(f"Описание: {_quoted(payload['description'])}")
    conflicts = int(payload.get("conflict_count", 0))
    lines.append(f"Пересечений с занятыми событиями: {conflicts}")
    lines.append("После подтверждения параметры не изменятся.")
    return "\n".join(lines)


def _quoted(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)
