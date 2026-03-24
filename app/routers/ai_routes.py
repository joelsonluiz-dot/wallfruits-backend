from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.conversational_ai import ConversationalAI
from app.ai.ml_pipeline import train_models, predict_with_fallback
from app.ai.negotiation_intelligence import NegotiationIntelligenceAI
from app.ai.risk_alert import RiskAlertAI
from app.ai.service_recommendation import ServiceRecommendationAI
from app.ai.smart_scheduling import SmartSchedulingAI
from app.cache.redis_client import get_cache, set_cache
from app.core.auth_middleware import get_current_user
from app.core.config import settings
from app.database.connection import get_db
from app.models.user import User
from app.services.ai_telemetry_service import AITelemetryService
from app.schemas.ai_schema import (
    AISuggestionsResponse,
    ChatRequest,
    ChatResponse,
    PredictRequest,
    PredictResponse,
    RecommendationRequest,
    RecommendationResponse,
    SuggestionItem,
    TrainModelsResponse,
)


router = APIRouter(prefix="/ai", tags=["ai"])


def _cache_key(*parts: str) -> str:
    return "ai:" + ":".join(parts)


@router.get("/suggestions", response_model=AISuggestionsResponse)
async def get_ai_suggestions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    telemetry = AITelemetryService(db)
    telemetry.log_event(
        user_id=current_user.id,
        event_type="ai_suggestions_requested",
        entity_type="ai",
        metadata={"endpoint": "/api/ai/suggestions"},
        commit=True,
    )

    cache_key = _cache_key("suggestions", str(current_user.id))
    cached = get_cache(cache_key)
    if cached:
        payload = json.loads(cached)
        return AISuggestionsResponse(**payload)

    scheduling = SmartSchedulingAI(db)
    slots = await scheduling.suggest_best_slots(
        user_id=current_user.id,
        location_lat=-23.5505,
        location_lon=-46.6333,
        availability=[8, 9, 10, 14, 15, 16],
    )

    negotiation = NegotiationIntelligenceAI(db)
    negotiation_out = negotiation.predict_close_probability(
        user_id=current_user.id,
        payload={"contact_hour": 9, "response_time_hours": 5, "discount_pct": 4, "inactive_days": 2},
    )

    risk = RiskAlertAI(db)
    risk_alerts = risk.run_for_user(user_id=current_user.id)

    items = [
        SuggestionItem(
            module="smart_scheduling",
            suggestion_type="best_slot",
            title="Horário inteligente sugerido",
            content=scheduling.build_natural_language_summary(slots),
            priority="high",
            confidence=slots[0]["score"] if slots else 0.0,
            metadata={"slots": slots},
        ),
        SuggestionItem(
            module="negotiation_intelligence",
            suggestion_type="deal_probability",
            title="Probabilidade de fechamento",
            content=(
                f"Chance estimada de fechamento: "
                f"{negotiation_out['close_probability'] * 100:.1f}%"
            ),
            priority="medium",
            confidence=negotiation_out["confidence"],
            metadata={"actions": negotiation_out["suggested_actions"]},
        ),
    ]

    for alert in risk_alerts:
        items.append(
            SuggestionItem(
                module="risk_alert",
                suggestion_type=alert["type"],
                title="Alerta de risco",
                content=alert["message"],
                priority="high",
                confidence=alert.get("risk_score", 0.5),
                metadata=alert,
            )
        )

    response = AISuggestionsResponse(generated_at=datetime.now(timezone.utc), items=items)
    set_cache(
        cache_key,
        response.model_dump_json(),
        expire=settings.AI_CACHE_TTL_SECONDS,
    )
    return response


@router.post("/predict", response_model=PredictResponse)
def predict_ai(
    payload: PredictRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    telemetry = AITelemetryService(db)
    telemetry.log_event(
        user_id=current_user.id,
        event_type="ai_predict_requested",
        entity_type="ai",
        metadata={"module": payload.module, "payload": payload.payload},
        commit=True,
    )

    payload_key = json.dumps(payload.payload, sort_keys=True, separators=(",", ":"))
    cache_key = _cache_key("predict", str(current_user.id), payload.module, payload_key)
    cached = get_cache(cache_key)
    if cached:
        return PredictResponse(**json.loads(cached))

    prediction_payload, confidence = predict_with_fallback(payload.module, payload.payload)

    response = PredictResponse(
        module=payload.module,
        prediction=prediction_payload,
        confidence=confidence,
    )
    set_cache(
        cache_key,
        response.model_dump_json(),
        expire=settings.AI_CACHE_TTL_SECONDS,
    )
    return response


@router.post("/chat", response_model=ChatResponse)
def ai_chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    telemetry = AITelemetryService(db)
    telemetry.log_event(
        user_id=current_user.id,
        event_type="ai_chat_requested",
        entity_type="chat",
        metadata={"session_id": payload.session_id, "message_size": len(payload.message)},
        commit=True,
    )

    service = ConversationalAI(db)
    result = service.process_message(
        user_id=current_user.id,
        session_id=payload.session_id,
        message=payload.message,
    )

    return ChatResponse(**result)


@router.post("/recommendations", response_model=RecommendationResponse)
def get_recommendations(
    payload: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    telemetry = AITelemetryService(db)
    telemetry.log_event(
        user_id=current_user.id,
        event_type="ai_recommendations_requested",
        entity_type="recommendation",
        metadata={
            "crop_type": payload.crop_type,
            "region": payload.region,
            "season": payload.season,
        },
        commit=True,
    )

    service = ServiceRecommendationAI(db)
    recommendations = service.recommend(
        user_id=current_user.id,
        crop_type=payload.crop_type,
        region=payload.region,
        season=payload.season,
    )
    return RecommendationResponse(recommendations=recommendations)


@router.post("/train", response_model=TrainModelsResponse)
def train_ai_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    telemetry = AITelemetryService(db)
    telemetry.log_event(
        user_id=current_user.id,
        event_type="ai_train_requested",
        entity_type="ml",
        metadata={"endpoint": "/api/ai/train"},
        commit=True,
    )

    details = train_models(db)
    return TrainModelsResponse(success=bool(details.get("trained", False)), details=details)
