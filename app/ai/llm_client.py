from __future__ import annotations

import importlib
import json
import logging
from typing import Any

from app.core.config import settings


logger = logging.getLogger("ai_llm")


class LLMClient:
    def __init__(self) -> None:
        self.provider = settings.LLM_PROVIDER.strip().lower()

    def is_enabled(self) -> bool:
        return self.provider == "openai" and bool(settings.OPENAI_API_KEY.strip())

    def complete_json(self, *, system_prompt: str, user_prompt: str, fallback: dict[str, Any]) -> dict[str, Any]:
        if not self.is_enabled():
            return fallback

        try:
            openai_module = importlib.import_module("openai")
            client = openai_module.OpenAI(api_key=settings.OPENAI_API_KEY)

            completion = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content or "{}"
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
            return fallback
        except Exception as exc:
            logger.warning("LLM indisponível, usando fallback local: %s", exc)
            return fallback
