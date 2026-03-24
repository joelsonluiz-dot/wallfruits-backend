from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.ml_pipeline import predict_with_fallback
from app.models.ai_models import AISuggestion, Prediction


class NegotiationIntelligenceAI:
    def __init__(self, db: Session):
        self.db = db

    def predict_close_probability(self, *, user_id: int, payload: dict) -> dict:
        prediction_payload, confidence = predict_with_fallback("negotiation", payload)

        row = Prediction(
            user_id=user_id,
            module="negotiation_intelligence",
            model_name="deal_success_model",
            target="deal_success",
            input_payload=payload,
            prediction_payload=prediction_payload,
            confidence=confidence,
        )
        self.db.add(row)

        close_probability = float(prediction_payload.get("close_probability", 0.0))
        actions = self._suggest_actions(close_probability=close_probability, payload=payload)

        for action in actions:
            self.db.add(
                AISuggestion(
                    user_id=user_id,
                    module="negotiation_intelligence",
                    suggestion_type="next_action",
                    title="Ação recomendada na negociação",
                    content=action,
                    priority="high" if close_probability < 0.45 else "medium",
                    confidence=confidence,
                    meta_json={"close_probability": close_probability},
                )
            )

        self.db.commit()
        return {
            "close_probability": close_probability,
            "confidence": confidence,
            "suggested_actions": actions,
        }

    @staticmethod
    def _suggest_actions(*, close_probability: float, payload: dict) -> list[str]:
        actions: list[str] = []

        response_time = float(payload.get("response_time_hours", 6.0) or 6.0)
        if response_time > 10:
            actions.append("Follow up agora: janela de resposta está esfriando.")

        if close_probability < 0.4:
            actions.append("Ofereça desconto progressivo e proponha call curta de alinhamento.")
            actions.append("Entre em contato entre 08h e 10h para melhor taxa de resposta.")
        elif close_probability < 0.7:
            actions.append("Envie prova social (casos de sucesso) antes da próxima proposta.")
            actions.append("Contato recomendado no período da manhã para acelerar decisão.")
        else:
            actions.append("Probabilidade alta: priorize fechamento hoje com CTA objetivo.")

        return actions
