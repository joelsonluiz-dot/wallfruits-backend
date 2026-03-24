from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.ai.weather_client import WeatherClient
from app.models.ai_models import AISuggestion, UserBehaviorLog


class SmartSchedulingAI:
    def __init__(self, db: Session):
        self.db = db
        self.weather_client = WeatherClient()

    async def suggest_best_slots(
        self,
        *,
        user_id: int,
        location_lat: float,
        location_lon: float,
        availability: list[int] | None = None,
    ) -> list[dict]:
        availability = availability or [8, 9, 10, 14, 15, 16]

        weather_score = await self.weather_client.get_forecast_score(
            lat=location_lat,
            lon=location_lon,
        )

        history_rows = (
            self.db.query(UserBehaviorLog)
            .filter(UserBehaviorLog.user_id == user_id, UserBehaviorLog.event_type == "meeting_success")
            .order_by(UserBehaviorLog.created_at.desc())
            .limit(80)
            .all()
        )

        preferred_hours = []
        for row in history_rows:
            meta = row.meta_json or {}
            hour = meta.get("hour")
            if isinstance(hour, int):
                preferred_hours.append(hour)

        suggestions = []
        for hour in availability:
            hist_bonus = 0.2 if hour in preferred_hours else 0.05
            score = max(0.0, min(1.0, weather_score * 0.65 + hist_bonus + 0.15))
            suggestions.append(
                {
                    "hour": hour,
                    "score": round(score, 4),
                    "reason": "clima + histórico + disponibilidade",
                }
            )

        suggestions.sort(key=lambda s: s["score"], reverse=True)
        top = suggestions[:3]

        for item in top:
            self.db.add(
                AISuggestion(
                    user_id=user_id,
                    module="smart_scheduling",
                    suggestion_type="best_time",
                    title="Melhor horário sugerido",
                    content=f"Agende em torno de {item['hour']:02d}:00 para maior chance de sucesso.",
                    priority="high" if item["score"] >= 0.75 else "medium",
                    confidence=item["score"],
                    meta_json={"hour": item["hour"], "weather_score": weather_score},
                )
            )

        self.db.commit()
        return top

    def build_natural_language_summary(self, slots: list[dict]) -> str:
        if not slots:
            return "Nenhum horário recomendado no momento."
        best = slots[0]
        return (
            f"Recomendação principal: {best['hour']:02d}:00 "
            f"(confiança {best['score'] * 100:.1f}%)."
        )

    @staticmethod
    def now_iso() -> str:
        return datetime.utcnow().isoformat()
