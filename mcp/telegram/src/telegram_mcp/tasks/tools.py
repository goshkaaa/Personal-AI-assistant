"""Autonomous task MCP tool registration."""

import json

from mcp.server.mcpserver import MCPServer

from ..client import create_client
from ..serializers import normalize_peer
from .conversations import conversations
from .task_repository import task_repository


def register_task_tools(mcp: MCPServer) -> None:
    """Attach persistent task management tools to the application server."""

    @mcp.tool()
    def task_create(
        title: str,
        goal: str,
        required_fields: list[str] | None = None,
    ) -> dict:
        """Create a persistent autonomous outreach/conversation task."""
        title = title.strip()
        goal = goal.strip()
        if not title:
            raise ValueError("title cannot be empty")
        if not goal:
            raise ValueError("goal cannot be empty")

        fields = [str(value).strip() for value in (required_fields or []) if str(value).strip()]
        task_id = task_repository.create(
            title=title,
            goal=goal,
            required_fields=json.dumps(fields, ensure_ascii=False),
            silent_mode=True,
        )
        return {
            "task_id": task_id,
            "title": title,
            "goal": goal,
            "required_fields": fields,
            "status": "ACTIVE",
            "silent_mode": True,
        }

    @mcp.tool()
    def task_attach_chat(task_id: int, chat_id: str) -> dict:
        """Attach an existing Telegram conversation to an autonomous task."""
        peer = normalize_peer(chat_id)
        if not isinstance(peer, int):
            try:
                with create_client() as app:
                    peer = app.get_chat(peer).id
            except Exception as exc:
                raise RuntimeError(
                    f"Could not resolve Telegram chat: {type(exc).__name__}: {exc}"
                ) from exc

        task_repository.attach(task_id=int(task_id), chat_id=int(peer))
        conversations.mark_managed(int(peer), None, None, f"autonomous_task_{task_id}")
        return {
            "task_id": int(task_id),
            "chat_id": int(peer),
            "state": "SILENT",
            "attached": True,
        }

    @mcp.tool()
    def task_list(status: str = "ACTIVE") -> list[dict]:
        """List persistent autonomous tasks by status."""
        status = status.strip().upper()
        if status == "ALL":
            rows = task_repository.list_tasks()
        else:
            if status not in {"ACTIVE", "DONE", "CANCELLED"}:
                raise ValueError("status must be ACTIVE, DONE, CANCELLED, or ALL")
            rows = task_repository.list_tasks(status=status)
        return rows

    @mcp.tool()
    def task_status(task_id: int) -> dict:
        """Get full task status and the state of each attached contact."""
        return task_repository.status(task_id)

    @mcp.tool()
    def task_cancel(task_id: int) -> dict:
        """Cancel a task and deactivate its autonomous conversations."""
        task_repository.cancel(task_id)
        return {"task_id": int(task_id), "status": "CANCELLED"}
