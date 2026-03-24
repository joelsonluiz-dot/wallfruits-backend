from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.ai.ml_pipeline import predict_with_fallback
from app.models.ai_models import AISuggestion, UserBehaviorLog


class RiskAlertAI:
    def __init__(self, db: Session):
        self.db = db

    def run_for_user(self, *, user_id: int) -> list[dict]:
        alerts: list[dict] = []

        inactivity = self._compute_inactivity_days(user_id)
        pred, confidence = predict_with_fallback(
            "engagement",
            {"inactive_days": inactivity, "response_time_hours": 12.0, "contact_hour": 9.0},
        )
        inactive_risk = float(pred.get("inactive_risk", 0.0))

        if inactivity >= 7 or inactive_risk >= 0.55:
            alerts.append(
                {
                    "type": "low_engagement",
                    "message": "Cliente com baixa interação. Recomendado contato em até 24h.",
                    "risk_score": round(inactive_risk, 4),
                }
            )

        if inactivity >= 14:
            alerts.append(
                {
                    "type": "missed_deadline",
                    "message": "Há sinais de atraso em follow-up e risco de perda de negociação.",
                    "risk_score": round(min(0.98, 0.6 + inactivity / 60.0), 4),
                }
            )

        for alert in alerts:
            self.db.add(
                AISuggestion(
                    user_id=user_id,
                    module="risk_alert",
                    suggestion_type=alert["type"],
                    title="Alerta preditivo de risco",
                    content=alert["message"],
                    priority="high",
                    confidence=confidence,
                    meta_json={"risk_score": alert["risk_score"], "inactive_days": inactivity},
                )
            )

        self.db.commit()
        return alerts

    def _compute_inactivity_days(self, user_id: int) -> int:
        last_action = (
            self.db.query(UserBehaviorLog)
            .filter(UserBehaviorLog.user_id == user_id)
            .order_by(UserBehaviorLog.created_at.desc())
            .first()
        )

        if last_action is None:
            return 30

        ref = last_action.created_at
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        delta: timedelta = now - ref
        return max(0, delta.days)
