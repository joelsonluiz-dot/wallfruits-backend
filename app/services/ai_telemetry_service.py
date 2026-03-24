from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.ai_models import UserBehaviorLog


class AITelemetryService:
    def __init__(self, db: Session):
        self.db = db

    def log_event(
        self,
        *,
        user_id: int,
        event_type: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        commit: bool = False,
    ) -> UserBehaviorLog:
        payload = dict(metadata or {})
        payload.setdefault("captured_at", datetime.now(timezone.utc).isoformat())

        row = UserBehaviorLog(
            user_id=user_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            meta_json=payload,
        )
        self.db.add(row)

        if commit:
            self.db.commit()
            self.db.refresh(row)

        return row
