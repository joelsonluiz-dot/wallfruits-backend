from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.cache.redis_client import get_cache, set_cache
from app.core.config import settings
from app.models.ai_models import UserBehaviorLog


class AITelemetryService:
    def __init__(self, db: Session | None):
        self.db = db

    @staticmethod
    def _normalize_text(value: str | None, *, max_len: int, default: str | None = None) -> str | None:
        raw = str(value or "").strip()
        if not raw:
            return default
        return raw[:max_len]

    @staticmethod
    def _idempotency_cache_key(*, user_id: int, event_type: str, idempotency_key: str) -> str:
        digest = hashlib.sha256(
            f"{user_id}:{event_type}:{idempotency_key}".encode("utf-8")
        ).hexdigest()
        return f"ai:telemetry:idem:{digest}"

    def _existing_event_for_idempotency(
        self,
        *,
        user_id: int,
        event_type: str,
        entity_type: str | None,
        entity_id: str | None,
    ) -> UserBehaviorLog | None:
        if self.db is None:
            return None

        query = self.db.query(UserBehaviorLog).filter(
            UserBehaviorLog.user_id == user_id,
            UserBehaviorLog.event_type == event_type,
        )

        if entity_type is None:
            query = query.filter(UserBehaviorLog.entity_type.is_(None))
        else:
            query = query.filter(UserBehaviorLog.entity_type == entity_type)

        if entity_id is None:
            query = query.filter(UserBehaviorLog.entity_id.is_(None))
        else:
            query = query.filter(UserBehaviorLog.entity_id == entity_id)

        return query.order_by(UserBehaviorLog.id.desc()).first()

    def log_event(
        self,
        *,
        user_id: int,
        event_type: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        commit: bool = False,
        event_domain: str | None = None,
        event_source: str | None = None,
        request_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> UserBehaviorLog:
        normalized_event_type = self._normalize_text(event_type, max_len=80, default="unknown_event") or "unknown_event"
        normalized_entity_type = self._normalize_text(entity_type, max_len=80)
        normalized_entity_id = self._normalize_text(entity_id, max_len=120)

        payload = dict(metadata or {})
        payload.setdefault("captured_at", datetime.now(timezone.utc).isoformat())
        payload.setdefault("event_version", 1)
        payload.setdefault("event_domain", self._normalize_text(event_domain, max_len=80, default="ai") or "ai")
        payload.setdefault("event_source", self._normalize_text(event_source, max_len=180, default="api") or "api")

        normalized_request_id = self._normalize_text(request_id, max_len=120)
        if normalized_request_id:
            payload.setdefault("request_id", normalized_request_id)

        normalized_idempotency = self._normalize_text(idempotency_key, max_len=180)
        idempotency_cache_key: str | None = None
        if normalized_idempotency:
            payload.setdefault("idempotency_key", normalized_idempotency)
            idempotency_cache_key = self._idempotency_cache_key(
                user_id=user_id,
                event_type=normalized_event_type,
                idempotency_key=normalized_idempotency,
            )

            try:
                if get_cache(idempotency_cache_key):
                    existing = self._existing_event_for_idempotency(
                        user_id=user_id,
                        event_type=normalized_event_type,
                        entity_type=normalized_entity_type,
                        entity_id=normalized_entity_id,
                    )
                    if existing:
                        return existing
            except Exception:
                pass

        row = UserBehaviorLog(
            user_id=user_id,
            event_type=normalized_event_type,
            entity_type=normalized_entity_type,
            entity_id=normalized_entity_id,
            meta_json=payload,
        )

        # Modo no-op (ex.: testes com get_db sobrescrito para None).
        if self.db is None:
            return row

        self.db.add(row)

        if commit:
            self.db.commit()
            self.db.refresh(row)

        if idempotency_cache_key:
            try:
                ttl_seconds = max(300, int(settings.AI_CACHE_TTL_SECONDS) * 20)
                set_cache(idempotency_cache_key, json.dumps({"event_id": row.id}), expire=ttl_seconds)
            except Exception:
                pass

        return row

    def log_decision(
        self,
        *,
        user_id: int,
        action_type: str,
        entity_type: str,
        entity_id: str,
        decision_payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        commit: bool = False,
        request_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> UserBehaviorLog:
        merged_metadata = dict(metadata or {})
        merged_metadata["decision"] = decision_payload

        return self.log_event(
            user_id=user_id,
            event_type="ai_decision_recorded",
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=merged_metadata,
            event_domain="autonomous_commerce",
            event_source=f"ai:{action_type}",
            request_id=request_id,
            idempotency_key=idempotency_key,
            commit=commit,
        )
