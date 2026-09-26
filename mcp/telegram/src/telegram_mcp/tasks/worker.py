"""Autonomous Telegram conversation worker."""

import json
import os
import subprocess
import time
from collections.abc import Callable

from ..client import send_reply
from .conversations import ConversationRepository, conversations
from .database import database
from .decision import HermesDecisionClient
from .task_repository import TaskRepository, task_repository

POLL_SECONDS = 5


class AutonomyWorker:
    def __init__(
        self,
        tasks: TaskRepository,
        conversation_log: ConversationRepository,
        decisions: HermesDecisionClient,
        reply_sender: Callable[..., dict] = send_reply,
    ) -> None:
        self.tasks = tasks
        self.conversation_log = conversation_log
        self.decisions = decisions
        self.reply_sender = reply_sender

    def run_once(self) -> bool:
        event = self.tasks.claim_event()
        if event is None:
            return False
        try:
            self.process(event)
        except Exception as exc:
            self.tasks.release_event(event["id"], f"{type(exc).__name__}: {exc}")
            raise
        return True

    def process(self, event: dict) -> None:
        history = self.conversation_log.messages(event["chat_id"], limit=30)
        decision = self.decisions.decide(event, history)
        action = decision["action"]
        print(
            "[AUTONOMY DECISION] "
            + json.dumps(
                {
                    "event_id": event["id"],
                    "task_id": event["task_id"],
                    "chat_id": event["chat_id"],
                    "decision": decision,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

        if action == "WAIT":
            self._update(event, state="SILENT")
            self.tasks.finish_event(event["id"])
        elif action == "COMPLETE":
            self._complete(event, decision)
        elif action == "NEEDS_USER":
            self._needs_user(event, decision)
        elif action == "REPLY":
            self._reply(event, decision)

    def _complete(self, event: dict, decision: dict) -> None:
        summary = (
            decision.get("result_summary")
            or decision.get("reason")
            or "Задача по контакту завершена."
        )
        self._update(
            event,
            state="DONE",
            result_summary=summary,
            missing_fields=json.dumps(decision.get("missing_fields") or [], ensure_ascii=False),
        )
        self.tasks.complete_contact(event["task_contact_id"])
        self.tasks.finish_event(event["id"])
        remaining, contacts = self.tasks.completion_state(event["task_id"])
        if remaining:
            self._notify(event, "PROGRESS", summary)
            print(
                f"[TASK PROGRESS] task={event['task_id']} remaining={remaining}",
                flush=True,
            )
            return

        results = [
            contact["result_summary"].strip()
            for contact in contacts
            if (contact["result_summary"] or "").strip()
        ]
        final_summary = (
            "\n".join(f"• {result}" for result in results)
            if results
            else "Все контакты обработаны."
        )
        self.tasks.complete_task(event["task_id"])
        self._notify(event, "DONE", final_summary)
        print(
            f"[TASK DONE] task={event['task_id']} contacts={len(contacts)}",
            flush=True,
        )

    def _needs_user(self, event: dict, decision: dict) -> None:
        question = decision.get("user_question") or "Нужна информация пользователя."
        self._update(
            event,
            state="NEEDS_USER",
            needs_user_question=question,
            missing_fields=json.dumps(decision.get("missing_fields") or [], ensure_ascii=False),
        )
        self._notify(event, "NEEDS_USER", question)
        self.tasks.finish_event(event["id"])

    def _reply(self, event: dict, decision: dict) -> None:
        text = (decision.get("reply_text") or "").strip()
        if not text:
            raise ValueError("REPLY decision has empty reply_text")

        clarification_count = int(event.get("clarification_count") or 0)
        if clarification_count >= int(event.get("max_clarifications") or 2):
            question = "Собеседник не дал нужную информацию после нескольких уточнений."
            self._update(event, state="NEEDS_USER", needs_user_question=question)
            self._notify(event, "NEEDS_USER", question)
            self.tasks.finish_event(event["id"])
            return

        chat_id = int(event["chat_id"])
        if chat_id <= 0:
            print(f"[AUTONOMY SEND BLOCKED] chat={chat_id} text={text!r}", flush=True)
            self._update(
                event,
                state="AWAITING_REPLY",
                clarification_count=clarification_count + 1,
            )
            self.tasks.finish_event(event["id"])
            return
        if not self.tasks.event_is_claimed(event["id"]):
            return

        self.tasks.finish_event(event["id"])
        try:
            result = self.reply_sender(
                chat_id=chat_id,
                message_id=int(event["message_id"]),
                text=text,
            )
        except Exception as exc:
            question = "Автономный ответ не доставлен; нужна ручная проверка диалога."
            self._update(event, state="NEEDS_USER", needs_user_question=question)
            self._notify(event, "NEEDS_USER", question)
            raise RuntimeError(f"Telegram delivery failed: {exc}") from exc

        self.conversation_log.save_message(
            chat_id=chat_id,
            message_id=result["message_id"],
            date=result["date"],
            direction="outgoing",
            sender_id=None,
            sender_name=os.environ.get("OWNER_DISPLAY_NAME", "Owner"),
            sender_username=None,
            chat_title=None,
            chat_username=None,
            text=text,
            reply_to_message_id=int(event["message_id"]),
        )
        self._update(
            event,
            state="AWAITING_REPLY",
            clarification_count=clarification_count + 1,
            last_outgoing_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            missing_fields=json.dumps(decision.get("missing_fields") or [], ensure_ascii=False),
        )
        print(f"[AUTONOMY SENT] chat={chat_id} message={result['message_id']}", flush=True)

    def _update(self, event: dict, **fields: object) -> None:
        self.tasks.update_contact(event["task_contact_id"], **fields)

    def _notify(self, event: dict, kind: str, text: str) -> None:
        self.tasks.queue_notification(event["task_id"], kind, text)


def main() -> None:
    database.initialize()
    worker = AutonomyWorker(
        task_repository,
        conversations,
        HermesDecisionClient.from_env(),
    )
    print("Telegram conversation worker starting", flush=True)
    while True:
        try:
            worker.run_once()
        except subprocess.TimeoutExpired:
            print("[AUTONOMY ERROR] Hermes decision timed out", flush=True)
        except Exception as exc:
            print(f"[AUTONOMY ERROR] {type(exc).__name__}: {exc}", flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
