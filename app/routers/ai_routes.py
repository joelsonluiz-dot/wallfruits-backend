from datetime import date, datetime, time, timedelta, timezone
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
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
from app.models.ai_models import UserBehaviorLog
from app.models.notification import Notification
from app.models.offer import Offer
from app.models.service import Service
from app.models.store_models import Order, QuoteRequest, QuoteRequestStatus
from app.models.transaction import Transaction
from app.models.agenda_event import AgendaEvent
from app.services.agenda_proactive_service import (
    emit_predictive_notifications_for_user,
    event_rule_hints,
    maybe_create_rule_notifications,
)
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


class AgendaProfileIn(BaseModel):
    autonomy_mode: str = Field(default="assistida", pattern="^(assistida|semi_autonoma|autonoma)$")
    main_goal: str = Field(default="produtividade", min_length=3, max_length=80)
    decision_style: str = Field(default="equilibrado", pattern="^(conservador|equilibrado|agressivo)$")
    preferred_contact_period: str = Field(default="manha", pattern="^(manha|tarde|noite|comercial)$")
    wants_offer_alerts: bool = True
    wants_service_alerts: bool = True
    wants_purchase_based_actions: bool = True
    weight_purchases: int = Field(default=30, ge=0, le=100)
    weight_services: int = Field(default=20, ge=0, le=100)
    weight_offers: int = Field(default=25, ge=0, le=100)
    weight_notifications: int = Field(default=25, ge=0, le=100)


class AgendaEventIn(BaseModel):
    title: str = Field(..., min_length=3, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    event_type: str = Field(default="reservation", pattern="^(reservation|task|meeting|reminder)$")
    starts_at: datetime
    ends_at: datetime
    location: str | None = Field(default=None, max_length=180)
    is_all_day: bool = False
    meta_json: dict = Field(default_factory=dict)


class AgendaEventUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    event_type: str | None = Field(default=None, pattern="^(reservation|task|meeting|reminder)$")
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location: str | None = Field(default=None, max_length=180)
    is_all_day: bool | None = None
    status: str | None = Field(default=None, pattern="^(scheduled|completed|cancelled)$")
    meta_json: dict | None = None


class AgendaMoveEventIn(BaseModel):
    target_date: date


def _default_agenda_profile() -> dict:
    return {
        "onboarding_complete": False,
        "autonomy_mode": "assistida",
        "main_goal": "produtividade",
        "decision_style": "equilibrado",
        "preferred_contact_period": "manha",
        "wants_offer_alerts": True,
        "wants_service_alerts": True,
        "wants_purchase_based_actions": True,
        "weight_purchases": 30,
        "weight_services": 20,
        "weight_offers": 25,
        "weight_notifications": 25,
    }


def _load_agenda_profile(db: Session, user_id: int) -> dict:
    row = (
        db.query(UserBehaviorLog)
        .filter(
            UserBehaviorLog.user_id == user_id,
            UserBehaviorLog.event_type == "agenda_profile_updated",
        )
        .order_by(UserBehaviorLog.created_at.desc())
        .first()
    )
    if not row:
        return _default_agenda_profile()

    merged = _default_agenda_profile()
    meta = row.meta_json if isinstance(row.meta_json, dict) else {}
    merged.update(meta)
    return merged


def _cache_key(*parts: str) -> str:
    return "ai:" + ":".join(parts)


def _normalize_weights(profile: dict) -> dict:
    raw = {
        "purchases": int(profile.get("weight_purchases", 30) or 0),
        "services": int(profile.get("weight_services", 20) or 0),
        "offers": int(profile.get("weight_offers", 25) or 0),
        "notifications": int(profile.get("weight_notifications", 25) or 0),
    }
    total = sum(max(0, value) for value in raw.values()) or 1
    return {key: round((max(0, value) / total) * 100, 2) for key, value in raw.items()}


def _priority_from_score(score: float) -> str:
    if score >= 70:
        return "alta"
    if score >= 40:
        return "media"
    return "baixa"


def _event_payload(item: AgendaEvent) -> dict:
    hints = event_rule_hints(item.starts_at, item.ends_at)
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "event_type": item.event_type,
        "starts_at": item.starts_at.isoformat() if item.starts_at else None,
        "ends_at": item.ends_at.isoformat() if item.ends_at else None,
        "location": item.location,
        "status": item.status,
        "is_all_day": bool(item.is_all_day),
        "meta_json": item.meta_json if isinstance(item.meta_json, dict) else {},
        "rule_hints": hints,
    }


def _date_bounds(view: str, anchor: date) -> tuple[datetime, datetime]:
    if view == "day":
        start_d = anchor
        end_d = anchor + timedelta(days=1)
    elif view == "week":
        start_d = anchor - timedelta(days=anchor.weekday())
        end_d = start_d + timedelta(days=7)
    else:
        start_d = anchor.replace(day=1)
        next_month = (start_d.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_d = next_month

    return (
        datetime.combine(start_d, time.min, tzinfo=timezone.utc),
        datetime.combine(end_d, time.min, tzinfo=timezone.utc),
    )


def _calendar_payload(view: str, anchor: date, events: list[AgendaEvent]) -> dict:
    by_day: dict[str, list[AgendaEvent]] = {}
    for event in events:
        day_key = event.starts_at.date().isoformat()
        by_day.setdefault(day_key, []).append(event)

    if view == "day":
        day_key = anchor.isoformat()
        day_events = sorted(by_day.get(day_key, []), key=lambda row: row.starts_at)
        return {
            "view": "day",
            "anchor_date": day_key,
            "days": [
                {
                    "date": day_key,
                    "events": [_event_payload(item) for item in day_events],
                }
            ],
        }

    if view == "week":
        week_start = anchor - timedelta(days=anchor.weekday())
        days = []
        for i in range(7):
            current = week_start + timedelta(days=i)
            key = current.isoformat()
            items = sorted(by_day.get(key, []), key=lambda row: row.starts_at)
            days.append(
                {
                    "date": key,
                    "weekday": current.strftime("%A"),
                    "events": [_event_payload(item) for item in items],
                    "count": len(items),
                }
            )
        return {"view": "week", "anchor_date": anchor.isoformat(), "days": days}

    month_start = anchor.replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    current = month_start
    days = []
    while current < next_month:
        key = current.isoformat()
        items = sorted(by_day.get(key, []), key=lambda row: row.starts_at)
        days.append(
            {
                "date": key,
                "day": current.day,
                "count": len(items),
                "events_preview": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "starts_at": item.starts_at.isoformat(),
                        "event_type": item.event_type,
                        "ends_at": item.ends_at.isoformat(),
                    }
                    for item in items[:3]
                ],
                "events": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "starts_at": item.starts_at.isoformat(),
                        "ends_at": item.ends_at.isoformat(),
                        "event_type": item.event_type,
                    }
                    for item in items
                ],
            }
        )
        current += timedelta(days=1)

    return {"view": "month", "anchor_date": anchor.isoformat(), "days": days}


def _create_notification_once(
    db: Session,
    *,
    user_id: int,
    title: str,
    message: str,
    resource_key: str,
) -> bool:
    window_start = datetime.now(timezone.utc) - timedelta(hours=12)
    exists = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.notification_type == "agenda_proactive",
            Notification.resource_type == "agenda_alert",
            Notification.resource_id == resource_key,
            Notification.created_at >= window_start,
        )
        .first()
    )
    if exists:
        return False

    db.add(
        Notification(
            user_id=user_id,
            actor_user_id=None,
            notification_type="agenda_proactive",
            title=title,
            message=message,
            resource_type="agenda_alert",
            resource_id=resource_key,
            is_read=False,
        )
    )
    return True


def _score_actions_with_weights(actions: list[dict], weights: dict) -> list[dict]:
    scored = []
    for item in actions:
        source = item.get("source", "notifications")
        base = float(item.get("base_impact", 40.0))
        urgency = float(item.get("urgency", 1.0))
        weight = float(weights.get(source, 25.0))

        score = min(100.0, max(0.0, (weight * 0.55) + (base * 0.45))) * urgency
        normalized = min(100.0, round(score, 2))

        payload = dict(item)
        payload["score"] = normalized
        payload["priority"] = _priority_from_score(normalized)
        scored.append(payload)

    scored.sort(key=lambda row: row.get("score", 0), reverse=True)
    return scored


@router.get("/agenda/profile")
def get_agenda_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _load_agenda_profile(db, current_user.id)
    return {"profile": profile}


@router.post("/agenda/profile")
def save_agenda_profile(
    payload: AgendaProfileIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = payload.model_dump()
    profile["onboarding_complete"] = True

    telemetry = AITelemetryService(db)
    telemetry.log_event(
        user_id=current_user.id,
        event_type="agenda_profile_updated",
        entity_type="agenda",
        metadata=profile,
        commit=True,
    )

    return {"ok": True, "profile": profile}


@router.get("/agenda/events")
def get_agenda_events(
    view: str = Query(default="month", pattern="^(day|week|month)$"),
    anchor_date: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        anchor = date.fromisoformat(anchor_date) if anchor_date else datetime.now(timezone.utc).date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="anchor_date inválida. Use YYYY-MM-DD") from exc

    dt_start, dt_end = _date_bounds(view, anchor)

    rows = (
        db.query(AgendaEvent)
        .filter(
            AgendaEvent.user_id == current_user.id,
            AgendaEvent.starts_at >= dt_start,
            AgendaEvent.starts_at < dt_end,
            AgendaEvent.status != "cancelled",
        )
        .order_by(AgendaEvent.starts_at.asc())
        .all()
    )

    created_predictive = emit_predictive_notifications_for_user(db, user_id=current_user.id)
    if created_predictive:
        db.commit()

    payload = _calendar_payload(view, anchor, rows)
    payload["predictive_alerts_created"] = created_predictive
    return payload


@router.post("/agenda/events")
def create_agenda_event(
    payload: AgendaEventIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=400, detail="ends_at deve ser maior que starts_at")

    item = AgendaEvent(
        user_id=current_user.id,
        title=payload.title.strip(),
        description=(payload.description or "").strip() or None,
        event_type=payload.event_type,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        location=(payload.location or "").strip() or None,
        is_all_day=bool(payload.is_all_day),
        status="scheduled",
        meta_json=payload.meta_json or {},
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    hints = event_rule_hints(item.starts_at, item.ends_at)
    meta = item.meta_json if isinstance(item.meta_json, dict) else {}
    meta["rule_hints"] = hints
    item.meta_json = meta
    db.commit()
    db.refresh(item)

    db.add(
        Notification(
            user_id=current_user.id,
            actor_user_id=None,
            notification_type="agenda_event_created",
            title="Novo evento na agenda",
            message=f"{item.title} agendado para {item.starts_at.strftime('%d/%m %H:%M')}.",
            resource_type="agenda_event",
            resource_id=str(item.id),
            is_read=False,
        )
    )
    created_rules = maybe_create_rule_notifications(db, user_id=current_user.id, event=item)
    created_predictive = emit_predictive_notifications_for_user(db, user_id=current_user.id)
    db.commit()

    return {
        "ok": True,
        "event": _event_payload(item),
        "rule_notifications_created": created_rules,
        "predictive_notifications_created": created_predictive,
    }


@router.patch("/agenda/events/{event_id}")
def update_agenda_event(
    event_id: int,
    payload: AgendaEventUpdateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(AgendaEvent)
        .filter(AgendaEvent.id == event_id, AgendaEvent.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    data = payload.model_dump(exclude_unset=True)
    for key in ["title", "description", "event_type", "starts_at", "ends_at", "location", "status", "is_all_day"]:
        if key in data:
            setattr(item, key, data[key])

    if "meta_json" in data and isinstance(data["meta_json"], dict):
        item.meta_json = data["meta_json"]

    if item.ends_at <= item.starts_at:
        raise HTTPException(status_code=400, detail="ends_at deve ser maior que starts_at")

    hints = event_rule_hints(item.starts_at, item.ends_at)
    meta = item.meta_json if isinstance(item.meta_json, dict) else {}
    meta["rule_hints"] = hints
    item.meta_json = meta

    db.commit()
    db.refresh(item)
    created_rules = maybe_create_rule_notifications(db, user_id=current_user.id, event=item)
    created_predictive = emit_predictive_notifications_for_user(db, user_id=current_user.id)
    db.commit()
    return {
        "ok": True,
        "event": _event_payload(item),
        "rule_notifications_created": created_rules,
        "predictive_notifications_created": created_predictive,
    }


@router.patch("/agenda/events/{event_id}/move")
def move_agenda_event(
    event_id: int,
    payload: AgendaMoveEventIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(AgendaEvent)
        .filter(AgendaEvent.id == event_id, AgendaEvent.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    current_start = item.starts_at.astimezone(timezone.utc)
    current_end = item.ends_at.astimezone(timezone.utc)
    duration = current_end - current_start

    new_start = datetime.combine(payload.target_date, current_start.time(), tzinfo=timezone.utc)
    new_end = new_start + duration

    item.starts_at = new_start
    item.ends_at = new_end

    hints = event_rule_hints(item.starts_at, item.ends_at)
    meta = item.meta_json if isinstance(item.meta_json, dict) else {}
    meta["rule_hints"] = hints
    meta["last_moved_at"] = datetime.now(timezone.utc).isoformat()
    item.meta_json = meta

    db.commit()
    db.refresh(item)

    created_rules = maybe_create_rule_notifications(db, user_id=current_user.id, event=item)
    created_predictive = emit_predictive_notifications_for_user(db, user_id=current_user.id)
    db.commit()

    return {
        "ok": True,
        "event": _event_payload(item),
        "rule_notifications_created": created_rules,
        "predictive_notifications_created": created_predictive,
    }


@router.delete("/agenda/events/{event_id}")
def cancel_agenda_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(AgendaEvent)
        .filter(AgendaEvent.id == event_id, AgendaEvent.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    item.status = "cancelled"
    db.commit()
    return {"ok": True, "id": event_id}


@router.get("/agenda/plan")
async def agenda_agent_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cache_key = _cache_key("agenda-plan", str(current_user.id))
    cached = get_cache(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass

    profile = _load_agenda_profile(db, current_user.id)

    scheduling = SmartSchedulingAI(db)
    slots = await scheduling.suggest_best_slots(
        user_id=current_user.id,
        location_lat=-23.5505,
        location_lon=-46.6333,
        availability=[8, 9, 10, 11, 14, 15, 16, 17],
        persist_suggestions=False,
    )

    total_store_orders = (
        db.query(Order)
        .filter(Order.customer_id == current_user.id, Order.payment_method != "cart_open")
        .count()
    )
    pending_quotes = (
        db.query(QuoteRequest)
        .filter(
            QuoteRequest.requester_id == current_user.id,
            QuoteRequest.status == QuoteRequestStatus.PENDING,
        )
        .count()
    )
    unread_notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .count()
    )
    my_offers = db.query(Offer).filter(Offer.user_id == current_user.id).count()
    my_services = db.query(Service).filter(Service.created_by_user_id == current_user.id).count()
    my_transactions = db.query(Transaction).filter(Transaction.buyer_id == current_user.id).count()

    weights = _normalize_weights(profile)
    actions: list[dict] = []

    if unread_notifications > 0:
        actions.append(
            {
                "type": "notifications",
                "source": "notifications",
                "base_impact": 82,
                "urgency": 1.0,
                "title": "Revisar notificações pendentes",
                "description": f"Você possui {unread_notifications} notificação(ões) não lida(s).",
                "cta": "/notifications",
                "notify": True,
                "notify_key": "unread_notifications",
            }
        )

    if pending_quotes > 0:
        actions.append(
            {
                "type": "quotes",
                "source": "purchases",
                "base_impact": 88,
                "urgency": 1.08,
                "title": "Responder propostas de volume",
                "description": f"Existem {pending_quotes} proposta(s) pendente(s) para acompanhamento.",
                "cta": "/store/proposals",
                "notify": True,
                "notify_key": "pending_quotes",
            }
        )

    if total_store_orders == 0 and profile.get("wants_purchase_based_actions", True):
        actions.append(
            {
                "type": "first_purchase",
                "source": "purchases",
                "base_impact": 54,
                "urgency": 0.95,
                "title": "Planejar primeira compra inteligente",
                "description": "Ainda não há pedidos concluídos. Monte sua compra com itens recomendados pela IA.",
                "cta": "/store",
                "notify": False,
            }
        )

    if my_services == 0 and profile.get("wants_service_alerts", True):
        actions.append(
            {
                "type": "services",
                "source": "services",
                "base_impact": 58,
                "urgency": 0.92,
                "title": "Cadastrar ou revisar serviços agrícolas",
                "description": "Você pode ampliar sua operação com novos serviços na vitrine.",
                "cta": "/services",
                "notify": False,
            }
        )

    if my_offers == 0 and profile.get("wants_offer_alerts", True):
        actions.append(
            {
                "type": "offers",
                "source": "offers",
                "base_impact": 62,
                "urgency": 0.96,
                "title": "Publicar novas ofertas",
                "description": "Sem ofertas ativas no momento. Publicar aumenta visibilidade e negociações.",
                "cta": "/offers/new",
                "notify": False,
            }
        )

    upcoming_reservations = (
        db.query(AgendaEvent)
        .filter(
            AgendaEvent.user_id == current_user.id,
            AgendaEvent.event_type == "reservation",
            AgendaEvent.status == "scheduled",
            AgendaEvent.starts_at >= datetime.now(timezone.utc),
        )
        .order_by(AgendaEvent.starts_at.asc())
        .limit(5)
        .all()
    )

    if not upcoming_reservations:
        actions.append(
            {
                "type": "reservation",
                "source": "services",
                "base_impact": 68,
                "urgency": 1.02,
                "title": "Criar reserva na agenda",
                "description": "Nenhuma reserva futura encontrada. Agende atendimento, visita ou tarefa crítica.",
                "cta": "/ai-agent",
                "notify": True,
                "notify_key": "missing_reservation",
            }
        )

    if not actions:
        actions.append(
            {
                "type": "optimization",
                "source": "notifications",
                "base_impact": 32,
                "urgency": 0.9,
                "title": "Rotina otimizada",
                "description": "Sua agenda está estável. Execute ações de manutenção e acompanhe métricas.",
                "cta": "/strategy",
                "notify": False,
            }
        )

    scored_actions = _score_actions_with_weights(actions, weights)

    proactive_created = 0
    for action in scored_actions[:3]:
        if not action.get("notify"):
            continue
        key = str(action.get("notify_key") or action.get("type") or "agenda_action")
        if _create_notification_once(
            db,
            user_id=current_user.id,
            title=f"Agenda Inteligente: {action.get('title', 'Ação recomendada')}",
            message=str(action.get("description") or "Você possui uma recomendação importante."),
            resource_key=key,
        ):
            proactive_created += 1

    predictive_created = emit_predictive_notifications_for_user(db, user_id=current_user.id)

    if proactive_created or predictive_created:
        db.commit()

    summary = {
        "user": {
            "id": current_user.id,
            "name": current_user.name,
            "role": current_user.role,
            "location": current_user.location,
        },
        "profile": profile,
        "history": {
            "store_orders": int(total_store_orders),
            "pending_quotes": int(pending_quotes),
            "unread_notifications": int(unread_notifications),
            "my_offers": int(my_offers),
            "my_services": int(my_services),
            "my_transactions": int(my_transactions),
            "upcoming_reservations": len(upcoming_reservations),
        },
        "best_slots": slots,
        "decision_mode": profile.get("autonomy_mode", "assistida"),
        "decision_weights": weights,
        "actions": scored_actions,
        "proactive_alerts_created": proactive_created,
        "predictive_alerts_created": predictive_created,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    telemetry = AITelemetryService(db)
    telemetry.log_event(
        user_id=current_user.id,
        event_type="agenda_plan_generated",
        entity_type="agenda",
        metadata={
            "actions": len(actions),
            "autonomy_mode": profile.get("autonomy_mode", "assistida"),
        },
        commit=True,
    )

    set_cache(
        cache_key,
        json.dumps(summary, ensure_ascii=False),
        expire=max(30, min(settings.AI_CACHE_TTL_SECONDS, 180)),
    )

    return summary


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
