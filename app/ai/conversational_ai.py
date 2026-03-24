from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any

from sqlalchemy.orm import Session

from app.ai.llm_client import LLMClient
from app.models.ai_models import AIChatMessage, AISuggestion


SCHEDULE_PATTERNS = [
    re.compile(r"\b(amanh[ãa])\b.*\b(\d{1,2})(?:[:h](\d{2}))?\b", re.IGNORECASE),
    re.compile(r"\b(hoje)\b.*\b(\d{1,2})(?:[:h](\d{2}))?\b", re.IGNORECASE),
]


class ConversationalAI:
    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMClient()

    def process_message(self, *, user_id: int, session_id: str, message: str) -> dict[str, Any]:
        intent = "generic"
        actions: list[dict[str, Any]] = []
        automation_triggered = False

        normalized = message.lower().strip()

        if any(term in normalized for term in ["reuni", "encontro", "visita", "amanhã", "amanha", "hoje"]):
            parsed = self._extract_schedule(message)
            if parsed:
                intent = "schedule_event"
                automation_triggered = True
                actions.append(
                    {
                        "type": "create_event",
                        "title": "Evento criado automaticamente",
                        "scheduled_for": parsed.isoformat(),
                    }
                )
                self.db.add(
                    AISuggestion(
                        user_id=user_id,
                        module="conversational_ai",
                        suggestion_type="auto_event",
                        title="Evento criado via chat",
                        content=f"Evento agendado para {parsed.strftime('%d/%m %H:%M')}.",
                        priority="high",
                        confidence=0.84,
                        meta_json={"scheduled_for": parsed.isoformat()},
                    )
                )

        local_response = self._build_reply(intent=intent, actions=actions)
        llm_payload = self.llm.complete_json(
            system_prompt=(
                "Você é um assistente de operações agrícolas. "
                "Responda estritamente em JSON com chaves: response, intent, actions."
            ),
            user_prompt=(
                f"Mensagem do usuário: {message}\n"
                f"Intenção local detectada: {intent}\n"
                f"Ações locais detectadas: {actions}"
            ),
            fallback={
                "response": local_response,
                "intent": intent,
                "actions": actions,
            },
        )

        assistant_reply = str(llm_payload.get("response") or local_response)
        intent = str(llm_payload.get("intent") or intent)
        llm_actions = llm_payload.get("actions") or actions
        if isinstance(llm_actions, list):
            actions = llm_actions

        automation_triggered = automation_triggered or any(
            (isinstance(item, dict) and item.get("type") == "create_event")
            for item in actions
        )

        self.db.add(
            AIChatMessage(
                user_id=user_id,
                session_id=session_id,
                role="user",
                message=message,
                parsed_intent=intent,
                automation_triggered=automation_triggered,
                meta_json={"actions": actions},
            )
        )
        self.db.add(
            AIChatMessage(
                user_id=user_id,
                session_id=session_id,
                role="assistant",
                message=assistant_reply,
                parsed_intent=intent,
                automation_triggered=automation_triggered,
                meta_json={"actions": actions},
            )
        )

        self.db.commit()

        return {
            "response": assistant_reply,
            "intent": intent,
            "actions": actions,
            "automation_triggered": automation_triggered,
        }

    @staticmethod
    def _extract_schedule(message: str) -> datetime | None:
        for pattern in SCHEDULE_PATTERNS:
            match = pattern.search(message)
            if not match:
                continue

            day_word = match.group(1).lower()
            hour = int(match.group(2))
            minute = int(match.group(3) or 0)

            now = datetime.now()
            target_date = now.date()
            if "amanh" in day_word:
                target_date = (now + timedelta(days=1)).date()

            hour = max(0, min(23, hour))
            minute = max(0, min(59, minute))

            return datetime(
                year=target_date.year,
                month=target_date.month,
                day=target_date.day,
                hour=hour,
                minute=minute,
            )

        return None

    @staticmethod
    def _build_reply(*, intent: str, actions: list[dict[str, Any]]) -> str:
        if intent == "schedule_event" and actions:
            return "Perfeito. Transformei sua mensagem em evento na agenda inteligente."

        return "Entendi. Posso transformar mensagens em tarefas, eventos ou próximos passos de negociação."
