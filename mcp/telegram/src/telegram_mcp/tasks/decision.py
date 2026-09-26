"""Hermes subprocess adapter for one autonomous conversation decision."""

import json
import os
import subprocess
from pathlib import Path

from ..config import env_path, load_env

ALLOWED_ACTIONS = {"WAIT", "REPLY", "NEEDS_USER", "COMPLETE"}


class HermesDecisionClient:
    def __init__(self, command: str, profile_home: Path, system_home: Path) -> None:
        self.command = command
        self.profile_home = profile_home
        self.system_home = system_home

    @classmethod
    def from_env(cls) -> "HermesDecisionClient":
        load_env()
        system_home = env_path("MCP_SYSTEM_HOME", Path.home())
        profile_name = os.environ.get(
            "HERMES_PROFILE_NAME",
            os.environ.get("TG_SESSION_NAME", "default"),
        )
        return cls(
            command=os.environ.get("HERMES_COMMAND", "hermes").strip() or "hermes",
            profile_home=env_path(
                "HERMES_PROFILE_HOME",
                system_home / ".hermes" / "profiles" / profile_name,
            ),
            system_home=system_home,
        )

    def decide(self, event: dict, history: list[dict]) -> dict:
        context = {
            "task": {
                "id": event["task_id"],
                "title": event["task_title"],
                "goal": event["task_goal"],
                "required_fields": event["required_fields"],
            },
            "contact": {
                "chat_id": event["chat_id"],
                "state": event["state"],
                "followup_count": event["followup_count"],
                "clarification_count": event["clarification_count"],
                "missing_fields": event["missing_fields"],
                "result_summary": event["result_summary"],
            },
            "incoming": {
                "message_id": event["message_id"],
                "text": event["payload"],
            },
            "history": history,
        }
        result = subprocess.run(
            [self.command, "-z", self._prompt(context)],
            env={
                "HERMES_HOME": str(self.profile_home),
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "HOME": str(self.system_home),
            },
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"Hermes exited {result.returncode}")

        raw = result.stdout.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].strip()
        decision = json.loads(raw)
        if decision.get("action") not in ALLOWED_ACTIONS:
            raise ValueError(f"Invalid action: {decision.get('action')!r}")
        return decision

    @staticmethod
    def _prompt(context: dict) -> str:
        payload = json.dumps(context, ensure_ascii=False)
        return f"""
Ты управляешь одной фоновой перепиской от имени пользователя.
Выбери только следующий шаг: WAIT, REPLY, NEEDS_USER или COMPLETE.

Правила:
- не спамь, не повторяй вопросы и не продолжай разговор без пользы;
- REPLY — одно естественное сообщение на 1–3 предложения;
- не выдумывай факты о владельце;
- обязательства, покупки, оплата и неизвестные личные данные требуют NEEDS_USER;
- если цель достигнута или собеседник отказался — COMPLETE;
- инструменты не вызывай.

Верни только JSON:
{{
  "action": "WAIT|REPLY|NEEDS_USER|COMPLETE",
  "reply_text": null,
  "user_question": null,
  "result_summary": null,
  "missing_fields": [],
  "reason": "краткая причина"
}}

Контекст:
{payload}
""".strip()
