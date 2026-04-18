from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.ai_models import AISuggestion
from app.models.user import User


class AIDecisionReviewService:
    """Gerencia fila de revisao humana para decisoes IA classificadas como L1."""

    MODULE = "ai_governance"
    SUGGESTION_TYPE = "human_review_required"
    STATUS_PENDING = "pending_review"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _safe_metadata(row: AISuggestion) -> dict[str, Any]:
        return row.meta_json if isinstance(row.meta_json, dict) else {}

    def enqueue_review(
        self,
        *,
        user_id: int,
        action_type: str,
        entity_id: str,
        decision: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> tuple[AISuggestion, bool]:
        review_key = (
            f"review:{str(action_type or '').strip().lower()}:"
            f"{str(entity_id or '').strip()}:{str(decision.get('event_id') or 'none')}"
        )

        # Busca em memoria para manter compatibilidade entre SQLite/PostgreSQL sem depender de query JSON especifica.
        existing_rows = (
            self.db.query(AISuggestion)
            .filter(
                AISuggestion.module == self.MODULE,
                AISuggestion.suggestion_type == self.SUGGESTION_TYPE,
                AISuggestion.status == self.STATUS_PENDING,
            )
            .order_by(AISuggestion.created_at.desc())
            .limit(200)
            .all()
        )
        for row in existing_rows:
            meta = self._safe_metadata(row)
            if str(meta.get("review_key") or "") == review_key:
                return row, False

        risk_level = str(decision.get("risk_level") or "unknown")
        policy_reasons = decision.get("policy_reasons") if isinstance(decision.get("policy_reasons"), list) else []
        reason_summary = ", ".join(str(item) for item in policy_reasons[:4]) or "governance_review"

        row = AISuggestion(
            user_id=user_id,
            module=self.MODULE,
            suggestion_type=self.SUGGESTION_TYPE,
            title=f"Revisao humana pendente: {action_type}",
            content=(
                f"Acao {action_type} para entidade {entity_id} requer aprovacao humana. "
                f"Risco {risk_level}. Motivos: {reason_summary}."
            ),
            priority="high" if risk_level in {"high", "medium"} else "medium",
            status=self.STATUS_PENDING,
            confidence=max(0.0, min(1.0, 1.0 - float(decision.get("risk_score") or 0.0))),
            meta_json={
                "review_key": review_key,
                "queued_at": datetime.now(timezone.utc).isoformat(),
                "action_type": action_type,
                "entity_id": entity_id,
                "decision": decision,
                "context": context or {},
            },
        )
        self.db.add(row)
        self.db.flush()
        return row, True

    def list_queue(self, *, status: str = "pending_review", limit: int = 50) -> list[AISuggestion]:
        query = (
            self.db.query(AISuggestion)
            .filter(
                AISuggestion.module == self.MODULE,
                AISuggestion.suggestion_type == self.SUGGESTION_TYPE,
            )
            .order_by(AISuggestion.created_at.desc())
        )

        normalized_status = str(status or "pending_review").strip().lower()
        if normalized_status != "all":
            query = query.filter(AISuggestion.status == normalized_status)

        return query.limit(max(1, min(int(limit), 200))).all()

    def resolve_review(
        self,
        *,
        review_id: int,
        decision: str,
        reviewer: User,
        notes: str | None = None,
    ) -> AISuggestion:
        row = (
            self.db.query(AISuggestion)
            .filter(
                AISuggestion.id == review_id,
                AISuggestion.module == self.MODULE,
                AISuggestion.suggestion_type == self.SUGGESTION_TYPE,
            )
            .first()
        )
        if row is None:
            raise ValueError("Item de revisao nao encontrado")

        normalized_decision = str(decision or "").strip().lower()
        if normalized_decision not in {"approve", "reject"}:
            raise ValueError("Decisao invalida. Use approve ou reject")

        row.status = self.STATUS_APPROVED if normalized_decision == "approve" else self.STATUS_REJECTED

        # Cria nova instancia para forcar dirty tracking do SQLAlchemy em colunas JSON.
        meta = dict(self._safe_metadata(row))
        meta["review"] = {
            "decision": normalized_decision,
            "notes": (notes or "").strip() or None,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewed_by_user_id": int(reviewer.id),
            "reviewed_by_name": str(reviewer.name or ""),
            "reviewed_by_role": str(reviewer.role or ""),
        }
        row.meta_json = meta

        self.db.add(row)
        self.db.flush()
        return row

    @staticmethod
    def to_payload(row: AISuggestion) -> dict[str, Any]:
        meta = row.meta_json if isinstance(row.meta_json, dict) else {}
        return {
            "id": int(row.id),
            "user_id": int(row.user_id),
            "module": row.module,
            "suggestion_type": row.suggestion_type,
            "title": row.title,
            "content": row.content,
            "priority": row.priority,
            "status": row.status,
            "confidence": float(row.confidence or 0.0),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "decision": meta.get("decision") if isinstance(meta.get("decision"), dict) else {},
            "context": meta.get("context") if isinstance(meta.get("context"), dict) else {},
            "review": meta.get("review") if isinstance(meta.get("review"), dict) else {},
        }