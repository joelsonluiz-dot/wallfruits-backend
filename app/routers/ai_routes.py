import csv
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai.conversational_ai import ConversationalAI
from app.ai.business_os import (
    build_business_os_blueprint,
    build_business_os_implementation_plan,
    build_business_os_readiness,
    build_orchestration_decision,
)
from app.ai.autonomous_commerce import AutonomousCommerceAI
from app.ai.market_intelligence import MarketIntelligenceAI
from app.ai.ml_pipeline import train_models, predict_with_fallback
from app.ai.negotiation_intelligence import NegotiationIntelligenceAI
from app.ai.risk_alert import RiskAlertAI
from app.ai.service_recommendation import ServiceRecommendationAI
from app.ai.smart_scheduling import SmartSchedulingAI
from app.cache.redis_client import get_cache, set_cache
from app.core.auth_middleware import (
    ACCOUNT_ROLE_ANALYST,
    ACCOUNT_ROLE_MANAGER,
    ACCOUNT_ROLE_OWNER,
    ACCOUNT_ROLE_VIEWER,
    PLATFORM_ROLE_STAFF_ADMIN,
    PLATFORM_ROLE_STAFF_OPS,
    PLATFORM_ROLE_STAFF_SUPPORT,
    get_current_user,
    require_account_roles,
    require_platform_roles,
    resolve_account_scope_id,
)
from app.core.config import settings
from app.database.connection import get_db
from app.models.user import User
from app.models.ai_models import AISuggestion, UserBehaviorLog
from app.models.message import Message
from app.models.notification import Notification
from app.models.offer import Offer
from app.models.service import Service
from app.models.subscription import Subscription
from app.models.store_models import Order, QuoteRequest, QuoteRequestStatus
from app.models.transaction import Transaction
from app.models.agenda_event import AgendaEvent
from app.services.agenda_proactive_service import (
    emit_predictive_notifications_for_user,
    event_rule_hints,
    maybe_create_rule_notifications,
)
from app.services.ai_decision_review_service import AIDecisionReviewService
from app.services.ai_governance_service import AIGovernanceService
from app.services.ai_telemetry_service import AITelemetryService
from app.services.profile_service import ProfileService
from app.services.subscription_policy_service import capabilities_for_plan, capabilities_for_user, require_minimum_plan
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

    auto_negotiation_enabled: bool = True
    auto_flash_auction_enabled: bool = True
    guardrail_max_discount_pct: float = Field(default=8, ge=0, le=40)
    guardrail_min_net_margin_pct: float = Field(default=7, ge=0, le=60)
    guardrail_max_response_hours: int = Field(default=12, ge=1, le=72)
    guardrail_risk_tolerance: str = Field(default="medio", pattern="^(baixo|medio|alto)$")
    flash_auction_window_minutes: int = Field(default=90, ge=15, le=360)
    flash_spoilage_risk_threshold: float = Field(default=62, ge=30, le=98)
    auto_execute_limit_per_day: int = Field(default=2, ge=0, le=10)


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


class AgendaAutonomousExecuteIn(BaseModel):
    action_type: str = Field(pattern="^(flash_auction|auto_negotiation)$")
    offer_id: str = Field(min_length=1, max_length=80)
    mode: str = Field(default="commit", pattern="^(commit|rollback)$")
    buyer_user_id: int | None = Field(default=None, ge=1)


class GovernanceReviewResolveIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    notes: str | None = Field(default=None, max_length=1000)


class BusinessOSOrchestrateEventIn(BaseModel):
    event_type: str = Field(min_length=3, max_length=120)
    event_domain: str | None = Field(default=None, max_length=80)
    entity_type: str | None = Field(default=None, max_length=80)
    entity_id: str | None = Field(default=None, max_length=120)
    metadata: dict = Field(default_factory=dict)
    risk_level: str | None = Field(default=None, pattern="^(low|medium|high)$")
    risk_score: float | None = Field(default=None, ge=0, le=1)


class BusinessOSSignalEventIn(BaseModel):
    event_type: str = Field(min_length=3, max_length=120)
    event_domain: str | None = Field(default=None, max_length=80)
    entity_type: str | None = Field(default=None, max_length=80)
    entity_id: str | None = Field(default=None, max_length=120)
    metadata: dict = Field(default_factory=dict)
    risk_level: str | None = Field(default=None, pattern="^(low|medium|high)$")
    risk_score: float | None = Field(default=None, ge=0, le=1)


class BusinessOSSignalPipelineIn(BaseModel):
    source: str = Field(default="business_os_pipeline", min_length=3, max_length=120)
    persist_only_accepted: bool = True
    events: list[BusinessOSSignalEventIn] = Field(default_factory=list, min_length=1, max_length=200)


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
        "auto_negotiation_enabled": True,
        "auto_flash_auction_enabled": True,
        "guardrail_max_discount_pct": 8,
        "guardrail_min_net_margin_pct": 7,
        "guardrail_max_response_hours": 12,
        "guardrail_risk_tolerance": "medio",
        "flash_auction_window_minutes": 90,
        "flash_spoilage_risk_threshold": 62,
        "auto_execute_limit_per_day": 2,
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


def _require_admin_user(user: User) -> None:
    require_platform_roles(
        user,
        allowed_roles={
            PLATFORM_ROLE_STAFF_ADMIN,
            PLATFORM_ROLE_STAFF_OPS,
            PLATFORM_ROLE_STAFF_SUPPORT,
        },
        detail="Acesso restrito ao staff da plataforma",
    )


def _require_platform_write_user(user: User) -> None:
    require_platform_roles(
        user,
        allowed_roles={
            PLATFORM_ROLE_STAFF_ADMIN,
            PLATFORM_ROLE_STAFF_OPS,
        },
        detail="Ação restrita a operadores da plataforma",
    )


def _resolve_account_user_ids(db: Session, current_user: User) -> list[int]:
    account_scope_id = resolve_account_scope_id(current_user)
    rows = (
        db.query(User.id)
        .filter(
            User.account_scope_id == account_scope_id,
            User.is_active.is_(True),
        )
        .all()
    )
    ids = sorted({int(item[0]) for item in rows if item and item[0] is not None})
    if ids:
        return ids
    return [int(current_user.id)]


def _require_account_ai_operator(
    *,
    db: Session,
    user: User,
    minimum_plan: str = "pro",
) -> dict:
    require_account_roles(
        user,
        allowed_roles={
            ACCOUNT_ROLE_OWNER,
            ACCOUNT_ROLE_MANAGER,
            ACCOUNT_ROLE_ANALYST,
        },
        detail="Acesso restrito ao gestor da conta",
    )
    if settings.AI_ENFORCE_SUBSCRIPTION_GUARDRAILS:
        return require_minimum_plan(
            db=db,
            user_id=int(user.id),
            minimum_plan=minimum_plan,
            detail=f"Recurso disponível para plano {minimum_plan} ou superior.",
        )

    return capabilities_for_plan("enterprise")


def _resolve_user_ai_capabilities(db: Session, user: User) -> dict:
    if settings.AI_ENFORCE_SUBSCRIPTION_GUARDRAILS:
        return capabilities_for_user(db, int(user.id))
    return capabilities_for_plan("enterprise")


def _count_today_ai_decisions(db: Session, user_id: int) -> int:
    now = datetime.now(timezone.utc)
    day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    return int(
        db.query(func.count(UserBehaviorLog.id))
        .filter(
            UserBehaviorLog.user_id == int(user_id),
            UserBehaviorLog.event_type == "ai_decision_recorded",
            UserBehaviorLog.created_at >= day_start,
            UserBehaviorLog.created_at < day_end,
        )
        .scalar()
        or 0
    )


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resolve_window(
    *,
    days: int,
    since: datetime | None = None,
    until: datetime | None = None,
) -> tuple[datetime, datetime, int]:
    window_end = _coerce_utc(until) if isinstance(until, datetime) else datetime.now(timezone.utc)
    if isinstance(since, datetime):
        window_start = _coerce_utc(since)
    else:
        window_start = window_end - timedelta(days=max(1, int(days)))

    if window_start >= window_end:
        window_start = window_end - timedelta(days=max(1, int(days)))

    total_seconds = max(1.0, (window_end - window_start).total_seconds())
    window_days = max(1, int(round(total_seconds / 86400.0)))
    return window_start, window_end, window_days


def _build_ai_governance_summary_payload(
    *,
    db: Session,
    days: int,
    include_recent: bool,
    since: datetime | None = None,
    until: datetime | None = None,
    user_ids: list[int] | None = None,
) -> dict:
    window_start, window_end, window_days = _resolve_window(
        days=days,
        since=since,
        until=until,
    )
    query = (
        db.query(UserBehaviorLog)
        .filter(
            UserBehaviorLog.event_type == "ai_decision_recorded",
            UserBehaviorLog.created_at >= window_start,
            UserBehaviorLog.created_at < window_end,
        )
    )
    if user_ids:
        query = query.filter(UserBehaviorLog.user_id.in_(list(user_ids)))

    rows = query.order_by(UserBehaviorLog.created_at.desc()).all()

    total = len(rows)
    requires_review = 0
    by_action = {
        "auto_negotiation": 0,
        "flash_auction": 0,
        "unknown": 0,
    }
    by_outcome: dict[str, int] = {}
    by_risk = {
        "low": 0,
        "medium": 0,
        "high": 0,
        "unknown": 0,
    }

    recent: list[dict] = []

    for row in rows:
        meta = row.meta_json if isinstance(row.meta_json, dict) else {}
        decision = meta.get("decision") if isinstance(meta.get("decision"), dict) else {}

        action = str(decision.get("action_type") or "unknown")
        outcome = str(decision.get("decision_outcome") or "unknown")
        risk_level = str(decision.get("risk_level") or "unknown")

        if action not in by_action:
            by_action["unknown"] += 1
        else:
            by_action[action] += 1

        by_outcome[outcome] = int(by_outcome.get(outcome, 0)) + 1

        if risk_level not in by_risk:
            by_risk["unknown"] += 1
        else:
            by_risk[risk_level] += 1

        if bool(decision.get("requires_human_review")):
            requires_review += 1

        if include_recent and len(recent) < 25:
            recent.append(
                {
                    "event_id": row.id,
                    "user_id": row.user_id,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "action_type": action,
                    "decision_outcome": outcome,
                    "risk_level": risk_level,
                    "requires_human_review": bool(decision.get("requires_human_review")),
                }
            )

    review_rate = round((requires_review / total) * 100, 2) if total > 0 else 0.0
    autonomous_approved = int(by_outcome.get("approved_autonomous", 0))
    autonomous_rate = round((autonomous_approved / total) * 100, 2) if total > 0 else 0.0

    review_queue_query = (
        db.query(AISuggestion)
        .filter(
            AISuggestion.module == AIDecisionReviewService.MODULE,
            AISuggestion.suggestion_type == AIDecisionReviewService.SUGGESTION_TYPE,
            AISuggestion.created_at >= window_start,
            AISuggestion.created_at < window_end,
        )
    )
    if user_ids:
        review_queue_query = review_queue_query.filter(AISuggestion.user_id.in_(list(user_ids)))

    review_queue_rows = review_queue_query.all()
    queue_total = len(review_queue_rows)
    queue_pending = 0
    queue_approved = 0
    queue_rejected = 0
    for row in review_queue_rows:
        status = str(row.status or "").strip().lower()
        if status == AIDecisionReviewService.STATUS_PENDING:
            queue_pending += 1
        elif status == AIDecisionReviewService.STATUS_APPROVED:
            queue_approved += 1
        elif status == AIDecisionReviewService.STATUS_REJECTED:
            queue_rejected += 1

    return {
        "window_days": window_days,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "totals": {
            "decisions": total,
            "requires_human_review": requires_review,
            "review_rate": review_rate,
            "approved_autonomous": autonomous_approved,
            "autonomous_rate": autonomous_rate,
        },
        "review_queue": {
            "total": queue_total,
            "pending": queue_pending,
            "approved": queue_approved,
            "rejected": queue_rejected,
        },
        "by_action": by_action,
        "by_outcome": by_outcome,
        "by_risk_level": by_risk,
        "recent": recent if include_recent else [],
    }


def _build_governance_summary_csv(summary_payload: dict) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "section",
            "key",
            "value",
            "event_id",
            "user_id",
            "created_at",
            "action_type",
            "decision_outcome",
            "risk_level",
            "requires_human_review",
        ]
    )

    writer.writerow(["meta", "window_days", summary_payload.get("window_days", 0), "", "", "", "", "", "", ""])

    totals = summary_payload.get("totals", {}) if isinstance(summary_payload.get("totals"), dict) else {}
    for key in [
        "decisions",
        "requires_human_review",
        "review_rate",
        "approved_autonomous",
        "autonomous_rate",
    ]:
        writer.writerow(["totals", key, totals.get(key, 0), "", "", "", "", "", "", ""])

    review_queue = summary_payload.get("review_queue", {}) if isinstance(summary_payload.get("review_queue"), dict) else {}
    for key in ["total", "pending", "approved", "rejected"]:
        writer.writerow(["review_queue", key, review_queue.get(key, 0), "", "", "", "", "", "", ""])

    by_action = summary_payload.get("by_action", {}) if isinstance(summary_payload.get("by_action"), dict) else {}
    for key in sorted(by_action.keys()):
        writer.writerow(["by_action", key, by_action.get(key, 0), "", "", "", "", "", "", ""])

    by_outcome = summary_payload.get("by_outcome", {}) if isinstance(summary_payload.get("by_outcome"), dict) else {}
    for key in sorted(by_outcome.keys()):
        writer.writerow(["by_outcome", key, by_outcome.get(key, 0), "", "", "", "", "", "", ""])

    by_risk_level = summary_payload.get("by_risk_level", {}) if isinstance(summary_payload.get("by_risk_level"), dict) else {}
    for key in sorted(by_risk_level.keys()):
        writer.writerow(["by_risk_level", key, by_risk_level.get(key, 0), "", "", "", "", "", "", ""])

    recent = summary_payload.get("recent", []) if isinstance(summary_payload.get("recent"), list) else []
    for item in recent:
        row = item if isinstance(item, dict) else {}
        writer.writerow(
            [
                "recent",
                "",
                "",
                row.get("event_id", ""),
                row.get("user_id", ""),
                row.get("created_at", ""),
                row.get("action_type", ""),
                row.get("decision_outcome", ""),
                row.get("risk_level", ""),
                row.get("requires_human_review", ""),
            ]
        )

    return buffer.getvalue()


def _build_governance_summary_weekly_csv(*, db: Session, days: int) -> str:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    decision_rows = (
        db.query(UserBehaviorLog)
        .filter(
            UserBehaviorLog.event_type == "ai_decision_recorded",
            UserBehaviorLog.created_at >= since,
        )
        .all()
    )

    review_queue_rows = (
        db.query(AISuggestion)
        .filter(
            AISuggestion.module == AIDecisionReviewService.MODULE,
            AISuggestion.suggestion_type == AIDecisionReviewService.SUGGESTION_TYPE,
            AISuggestion.created_at >= since,
        )
        .all()
    )

    weekly: dict[tuple[int, int], dict] = {}

    def ensure_bucket(timestamp: datetime | None) -> dict | None:
        if timestamp is None:
            return None

        safe_ts = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
        iso = safe_ts.isocalendar()
        key = (int(iso.year), int(iso.week))

        if key not in weekly:
            week_start = date.fromisocalendar(key[0], key[1], 1)
            weekly[key] = {
                "week_start": week_start.isoformat(),
                "week_iso": f"{key[0]}-W{key[1]:02d}",
                "decisions": 0,
                "requires_human_review": 0,
                "approved_autonomous": 0,
                "queue_total": 0,
                "queue_pending": 0,
                "queue_approved": 0,
                "queue_rejected": 0,
                "auto_negotiation": 0,
                "flash_auction": 0,
                "unknown_action": 0,
                "low_risk": 0,
                "medium_risk": 0,
                "high_risk": 0,
                "unknown_risk": 0,
            }

        return weekly[key]

    for row in decision_rows:
        bucket = ensure_bucket(row.created_at)
        if bucket is None:
            continue

        meta = row.meta_json if isinstance(row.meta_json, dict) else {}
        decision = meta.get("decision") if isinstance(meta.get("decision"), dict) else {}

        action = str(decision.get("action_type") or "unknown")
        outcome = str(decision.get("decision_outcome") or "unknown")
        risk_level = str(decision.get("risk_level") or "unknown")

        bucket["decisions"] += 1
        if bool(decision.get("requires_human_review")):
            bucket["requires_human_review"] += 1

        if outcome == "approved_autonomous":
            bucket["approved_autonomous"] += 1

        if action == "auto_negotiation":
            bucket["auto_negotiation"] += 1
        elif action == "flash_auction":
            bucket["flash_auction"] += 1
        else:
            bucket["unknown_action"] += 1

        if risk_level == "low":
            bucket["low_risk"] += 1
        elif risk_level == "medium":
            bucket["medium_risk"] += 1
        elif risk_level == "high":
            bucket["high_risk"] += 1
        else:
            bucket["unknown_risk"] += 1

    for row in review_queue_rows:
        bucket = ensure_bucket(row.created_at)
        if bucket is None:
            continue

        status = str(row.status or "").strip().lower()
        bucket["queue_total"] += 1
        if status == AIDecisionReviewService.STATUS_PENDING:
            bucket["queue_pending"] += 1
        elif status == AIDecisionReviewService.STATUS_APPROVED:
            bucket["queue_approved"] += 1
        elif status == AIDecisionReviewService.STATUS_REJECTED:
            bucket["queue_rejected"] += 1

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "week_start",
            "week_iso",
            "decisions",
            "requires_human_review",
            "review_rate",
            "approved_autonomous",
            "autonomous_rate",
            "queue_total",
            "queue_pending",
            "queue_approved",
            "queue_rejected",
            "auto_negotiation",
            "flash_auction",
            "unknown_action",
            "low_risk",
            "medium_risk",
            "high_risk",
            "unknown_risk",
        ]
    )

    for key in sorted(weekly.keys(), reverse=True):
        bucket = weekly[key]
        decisions = int(bucket["decisions"])
        requires_human_review = int(bucket["requires_human_review"])
        approved_autonomous = int(bucket["approved_autonomous"])

        review_rate = round((requires_human_review / decisions) * 100, 2) if decisions > 0 else 0.0
        autonomous_rate = round((approved_autonomous / decisions) * 100, 2) if decisions > 0 else 0.0

        writer.writerow(
            [
                bucket["week_start"],
                bucket["week_iso"],
                decisions,
                requires_human_review,
                review_rate,
                approved_autonomous,
                autonomous_rate,
                int(bucket["queue_total"]),
                int(bucket["queue_pending"]),
                int(bucket["queue_approved"]),
                int(bucket["queue_rejected"]),
                int(bucket["auto_negotiation"]),
                int(bucket["flash_auction"]),
                int(bucket["unknown_action"]),
                int(bucket["low_risk"]),
                int(bucket["medium_risk"]),
                int(bucket["high_risk"]),
                int(bucket["unknown_risk"]),
            ]
        )

    return buffer.getvalue()


def _pct(num: int | float, den: int | float) -> float:
    denominator = float(den or 0)
    if denominator <= 0:
        return 0.0
    return round((float(num or 0) / denominator) * 100, 2)


_DECISION_COST_MODEL = {
    "base_by_action": {
        "auto_negotiation": 0.12,
        "flash_auction": 0.10,
        "unknown": 0.08,
    },
    "review_surcharge": 0.05,
    "rollback_surcharge": 0.07,
    "blocked_surcharge": 0.02,
}

_AUTONOMY_LEVELS = ["L0", "L1", "L2", "L3"]
_DEFAULT_AUTONOMY_LEVELS = {
    "auto_negotiation": "L1",
    "flash_auction": "L1",
    "unknown": "L1",
}
_AUTONOMY_RULES = {
    "min_samples": 6,
    "upgrade": {
        "autonomous_rate_min": 72.0,
        "review_rate_max": 35.0,
        "rollback_rate_max": 5.0,
        "blocked_rate_max": 20.0,
    },
    "downgrade": {
        "review_rate_min": 70.0,
        "rollback_rate_min": 12.0,
        "blocked_rate_min": 35.0,
    },
}


def _estimate_decision_cost(
    *,
    action_type: str,
    requires_human_review: bool,
    rolled_back: bool,
    committed: bool,
) -> float:
    normalized_action = str(action_type or "unknown").strip().lower()
    base_by_action = _DECISION_COST_MODEL["base_by_action"]
    base_cost = float(base_by_action.get(normalized_action, base_by_action["unknown"]))

    cost = base_cost
    if requires_human_review:
        cost += float(_DECISION_COST_MODEL["review_surcharge"])
    if rolled_back:
        cost += float(_DECISION_COST_MODEL["rollback_surcharge"])
    if not committed:
        cost += float(_DECISION_COST_MODEL["blocked_surcharge"])

    return round(cost, 4)


def _build_ai_decision_cost_payload(
    *,
    db: Session,
    days: int,
    since: datetime | None = None,
    until: datetime | None = None,
    user_ids: list[int] | None = None,
) -> dict:
    window_start, window_end, window_days = _resolve_window(
        days=days,
        since=since,
        until=until,
    )

    query = (
        db.query(UserBehaviorLog)
        .filter(
            UserBehaviorLog.event_type == "ai_decision_recorded",
            UserBehaviorLog.created_at >= window_start,
            UserBehaviorLog.created_at < window_end,
        )
    )
    if user_ids:
        query = query.filter(UserBehaviorLog.user_id.in_(list(user_ids)))

    rows = query.all()

    total_cost = 0.0
    autonomous_approved = 0
    requires_review_total = 0
    rolled_back_total = 0
    blocked_total = 0

    by_action: dict[str, dict[str, float | int]] = {}

    for row in rows:
        meta = row.meta_json if isinstance(row.meta_json, dict) else {}
        decision = meta.get("decision") if isinstance(meta.get("decision"), dict) else {}
        result = meta.get("result") if isinstance(meta.get("result"), dict) else {}

        action = str(decision.get("action_type") or "unknown").strip().lower() or "unknown"
        outcome = str(decision.get("decision_outcome") or "unknown").strip().lower()
        requires_review = bool(decision.get("requires_human_review"))
        rolled_back = bool(result.get("rolled_back"))
        committed = bool(result.get("committed", outcome != "blocked"))

        estimated_cost = _estimate_decision_cost(
            action_type=action,
            requires_human_review=requires_review,
            rolled_back=rolled_back,
            committed=committed,
        )

        total_cost += estimated_cost
        if outcome == "approved_autonomous":
            autonomous_approved += 1
        if requires_review:
            requires_review_total += 1
        if rolled_back:
            rolled_back_total += 1
        if not committed or outcome == "blocked":
            blocked_total += 1

        action_bucket = by_action.setdefault(
            action,
            {
                "decisions": 0,
                "estimated_total_cost": 0.0,
                "autonomous_approved": 0,
                "requires_human_review": 0,
                "rolled_back": 0,
                "blocked": 0,
            },
        )
        action_bucket["decisions"] = int(action_bucket["decisions"]) + 1
        action_bucket["estimated_total_cost"] = float(action_bucket["estimated_total_cost"]) + estimated_cost
        if outcome == "approved_autonomous":
            action_bucket["autonomous_approved"] = int(action_bucket["autonomous_approved"]) + 1
        if requires_review:
            action_bucket["requires_human_review"] = int(action_bucket["requires_human_review"]) + 1
        if rolled_back:
            action_bucket["rolled_back"] = int(action_bucket["rolled_back"]) + 1
        if not committed or outcome == "blocked":
            action_bucket["blocked"] = int(action_bucket["blocked"]) + 1

    total_decisions = len(rows)
    avg_cost = round((total_cost / total_decisions), 4) if total_decisions > 0 else 0.0
    cost_per_autonomous = round((total_cost / autonomous_approved), 4) if autonomous_approved > 0 else 0.0

    by_action_items: list[dict] = []
    for action, item in by_action.items():
        action_decisions = int(item.get("decisions", 0) or 0)
        action_total_cost = float(item.get("estimated_total_cost", 0.0) or 0.0)
        by_action_items.append(
            {
                "action_type": action,
                "decisions": action_decisions,
                "estimated_total_cost": round(action_total_cost, 4),
                "estimated_avg_cost": round((action_total_cost / action_decisions), 4) if action_decisions > 0 else 0.0,
                "autonomous_approved": int(item.get("autonomous_approved", 0) or 0),
                "requires_human_review": int(item.get("requires_human_review", 0) or 0),
                "rolled_back": int(item.get("rolled_back", 0) or 0),
                "blocked": int(item.get("blocked", 0) or 0),
            }
        )

    by_action_items.sort(
        key=lambda item: (
            float(item.get("estimated_total_cost", 0.0) or 0.0),
            int(item.get("decisions", 0) or 0),
        ),
        reverse=True,
    )

    return {
        "window_days": window_days,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "totals": {
            "decisions": total_decisions,
            "estimated_total_cost": round(total_cost, 4),
            "estimated_avg_cost": avg_cost,
            "autonomous_approved": autonomous_approved,
            "cost_per_autonomous_approved": cost_per_autonomous,
            "requires_human_review": requires_review_total,
            "rolled_back": rolled_back_total,
            "blocked": blocked_total,
        },
        "by_action": by_action_items,
        "cost_model": _DECISION_COST_MODEL,
    }


def _normalize_agent_level(value: str | None) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in _AUTONOMY_LEVELS:
        return normalized
    return "L1"


def _shift_agent_level(current_level: str, delta: int) -> str:
    current = _normalize_agent_level(current_level)
    index = _AUTONOMY_LEVELS.index(current)
    target = max(0, min(len(_AUTONOMY_LEVELS) - 1, index + int(delta)))
    return _AUTONOMY_LEVELS[target]


def _load_current_autonomy_levels(db: Session) -> dict[str, str]:
    latest = (
        db.query(UserBehaviorLog)
        .filter(
            UserBehaviorLog.event_type == "ai_autonomy_policy_applied",
            UserBehaviorLog.entity_type == "ai_autonomy_policy",
            UserBehaviorLog.entity_id == "global",
        )
        .order_by(UserBehaviorLog.created_at.desc())
        .first()
    )

    levels = dict(_DEFAULT_AUTONOMY_LEVELS)
    if latest and isinstance(latest.meta_json, dict):
        raw_levels = latest.meta_json.get("levels_applied")
        if not isinstance(raw_levels, dict):
            raw_levels = latest.meta_json.get("levels_proposed")
        if not isinstance(raw_levels, dict):
            raw_levels = latest.meta_json.get("levels")

        if isinstance(raw_levels, dict):
            for key, value in raw_levels.items():
                levels[str(key).strip().lower() or "unknown"] = _normalize_agent_level(str(value))

    return levels


def _build_ai_autonomy_policy_payload(
    *,
    db: Session,
    days: int,
    since: datetime | None = None,
    until: datetime | None = None,
    current_levels: dict[str, str] | None = None,
) -> dict:
    window_start, window_end, window_days = _resolve_window(
        days=days,
        since=since,
        until=until,
    )

    levels_current = dict(current_levels or _load_current_autonomy_levels(db))
    for action, default_level in _DEFAULT_AUTONOMY_LEVELS.items():
        levels_current.setdefault(action, default_level)

    rows = (
        db.query(UserBehaviorLog)
        .filter(
            UserBehaviorLog.event_type == "ai_decision_recorded",
            UserBehaviorLog.created_at >= window_start,
            UserBehaviorLog.created_at < window_end,
        )
        .all()
    )

    stats_by_agent: dict[str, dict[str, int]] = {}
    for row in rows:
        meta = row.meta_json if isinstance(row.meta_json, dict) else {}
        decision = meta.get("decision") if isinstance(meta.get("decision"), dict) else {}
        result = meta.get("result") if isinstance(meta.get("result"), dict) else {}

        action = str(decision.get("action_type") or "unknown").strip().lower() or "unknown"
        outcome = str(decision.get("decision_outcome") or "unknown").strip().lower()
        requires_review = bool(decision.get("requires_human_review"))
        rolled_back = bool(result.get("rolled_back"))
        committed = bool(result.get("committed", outcome != "blocked"))
        blocked = (not committed) or outcome == "blocked"

        bucket = stats_by_agent.setdefault(
            action,
            {
                "decisions": 0,
                "autonomous_approved": 0,
                "requires_human_review": 0,
                "rolled_back": 0,
                "blocked": 0,
            },
        )
        bucket["decisions"] += 1
        if outcome == "approved_autonomous":
            bucket["autonomous_approved"] += 1
        if requires_review:
            bucket["requires_human_review"] += 1
        if rolled_back:
            bucket["rolled_back"] += 1
        if blocked:
            bucket["blocked"] += 1

    levels_proposed = dict(levels_current)
    actions = sorted(set(levels_current.keys()) | set(stats_by_agent.keys()))
    agents_payload: list[dict] = []

    min_samples = int(_AUTONOMY_RULES["min_samples"])
    up_rules = _AUTONOMY_RULES["upgrade"]
    down_rules = _AUTONOMY_RULES["downgrade"]

    for action in actions:
        stats = stats_by_agent.get(
            action,
            {
                "decisions": 0,
                "autonomous_approved": 0,
                "requires_human_review": 0,
                "rolled_back": 0,
                "blocked": 0,
            },
        )
        decisions = int(stats.get("decisions", 0) or 0)
        autonomous_rate = _pct(int(stats.get("autonomous_approved", 0) or 0), decisions)
        review_rate = _pct(int(stats.get("requires_human_review", 0) or 0), decisions)
        rollback_rate = _pct(int(stats.get("rolled_back", 0) or 0), decisions)
        blocked_rate = _pct(int(stats.get("blocked", 0) or 0), decisions)

        current_level = _normalize_agent_level(levels_current.get(action, "L1"))
        recommendation = "hold"
        reason = "performance_within_expected_range"

        if decisions < min_samples:
            reason = "insufficient_sample"
            proposed_level = current_level
        elif (
            review_rate >= float(down_rules["review_rate_min"])
            or rollback_rate >= float(down_rules["rollback_rate_min"])
            or blocked_rate >= float(down_rules["blocked_rate_min"])
        ):
            recommendation = "downgrade"
            reason = "risk_or_quality_breach"
            proposed_level = _shift_agent_level(current_level, -1)
        elif (
            autonomous_rate >= float(up_rules["autonomous_rate_min"])
            and review_rate <= float(up_rules["review_rate_max"])
            and rollback_rate <= float(up_rules["rollback_rate_max"])
            and blocked_rate <= float(up_rules["blocked_rate_max"])
        ):
            recommendation = "upgrade"
            reason = "high_stability_and_autonomy"
            proposed_level = _shift_agent_level(current_level, 1)
        else:
            proposed_level = current_level

        levels_proposed[action] = proposed_level
        agents_payload.append(
            {
                "agent": action,
                "current_level": current_level,
                "proposed_level": proposed_level,
                "recommendation": recommendation,
                "reason": reason,
                "metrics": {
                    "decisions": decisions,
                    "autonomous_rate": autonomous_rate,
                    "review_rate": review_rate,
                    "rollback_rate": rollback_rate,
                    "blocked_rate": blocked_rate,
                },
            }
        )

    upgrades = sum(1 for item in agents_payload if item["recommendation"] == "upgrade" and item["proposed_level"] != item["current_level"])
    downgrades = sum(1 for item in agents_payload if item["recommendation"] == "downgrade" and item["proposed_level"] != item["current_level"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": window_days,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "rules": _AUTONOMY_RULES,
        "levels_current": levels_current,
        "levels_proposed": levels_proposed,
        "summary": {
            "upgrade_candidates": upgrades,
            "downgrade_candidates": downgrades,
            "hold": max(0, len(agents_payload) - upgrades - downgrades),
        },
        "agents": agents_payload,
    }


def _week_window_bounds(week_offset: int = 0) -> tuple[str, datetime, datetime]:
    safe_offset = max(0, int(week_offset))
    reference_day = (datetime.now(timezone.utc) - timedelta(days=safe_offset * 7)).date()
    week_start = reference_day - timedelta(days=reference_day.weekday())
    week_end = week_start + timedelta(days=7)

    iso = week_start.isocalendar()
    week_iso = f"{int(iso.year)}-W{int(iso.week):02d}"
    window_start = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
    window_end = datetime.combine(week_end, time.min, tzinfo=timezone.utc)
    return week_iso, window_start, window_end


def _build_ai_executive_cockpit_payload(
    *,
    db: Session,
    days: int,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict:
    window_start, window_end, window_days = _resolve_window(
        days=days,
        since=since,
        until=until,
    )

    total_users = int(db.query(func.count(User.id)).scalar() or 0)
    new_users = int(
        db.query(func.count(User.id))
        .filter(User.created_at >= window_start, User.created_at < window_end)
        .scalar()
        or 0
    )
    active_offers = int(
        db.query(func.count(Offer.id))
        .filter(Offer.status == "active")
        .scalar()
        or 0
    )
    inbound_messages = int(
        db.query(func.count(Message.id))
        .filter(Message.created_at >= window_start, Message.created_at < window_end)
        .scalar()
        or 0
    )

    orders_rows = (
        db.query(Order)
        .filter(Order.created_at >= window_start, Order.created_at < window_end)
        .all()
    )
    total_orders = len(orders_rows)
    paid_or_delivered_orders = 0
    delivered_orders = 0
    cancelled_orders = 0
    gross_revenue = 0.0

    customers_window: dict[int, int] = {}
    by_payment_segment: dict[str, dict[str, float | int]] = {}

    for row in orders_rows:
        status = (
            row.status.value
            if hasattr(row.status, "value")
            else str(row.status or "").strip().lower()
        )
        payment_method = str(row.payment_method or "unknown").strip().lower() or "unknown"

        bucket = by_payment_segment.setdefault(
            payment_method,
            {
                "total_orders": 0,
                "paid_or_delivered_orders": 0,
                "delivered_orders": 0,
                "cancelled_orders": 0,
                "gross_revenue": 0.0,
            },
        )

        bucket["total_orders"] = int(bucket["total_orders"]) + 1

        if row.customer_id is not None:
            customer_id = int(row.customer_id)
            customers_window[customer_id] = int(customers_window.get(customer_id, 0)) + 1

        if status in {"paid", "delivered"}:
            paid_or_delivered_orders += 1
            amount = float(row.total_amount or 0.0)
            gross_revenue += amount
            bucket["paid_or_delivered_orders"] = int(bucket["paid_or_delivered_orders"]) + 1
            bucket["gross_revenue"] = float(bucket["gross_revenue"]) + amount

        if status == "delivered":
            delivered_orders += 1
            bucket["delivered_orders"] = int(bucket["delivered_orders"]) + 1

        if status == "cancelled":
            cancelled_orders += 1
            bucket["cancelled_orders"] = int(bucket["cancelled_orders"]) + 1

    total_customers_window = len(customers_window)
    recurring_customers = sum(1 for count in customers_window.values() if int(count) >= 2)

    active_subscriptions = int(
        db.query(func.count(Subscription.id))
        .filter(Subscription.status == "active")
        .scalar()
        or 0
    )
    new_active_subscriptions = int(
        db.query(func.count(Subscription.id))
        .filter(
            Subscription.created_at >= window_start,
            Subscription.created_at < window_end,
            Subscription.status == "active",
        )
        .scalar()
        or 0
    )

    checkouts_requested = int(
        db.query(func.count(UserBehaviorLog.id))
        .filter(
            UserBehaviorLog.created_at >= window_start,
            UserBehaviorLog.created_at < window_end,
            UserBehaviorLog.event_type.in_(
                [
                    "payment_checkout_requested",
                    "store_checkout_session_requested",
                    "payment_subscription_cta_event",
                ]
            ),
        )
        .scalar()
        or 0
    )

    unresolved_admin_alerts = int(
        db.query(func.count(Notification.id))
        .filter(
            Notification.notification_type == "admin_alert",
            Notification.is_read.is_(False),
        )
        .scalar()
        or 0
    )

    governance = _build_ai_governance_summary_payload(
        db=db,
        days=window_days,
        include_recent=False,
        since=window_start,
        until=window_end,
    )
    governance_totals = governance.get("totals", {}) if isinstance(governance.get("totals"), dict) else {}
    governance_queue = governance.get("review_queue", {}) if isinstance(governance.get("review_queue"), dict) else {}

    cost_monitor = _build_ai_decision_cost_payload(
        db=db,
        days=window_days,
        since=window_start,
        until=window_end,
    )
    autonomy_preview = _build_ai_autonomy_policy_payload(
        db=db,
        days=window_days,
        since=window_start,
        until=window_end,
    )

    ai_decisions_total = int(governance_totals.get("decisions", 0) or 0)
    ai_review_rate = float(governance_totals.get("review_rate", 0.0) or 0.0)
    ai_autonomous_rate = float(governance_totals.get("autonomous_rate", 0.0) or 0.0)

    order_conversion_rate = _pct(paid_or_delivered_orders, total_orders)
    order_cancel_rate = _pct(cancelled_orders, total_orders)
    recurring_customers_rate = _pct(recurring_customers, total_customers_window)

    profitability_by_segment: list[dict] = []
    for segment, stats in by_payment_segment.items():
        segment_total_orders = int(stats.get("total_orders", 0) or 0)
        segment_converted = int(stats.get("paid_or_delivered_orders", 0) or 0)
        segment_cancelled = int(stats.get("cancelled_orders", 0) or 0)
        segment_revenue = float(stats.get("gross_revenue", 0.0) or 0.0)

        profitability_by_segment.append(
            {
                "segment": segment,
                "total_orders": segment_total_orders,
                "paid_or_delivered_orders": segment_converted,
                "delivered_orders": int(stats.get("delivered_orders", 0) or 0),
                "cancelled_orders": segment_cancelled,
                "order_conversion_rate": _pct(segment_converted, segment_total_orders),
                "cancel_rate": _pct(segment_cancelled, segment_total_orders),
                "gross_revenue": round(segment_revenue, 2),
                "avg_ticket": round((segment_revenue / segment_converted), 2) if segment_converted > 0 else 0.0,
            }
        )

    profitability_by_segment.sort(
        key=lambda item: (
            float(item.get("gross_revenue", 0.0) or 0.0),
            float(item.get("order_conversion_rate", 0.0) or 0.0),
        ),
        reverse=True,
    )

    targets = {
        "order_conversion_rate": 55.0,
        "order_cancel_rate_max": 15.0,
        "ai_autonomous_rate": 65.0,
        "ai_review_rate_max": 45.0,
        "recurring_customers_rate": 25.0,
    }

    goal_gaps = [
        {
            "metric": "order_conversion_rate",
            "current": order_conversion_rate,
            "target": float(targets["order_conversion_rate"]),
            "gap": round(order_conversion_rate - float(targets["order_conversion_rate"]), 2),
            "status": "below_target" if order_conversion_rate < float(targets["order_conversion_rate"]) else "on_track",
        },
        {
            "metric": "ai_autonomous_rate",
            "current": ai_autonomous_rate,
            "target": float(targets["ai_autonomous_rate"]),
            "gap": round(ai_autonomous_rate - float(targets["ai_autonomous_rate"]), 2),
            "status": "below_target" if ai_autonomous_rate < float(targets["ai_autonomous_rate"]) else "on_track",
        },
        {
            "metric": "ai_review_rate",
            "current": ai_review_rate,
            "target": float(targets["ai_review_rate_max"]),
            "gap": round(float(targets["ai_review_rate_max"]) - ai_review_rate, 2),
            "status": "above_limit" if ai_review_rate > float(targets["ai_review_rate_max"]) else "within_limit",
        },
        {
            "metric": "order_cancel_rate",
            "current": order_cancel_rate,
            "target": float(targets["order_cancel_rate_max"]),
            "gap": round(float(targets["order_cancel_rate_max"]) - order_cancel_rate, 2),
            "status": "above_limit" if order_cancel_rate > float(targets["order_cancel_rate_max"]) else "within_limit",
        },
        {
            "metric": "recurring_customers_rate",
            "current": recurring_customers_rate,
            "target": float(targets["recurring_customers_rate"]),
            "gap": round(recurring_customers_rate - float(targets["recurring_customers_rate"]), 2),
            "status": "below_target" if recurring_customers_rate < float(targets["recurring_customers_rate"]) else "on_track",
        },
    ]

    alerts: list[str] = []
    recommended_actions: list[str] = []

    if total_orders > 0 and order_conversion_rate < float(targets["order_conversion_rate"]):
        alerts.append("Conversão de pedidos abaixo da meta operacional.")
        recommended_actions.append("Revisar funil de checkout e reduzir etapas de fricção no pagamento.")

    if total_orders > 0 and order_cancel_rate > float(targets["order_cancel_rate_max"]):
        alerts.append("Taxa de cancelamento de pedidos acima do limite saudável.")
        recommended_actions.append("Ativar rotina de prevenção de cancelamento com confirmação proativa e SLA de atendimento.")

    if ai_decisions_total > 0 and ai_review_rate > float(targets["ai_review_rate_max"]):
        alerts.append("Fila de revisão humana elevada nas decisões IA.")
        recommended_actions.append("Recalibrar guardrails de risco para elevar autonomia com segurança.")

    if ai_decisions_total > 0 and ai_autonomous_rate < float(targets["ai_autonomous_rate"]):
        alerts.append("Autonomia IA abaixo da meta para a janela selecionada.")
        recommended_actions.append("Revisar políticas por risco e promover ações de baixo risco para execução automática.")

    if total_customers_window > 0 and recurring_customers_rate < float(targets["recurring_customers_rate"]):
        alerts.append("Recorrência de clientes abaixo da meta de retenção.")
        recommended_actions.append("Rodar campanha de retenção por segmento com oferta de recompra contextual.")

    if int(governance_queue.get("pending", 0) or 0) > 0:
        alerts.append("Existem itens pendentes na fila L1 de governança.")
        recommended_actions.append("Aplicar rotina diária de resolução da fila L1 com prioridade por risco alto.")

    if unresolved_admin_alerts > 0:
        alerts.append("Há alertas administrativos não lidos afetando a operação.")
        recommended_actions.append("Definir dono por alerta crítico e acompanhar fechamento em até 24h.")

    if not alerts:
        alerts.append("Operação IA estável na janela monitorada.")

    opportunities: list[str] = []
    for segment in profitability_by_segment[:3]:
        if float(segment.get("gross_revenue", 0.0) or 0.0) <= 0:
            continue
        if float(segment.get("cancel_rate", 0.0) or 0.0) <= float(targets["order_cancel_rate_max"]):
            opportunities.append(
                (
                    f"Expandir segmento {segment.get('segment', 'unknown')} "
                    f"(receita {segment.get('gross_revenue', 0.0):.2f} e cancelamento {segment.get('cancel_rate', 0.0):.2f}%)."
                )
            )

    if ai_decisions_total > 0 and ai_autonomous_rate >= float(targets["ai_autonomous_rate"]):
        opportunities.append("Escalar autonomia IA em fluxos de baixo risco mantendo auditoria contínua.")

    if total_customers_window > 0 and recurring_customers_rate >= float(targets["recurring_customers_rate"]):
        opportunities.append("Aproveitar base recorrente para estratégias de expansão de ticket e upsell.")

    if not opportunities:
        opportunities.append("Consolidar mais sinais de operação para ampliar oportunidades orientadas por segmento.")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": window_days,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "loops": {
            "acquisition": {
                "total_users": total_users,
                "new_users": new_users,
                "active_offers": active_offers,
                "inbound_messages": inbound_messages,
            },
            "conversion": {
                "checkouts_requested": checkouts_requested,
                "orders_total": total_orders,
                "paid_or_delivered_orders": paid_or_delivered_orders,
                "order_conversion_rate": order_conversion_rate,
                "gross_revenue": round(gross_revenue, 2),
            },
            "retention_expansion": {
                "active_subscriptions": active_subscriptions,
                "new_active_subscriptions": new_active_subscriptions,
                "delivered_orders": delivered_orders,
                "total_customers_window": total_customers_window,
                "recurring_customers": recurring_customers,
                "recurring_customers_rate": recurring_customers_rate,
            },
            "efficiency_risk": {
                "ai_decisions_total": ai_decisions_total,
                "ai_review_rate": ai_review_rate,
                "ai_autonomous_rate": ai_autonomous_rate,
                "review_queue_pending": int(governance_queue.get("pending", 0) or 0),
                "order_cancel_rate": order_cancel_rate,
                "admin_alerts_open": unresolved_admin_alerts,
                "estimated_ai_cost_total": float(cost_monitor.get("totals", {}).get("estimated_total_cost", 0.0) or 0.0),
                "estimated_cost_per_decision": float(cost_monitor.get("totals", {}).get("estimated_avg_cost", 0.0) or 0.0),
                "autonomy_upgrade_candidates": int(autonomy_preview.get("summary", {}).get("upgrade_candidates", 0) or 0),
                "autonomy_downgrade_candidates": int(autonomy_preview.get("summary", {}).get("downgrade_candidates", 0) or 0),
            },
        },
        "targets": targets,
        "goal_gaps": goal_gaps,
        "profitability_by_segment": profitability_by_segment,
        "cost_monitor": cost_monitor,
        "autonomy_policy_preview": autonomy_preview,
        "alerts": alerts,
        "opportunities": opportunities,
        "recommended_actions": list(dict.fromkeys(recommended_actions)) or [
            "Manter rotina semanal de revisão de métricas e governança IA.",
        ],
    }


def _build_ai_weekly_learning_report(
    *,
    db: Session,
    week_iso: str,
    window_start: datetime,
    window_end: datetime,
) -> dict:
    executive = _build_ai_executive_cockpit_payload(
        db=db,
        days=7,
        since=window_start,
        until=window_end,
    )

    cost_monitor = executive.get("cost_monitor")
    if not isinstance(cost_monitor, dict):
        cost_monitor = _build_ai_decision_cost_payload(
            db=db,
            days=7,
            since=window_start,
            until=window_end,
        )

    autonomy_preview = executive.get("autonomy_policy_preview")
    if not isinstance(autonomy_preview, dict):
        autonomy_preview = _build_ai_autonomy_policy_payload(
            db=db,
            days=7,
            since=window_start,
            until=window_end,
        )

    return {
        "week_iso": week_iso,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "highlights": {
            "key_risks": list((executive.get("alerts") or [])[:5]),
            "key_opportunities": list((executive.get("opportunities") or [])[:5]),
            "priority_actions": list((executive.get("recommended_actions") or [])[:5]),
        },
        "executive": executive,
        "cost_monitor": cost_monitor,
        "autonomy_policy_preview": autonomy_preview,
    }


_GROWTH_FUNNEL_ENTRY_EVENTS = {
    "payment_checkout_requested",
    "store_checkout_session_requested",
    "payment_subscription_cta_event",
}
_GROWTH_FUNNEL_SUCCESS_EVENTS = {
    "payment_checkout_created",
    "store_checkout_completed",
}
_GROWTH_FUNNEL_FAILURE_EVENTS = {
    "payment_checkout_failed",
    "message_send_denied",
}
_GROWTH_FUNNEL_TRACKED_EVENTS = (
    _GROWTH_FUNNEL_ENTRY_EVENTS
    | _GROWTH_FUNNEL_SUCCESS_EVENTS
    | _GROWTH_FUNNEL_FAILURE_EVENTS
)


def _growth_segment_key(*, event_type: str, metadata: dict) -> str:
    source = str(
        metadata.get("source")
        or metadata.get("variant")
        or metadata.get("payment_method")
        or "direct"
    ).strip().lower() or "direct"
    plan = str(metadata.get("plan") or metadata.get("plan_id") or "none").strip().lower() or "none"
    billing_cycle = str(metadata.get("billing_cycle") or "na").strip().lower() or "na"
    page = str(metadata.get("page") or event_type).strip().lower() or "unknown"
    return f"{source}|{plan}|{billing_cycle}|{page}"


def _marketing_signal_playbook(signal_type: str) -> dict:
    normalized = str(signal_type or "").strip().lower()
    if normalized == "conversion_drop":
        return {
            "action": "revisar copy e simplificar jornada de checkout",
            "experiment": "ab_checkout_copy",
            "owner_agent": "agente_growth_marketing",
        }
    if normalized == "checkout_friction":
        return {
            "action": "reduzir friccao do checkout e ajustar etapa de pagamento",
            "experiment": "ab_checkout_flow",
            "owner_agent": "agente_growth_marketing",
        }
    if normalized == "high_intent_segment":
        return {
            "action": "escalar investimento e volume de ofertas para segmento quente",
            "experiment": "bandit_budget_allocation",
            "owner_agent": "agente_growth_marketing",
        }
    return {
        "action": "monitorar segmento e coletar mais sinais",
        "experiment": "no_experiment",
        "owner_agent": "orquestrador_central",
    }


def _build_business_os_marketing_funnel_payload(
    *,
    db: Session,
    days: int,
    min_segment_signals: int,
    user_ids: list[int] | None = None,
) -> dict:
    window_start, window_end, window_days = _resolve_window(days=days)

    query = (
        db.query(UserBehaviorLog)
        .filter(
            UserBehaviorLog.event_type.in_(list(_GROWTH_FUNNEL_TRACKED_EVENTS)),
            UserBehaviorLog.created_at >= window_start,
            UserBehaviorLog.created_at < window_end,
        )
    )
    if user_ids:
        query = query.filter(UserBehaviorLog.user_id.in_(list(user_ids)))

    rows = query.order_by(UserBehaviorLog.created_at.desc()).all()

    totals = {
        "events_total": len(rows),
        "entries": 0,
        "success": 0,
        "failure": 0,
    }

    by_segment: dict[str, dict] = {}
    for row in rows:
        event_type = str(row.event_type or "").strip().lower()
        metadata = row.meta_json if isinstance(row.meta_json, dict) else {}
        segment = _growth_segment_key(event_type=event_type, metadata=metadata)

        bucket = by_segment.setdefault(
            segment,
            {
                "segment": segment,
                "entries": 0,
                "success": 0,
                "failure": 0,
                "event_mix": {},
                "latest_event_at": row.created_at.isoformat() if row.created_at else None,
            },
        )
        bucket["event_mix"][event_type] = int(bucket["event_mix"].get(event_type, 0)) + 1

        if event_type in _GROWTH_FUNNEL_ENTRY_EVENTS:
            bucket["entries"] += 1
            totals["entries"] += 1
        elif event_type in _GROWTH_FUNNEL_SUCCESS_EVENTS:
            bucket["success"] += 1
            totals["success"] += 1
        elif event_type in _GROWTH_FUNNEL_FAILURE_EVENTS:
            bucket["failure"] += 1
            totals["failure"] += 1

    segments: list[dict] = []
    signals: list[dict] = []

    for segment_key, bucket in by_segment.items():
        entries = int(bucket.get("entries", 0) or 0)
        success = int(bucket.get("success", 0) or 0)
        failure = int(bucket.get("failure", 0) or 0)
        base = max(1, entries)

        conversion_rate = _pct(success, base)
        failure_rate = _pct(failure, base)

        segment_payload = {
            "segment": segment_key,
            "entries": entries,
            "success": success,
            "failure": failure,
            "conversion_rate": conversion_rate,
            "failure_rate": failure_rate,
            "event_mix": bucket.get("event_mix", {}),
            "latest_event_at": bucket.get("latest_event_at"),
        }
        segments.append(segment_payload)

        if entries < int(min_segment_signals):
            continue

        segment_signals: list[tuple[str, str, str]] = []
        if conversion_rate < 35.0:
            risk = "high" if conversion_rate < 20.0 else "medium"
            segment_signals.append(("conversion_drop", risk, "Conversão abaixo da meta operacional"))
        if failure_rate >= 20.0:
            risk = "high" if failure_rate >= 40.0 else "medium"
            segment_signals.append(("checkout_friction", risk, "Taxa de falha do checkout acima do esperado"))
        if conversion_rate >= 60.0:
            segment_signals.append(("high_intent_segment", "low", "Segmento com alta intenção de compra"))

        for signal_type, risk_level, reason in segment_signals:
            metadata = {
                "signal_type": signal_type,
                "segment": segment_key,
                "reason": reason,
                "entries": entries,
                "success": success,
                "failure": failure,
                "conversion_rate": conversion_rate,
                "failure_rate": failure_rate,
            }
            decision = build_orchestration_decision(
                event_type="growth_signal_detected",
                event_domain="marketing",
                metadata=metadata,
                risk_level=risk_level,
                risk_score=None,
            )
            signals.append(
                {
                    **metadata,
                    "risk_level": risk_level,
                    "decision": decision,
                    "playbook": _marketing_signal_playbook(signal_type),
                }
            )

    segments.sort(
        key=lambda item: (
            int(item.get("entries", 0) or 0),
            float(item.get("conversion_rate", 0.0) or 0.0),
        ),
        reverse=True,
    )
    signals.sort(
        key=lambda item: (
            {"high": 3, "medium": 2, "low": 1}.get(str(item.get("risk_level") or "low"), 0),
            float(item.get("conversion_rate", 0.0) or 0.0),
        ),
        reverse=True,
    )

    experiments = [
        {
            "segment": item.get("segment"),
            "signal_type": item.get("signal_type"),
            "experiment": item.get("playbook", {}).get("experiment"),
            "action": item.get("playbook", {}).get("action"),
            "owner_agent": item.get("playbook", {}).get("owner_agent"),
        }
        for item in signals
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": window_days,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "funnel_totals": totals,
        "segments": segments,
        "signals": signals,
        "experiments": experiments,
        "min_segment_signals": int(min_segment_signals),
    }


def _persist_business_os_marketing_signals(
    *,
    db: Session,
    actor_user_id: int,
    signals: list[dict],
    window_start: str,
    window_end: str,
    request_id: str | None,
    event_source: str,
) -> int:
    telemetry = AITelemetryService(db)
    processed_events = 0

    for signal in signals:
        signal_type = str(signal.get("signal_type") or "growth_signal_detected")
        segment = str(signal.get("segment") or "unknown_segment")
        signal_meta = {
            "signal_type": signal_type,
            "segment": segment,
            "reason": signal.get("reason"),
            "entries": signal.get("entries"),
            "success": signal.get("success"),
            "failure": signal.get("failure"),
            "conversion_rate": signal.get("conversion_rate"),
            "failure_rate": signal.get("failure_rate"),
            "playbook": signal.get("playbook", {}),
        }

        signal_row = telemetry.log_event(
            user_id=actor_user_id,
            event_type="growth_signal_detected",
            entity_type="growth_segment",
            entity_id=segment,
            metadata=signal_meta,
            event_domain="marketing",
            event_source=event_source,
            request_id=request_id,
            idempotency_key=(
                f"growth-signal:{window_start}:{window_end}:{segment}:{signal_type}"
            ),
            commit=False,
        )
        if signal_row is not None:
            processed_events += 1

        orchestration_row = telemetry.log_event(
            user_id=actor_user_id,
            event_type="ai_business_os_orchestrated",
            entity_type="growth_segment",
            entity_id=segment,
            metadata={
                "input": {
                    "event_type": "growth_signal_detected",
                    "event_domain": "marketing",
                    "risk_level": signal.get("risk_level"),
                    "metadata": signal_meta,
                },
                "decision": signal.get("decision", {}),
                "accepted": True,
                "missing_required_fields": [],
            },
            event_domain="business_os",
            event_source=event_source,
            request_id=request_id,
            idempotency_key=(
                f"growth-orchestration:{window_start}:{window_end}:{segment}:{signal_type}"
            ),
            commit=False,
        )
        if orchestration_row is not None:
            processed_events += 1

    return processed_events


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


@router.get("/agenda/market-intelligence")
def get_agenda_market_intelligence(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _load_agenda_profile(db, current_user.id)
    market_ai = MarketIntelligenceAI(db)
    snapshot = market_ai.build_market_snapshot(user_id=current_user.id, profile=profile)
    return snapshot


@router.get("/ops/governance-summary")
def get_ai_governance_summary(
    days: int = Query(30, ge=1, le=365),
    include_recent: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin_user(current_user)
    return _build_ai_governance_summary_payload(
        db=db,
        days=days,
        include_recent=include_recent,
    )


@router.get("/ops/executive-cockpit")
def get_ai_executive_cockpit(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin_user(current_user)
    return _build_ai_executive_cockpit_payload(db=db, days=days)


@router.get("/ops/business-os/blueprint")
def get_ai_business_os_blueprint(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin_user(current_user)

    business_os = build_business_os_blueprint()
    governance = _build_ai_governance_summary_payload(
        db=db,
        days=days,
        include_recent=False,
    )
    cockpit = _build_ai_executive_cockpit_payload(db=db, days=days)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "business_os": business_os,
        "runtime_snapshot": {
            "governance_totals": governance.get("totals", {}),
            "review_queue": governance.get("review_queue", {}),
            "loops": cockpit.get("loops", {}),
            "goal_gaps": cockpit.get("goal_gaps", []),
        },
    }


@router.get("/ops/business-os/readiness")
def get_ai_business_os_readiness(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin_user(current_user)

    governance = _build_ai_governance_summary_payload(
        db=db,
        days=days,
        include_recent=False,
    )
    cockpit = _build_ai_executive_cockpit_payload(db=db, days=days)

    readiness = build_business_os_readiness(
        governance_totals=governance.get("totals", {}),
        loops_snapshot=cockpit.get("loops", {}),
        goal_gaps=cockpit.get("goal_gaps", []),
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "readiness": readiness,
        "implementation_plan": build_business_os_implementation_plan(),
    }


@router.get("/ops/business-os/transformation-roadmap")
def get_ai_business_os_transformation_roadmap(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin_user(current_user)

    governance = _build_ai_governance_summary_payload(
        db=db,
        days=days,
        include_recent=False,
    )
    cockpit = _build_ai_executive_cockpit_payload(db=db, days=days)

    readiness = build_business_os_readiness(
        governance_totals=governance.get("totals", {}),
        loops_snapshot=cockpit.get("loops", {}),
        goal_gaps=cockpit.get("goal_gaps", []),
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "vision": {
            "operating_cycle": [
                "captar_sinais",
                "decidir_com_ia",
                "executar_por_agentes",
                "aprender_em_tempo_real",
            ],
            "loop_model": [
                "aquisicao",
                "conversao",
                "retencao_expansao",
                "eficiencia_risco",
            ],
        },
        "human_roles": [
            "dono_de_agente",
            "arquiteto_de_decisao",
            "gestor_de_risco_algoritmico",
        ],
        "autonomy_policy": {
            "low_risk": "ia_executa_automaticamente",
            "medium_risk": "ia_propoe_humano_aprova",
            "high_risk": "humano_decide_com_recomendacao_ia",
        },
        "kpis_nucleus": [
            "tempo_resposta_e_resolucao",
            "conversao_por_segmento_e_canal",
            "retencao_e_expansao_receita",
            "margem_por_jornada",
            "custo_por_decisao_automatizada",
            "taxa_de_acerto_das_recomendacoes",
            "percentual_de_decisoes_com_intervencao_humana",
        ],
        "readiness": readiness,
        "implementation_plan": build_business_os_implementation_plan(),
        "runtime_snapshot": {
            "alerts": cockpit.get("alerts", []),
            "opportunities": cockpit.get("opportunities", []),
            "recommended_actions": cockpit.get("recommended_actions", []),
            "goal_gaps": cockpit.get("goal_gaps", []),
        },
        "weekly_learning_ritual": {
            "frequency": "weekly",
            "agenda": [
                "revisar_riscos_e_guardrails",
                "avaliar_kpis_por_loop",
                "aprovar_experimentos_da_semana",
                "promover_ou_restringir_autonomia_por_risco",
                "fechar_aprendizados_em_playbooks",
            ],
        },
    }


@router.get("/ops/business-os/marketing-funnel")
def get_ai_business_os_marketing_funnel(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    min_segment_signals: int = Query(3, ge=1, le=20),
    persist: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin_user(current_user)
    if persist:
        _require_platform_write_user(current_user)

    payload = _build_business_os_marketing_funnel_payload(
        db=db,
        days=days,
        min_segment_signals=min_segment_signals,
    )
    payload["persist_performed"] = False
    payload["persisted_events"] = 0

    if persist and payload.get("signals"):
        processed_events = _persist_business_os_marketing_signals(
            db=db,
            actor_user_id=current_user.id,
            signals=list(payload.get("signals") or []),
            window_start=str(payload.get("window_start") or ""),
            window_end=str(payload.get("window_end") or ""),
            request_id=getattr(request.state, "request_id", None),
            event_source="/api/ai/ops/business-os/marketing-funnel",
        )

        db.commit()
        payload["persist_performed"] = True
        payload["persisted_events"] = processed_events

    return payload


@router.post("/ops/business-os/orchestrate-event")
def orchestrate_ai_business_os_event(
    payload: BusinessOSOrchestrateEventIn,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_platform_write_user(current_user)

    decision = build_orchestration_decision(
        event_type=payload.event_type,
        event_domain=payload.event_domain,
        metadata=payload.metadata,
        risk_level=payload.risk_level,
        risk_score=payload.risk_score,
    )

    missing_fields = list(decision.get("contract_validation", {}).get("missing_fields", []))
    accepted = len(missing_fields) == 0

    request_id = getattr(request.state, "request_id", None)
    telemetry = AITelemetryService(db)
    telemetry.log_event(
        user_id=current_user.id,
        event_type="ai_business_os_orchestrated",
        entity_type=payload.entity_type or "business_event",
        entity_id=payload.entity_id or str(payload.event_type),
        metadata={
            "input": {
                "event_type": payload.event_type,
                "event_domain": payload.event_domain,
                "risk_level": payload.risk_level,
                "risk_score": payload.risk_score,
                "metadata": payload.metadata,
            },
            "decision": decision,
            "accepted": accepted,
            "missing_required_fields": missing_fields,
        },
        event_domain="business_os",
        event_source="/api/ai/ops/business-os/orchestrate-event",
        request_id=request_id,
        idempotency_key=(
            f"business-os:{payload.event_type}:{payload.event_domain or 'unknown'}:"
            f"{payload.entity_type or 'business_event'}:{payload.entity_id or 'none'}"
        ),
        commit=True,
    )

    return {
        "accepted": accepted,
        "missing_required_fields": missing_fields,
        "requires_human_gate": bool(decision.get("autonomy_policy", {}).get("human_gate")),
        "decision": decision,
    }


@router.post("/ops/business-os/signal-pipeline")
def run_ai_business_os_signal_pipeline(
    payload: BusinessOSSignalPipelineIn,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Processa sinais em lote para o Business OS com governança e trilha auditável."""
    _require_platform_write_user(current_user)

    request_id = getattr(request.state, "request_id", None)
    telemetry = AITelemetryService(db)

    source = str(payload.source or "business_os_pipeline").strip() or "business_os_pipeline"
    persist_only_accepted = bool(payload.persist_only_accepted)

    processed: list[dict] = []
    persisted_events = 0

    by_risk = {"low": 0, "medium": 0, "high": 0}
    by_policy: dict[str, int] = {}
    by_agent: dict[str, int] = {}

    for index, event in enumerate(payload.events):
        decision = build_orchestration_decision(
            event_type=event.event_type,
            event_domain=event.event_domain,
            metadata=event.metadata,
            risk_level=event.risk_level,
            risk_score=event.risk_score,
        )

        missing_fields = list(decision.get("contract_validation", {}).get("missing_fields", []))
        accepted = len(missing_fields) == 0

        risk_level = str(decision.get("risk_level") or "medium").strip().lower()
        if risk_level in by_risk:
            by_risk[risk_level] += 1

        autonomy_policy = str((decision.get("autonomy_policy") or {}).get("policy") or "unknown")
        by_policy[autonomy_policy] = int(by_policy.get(autonomy_policy, 0)) + 1

        selected_agent = str(decision.get("selected_agent") or "orquestrador_central")
        by_agent[selected_agent] = int(by_agent.get(selected_agent, 0)) + 1

        persisted = False
        if (not persist_only_accepted) or accepted:
            signal_row = telemetry.log_event(
                user_id=current_user.id,
                event_type=event.event_type,
                entity_type=event.entity_type or "business_event",
                entity_id=event.entity_id or f"{source}:{index}",
                metadata={
                    "signal": {
                        "event_type": event.event_type,
                        "event_domain": event.event_domain,
                        "risk_level": event.risk_level,
                        "risk_score": event.risk_score,
                        "metadata": event.metadata,
                    },
                    "pipeline": {
                        "source": source,
                        "batch_index": index,
                    },
                },
                event_domain=event.event_domain or "business_os",
                event_source=f"/api/ai/ops/business-os/signal-pipeline:{source}",
                request_id=request_id,
                idempotency_key=(
                    f"business-os-signal:{source}:{index}:{event.event_type}:"
                    f"{event.entity_type or 'business_event'}:{event.entity_id or 'none'}"
                ),
                commit=False,
            )

            orchestration_row = telemetry.log_event(
                user_id=current_user.id,
                event_type="ai_business_os_orchestrated",
                entity_type=event.entity_type or "business_event",
                entity_id=event.entity_id or f"{source}:{index}",
                metadata={
                    "input": {
                        "event_type": event.event_type,
                        "event_domain": event.event_domain,
                        "risk_level": event.risk_level,
                        "risk_score": event.risk_score,
                        "metadata": event.metadata,
                    },
                    "decision": decision,
                    "accepted": accepted,
                    "missing_required_fields": missing_fields,
                    "pipeline": {
                        "source": source,
                        "batch_index": index,
                    },
                },
                event_domain="business_os",
                event_source=f"/api/ai/ops/business-os/signal-pipeline:{source}",
                request_id=request_id,
                idempotency_key=(
                    f"business-os-orchestration:{source}:{index}:{event.event_type}:"
                    f"{event.entity_type or 'business_event'}:{event.entity_id or 'none'}"
                ),
                commit=False,
            )

            persisted = bool(signal_row is not None and orchestration_row is not None)
            if persisted:
                persisted_events += 2

        processed.append(
            {
                "index": index,
                "event_type": event.event_type,
                "event_domain": decision.get("event_domain"),
                "selected_agent": selected_agent,
                "risk_level": risk_level,
                "autonomy_policy": autonomy_policy,
                "accepted": accepted,
                "missing_required_fields": missing_fields,
                "persisted": persisted,
                "requires_human_gate": bool((decision.get("autonomy_policy") or {}).get("human_gate")),
                "recommended_next_step": decision.get("recommended_next_step"),
            }
        )

    db.commit()

    accepted_total = sum(1 for item in processed if bool(item.get("accepted")))
    rejected_total = max(0, len(processed) - accepted_total)
    human_gate_total = sum(1 for item in processed if bool(item.get("requires_human_gate")))

    priority_recommendations: list[str] = []
    if rejected_total > 0:
        priority_recommendations.append("Corrigir contratos de evento com campos obrigatórios ausentes antes da execução automática.")
    if human_gate_total > 0:
        priority_recommendations.append("Priorizar fila de aprovação humana para eventos de médio/alto risco.")
    if by_risk.get("high", 0) > 0:
        priority_recommendations.append("Aplicar reforço de guardrails e trilha de auditoria para sinais de risco alto.")
    if not priority_recommendations:
        priority_recommendations.append("Pipeline íntegro: ampliar volume de sinais e aumentar cobertura por domínio.")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "persist_only_accepted": persist_only_accepted,
        "summary": {
            "events_total": len(processed),
            "accepted": accepted_total,
            "rejected": rejected_total,
            "requires_human_gate": human_gate_total,
            "persisted_rows": persisted_events,
            "by_risk": by_risk,
            "by_policy": by_policy,
            "by_agent": by_agent,
        },
        "priority_recommendations": priority_recommendations,
        "events": processed,
    }


@router.get("/ops/decision-cost-monitor")
def get_ai_decision_cost_monitor(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin_user(current_user)
    return _build_ai_decision_cost_payload(db=db, days=days)


@router.get("/ops/autonomy-policy")
def get_ai_autonomy_policy(
    days: int = Query(30, ge=1, le=365),
    apply: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin_user(current_user)
    if apply:
        _require_platform_write_user(current_user)

    payload = _build_ai_autonomy_policy_payload(db=db, days=days)
    payload["apply_performed"] = False

    if apply:
        levels_applied = payload.get("levels_proposed", {}) if isinstance(payload.get("levels_proposed"), dict) else {}
        db.add(
            UserBehaviorLog(
                user_id=current_user.id,
                event_type="ai_autonomy_policy_applied",
                entity_type="ai_autonomy_policy",
                entity_id="global",
                meta_json={
                    "generated_at": payload.get("generated_at"),
                    "window_days": payload.get("window_days"),
                    "window_start": payload.get("window_start"),
                    "window_end": payload.get("window_end"),
                    "levels_applied": levels_applied,
                    "summary": payload.get("summary", {}),
                    "agents": payload.get("agents", []),
                    "rules": payload.get("rules", {}),
                },
            )
        )
        db.commit()
        payload["apply_performed"] = True
        payload["levels_applied"] = levels_applied

    return payload


@router.get("/ops/weekly-learning-report")
def get_ai_weekly_learning_report(
    week_offset: int = Query(0, ge=0, le=26),
    regenerate: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin_user(current_user)
    if regenerate:
        _require_platform_write_user(current_user)

    week_iso, window_start, window_end = _week_window_bounds(week_offset)

    if not regenerate:
        cached = (
            db.query(UserBehaviorLog)
            .filter(
                UserBehaviorLog.event_type == "ai_weekly_learning_report_generated",
                UserBehaviorLog.entity_type == "ai_weekly_report",
                UserBehaviorLog.entity_id == week_iso,
            )
            .order_by(UserBehaviorLog.created_at.desc())
            .first()
        )
        if cached and isinstance(cached.meta_json, dict):
            return {
                "from_cache": True,
                "week_iso": week_iso,
                "report": cached.meta_json,
            }

    report = _build_ai_weekly_learning_report(
        db=db,
        week_iso=week_iso,
        window_start=window_start,
        window_end=window_end,
    )

    db.add(
        UserBehaviorLog(
            user_id=current_user.id,
            event_type="ai_weekly_learning_report_generated",
            entity_type="ai_weekly_report",
            entity_id=week_iso,
            meta_json=report,
        )
    )
    db.commit()

    return {
        "from_cache": False,
        "week_iso": week_iso,
        "report": report,
    }


@router.get("/ops/governance-summary.csv")
def export_ai_governance_summary_csv(
    days: int = Query(30, ge=1, le=365),
    include_recent: bool = Query(True),
    granularity: str = Query(default="flat", pattern="^(flat|week)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin_user(current_user)

    if granularity == "week":
        csv_payload = _build_governance_summary_weekly_csv(db=db, days=days)
    else:
        summary_payload = _build_ai_governance_summary_payload(
            db=db,
            days=days,
            include_recent=include_recent,
        )
        csv_payload = _build_governance_summary_csv(summary_payload)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    if granularity == "week":
        filename = f"ai_governance_summary_weekly_{timestamp}_{days}d.csv"
    else:
        filename = f"ai_governance_summary_{timestamp}_{days}d.csv"

    return Response(
        content="\ufeff" + csv_payload,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/ops/review-queue")
def get_ai_review_queue(
    status_filter: str = Query(default="pending_review", pattern="^(pending_review|approved|rejected|all)$"),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin_user(current_user)

    service = AIDecisionReviewService(db)
    rows = service.list_queue(status=status_filter, limit=limit)
    return {
        "status_filter": status_filter,
        "total": len(rows),
        "items": [service.to_payload(row) for row in rows],
    }


@router.post("/ops/review-queue/{review_id}/resolve")
def resolve_ai_review_queue_item(
    review_id: int,
    payload: GovernanceReviewResolveIn,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_platform_write_user(current_user)

    request_id = getattr(request.state, "request_id", None)
    service = AIDecisionReviewService(db)
    telemetry = AITelemetryService(db)

    try:
        row = service.resolve_review(
            review_id=review_id,
            decision=payload.decision,
            reviewer=current_user,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    telemetry.log_event(
        user_id=current_user.id,
        event_type="ai_review_queue_resolved",
        entity_type="ai_review_queue",
        entity_id=str(review_id),
        metadata={
            "decision": payload.decision,
            "notes": payload.notes,
            "resolved_status": row.status,
        },
        event_domain="governance_review",
        event_source="/api/ai/ops/review-queue/resolve",
        request_id=request_id,
        idempotency_key=f"review-resolve:{review_id}:{payload.decision}",
        commit=False,
    )

    db.commit()
    return {
        "ok": True,
        "item": service.to_payload(row),
    }


@router.get("/agenda/autonomous-commerce")
def get_agenda_autonomous_commerce(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _load_agenda_profile(db, current_user.id)
    capabilities = _require_account_ai_operator(db=db, user=current_user, minimum_plan="pro")

    market_ai = MarketIntelligenceAI(db)
    market_snapshot = market_ai.build_market_snapshot(user_id=current_user.id, profile=profile)
    autonomous_ai = AutonomousCommerceAI(db)
    plan = autonomous_ai.build_autonomous_plan(
        user_id=current_user.id,
        profile=profile,
        market_snapshot=market_snapshot,
    )

    if not bool(capabilities.get("allow_auto_negotiation")):
        plan["recommended_deals"] = []
    if not bool(capabilities.get("allow_auto_flash_auction")):
        plan["flash_auction_candidates"] = []

    plan["subscription_capabilities"] = {
        "plan": capabilities.get("plan"),
        "allowed_autonomy_modes": list(capabilities.get("allowed_autonomy_modes") or ["assistida"]),
        "max_auto_execute_per_day": int(capabilities.get("max_auto_execute_per_day", 0) or 0),
        "allow_auto_negotiation": bool(capabilities.get("allow_auto_negotiation")),
        "allow_auto_flash_auction": bool(capabilities.get("allow_auto_flash_auction")),
    }
    return plan


@router.post("/agenda/autonomous-commerce/execute")
def execute_agenda_autonomous_commerce(
    payload: AgendaAutonomousExecuteIn,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agenda_profile = _load_agenda_profile(db, current_user.id)
    capabilities = _require_account_ai_operator(db=db, user=current_user, minimum_plan="pro")
    allowed_modes = set(capabilities.get("allowed_autonomy_modes") or ["assistida"])

    current_mode = str(agenda_profile.get("autonomy_mode") or "assistida").strip().lower()
    if current_mode not in allowed_modes:
        raise HTTPException(
            status_code=403,
            detail="Modo de autonomia atual não permitido para o plano de assinatura.",
        )

    if payload.action_type == "auto_negotiation" and not bool(capabilities.get("allow_auto_negotiation")):
        raise HTTPException(
            status_code=403,
            detail="Auto negociação indisponível para o plano atual.",
        )

    if payload.action_type == "flash_auction" and not bool(capabilities.get("allow_auto_flash_auction")):
        raise HTTPException(
            status_code=403,
            detail="Leilão relâmpago indisponível para o plano atual.",
        )

    requested_mode = str(payload.mode or "commit").strip().lower()
    if requested_mode == "commit":
        max_auto_exec_per_day = int(capabilities.get("max_auto_execute_per_day", 0) or 0)
        if max_auto_exec_per_day <= 0:
            raise HTTPException(
                status_code=403,
                detail="Seu plano não permite execução autônoma em modo commit.",
            )

        today_auto_exec = _count_today_ai_decisions(db, int(current_user.id))
        if today_auto_exec >= max_auto_exec_per_day:
            raise HTTPException(
                status_code=429,
                detail="Limite diário de execuções autônomas atingido para o plano atual.",
            )

    governance = AIGovernanceService()
    review_queue_service = AIDecisionReviewService(db)
    telemetry = AITelemetryService(db)
    request_id = getattr(request.state, "request_id", None)

    precheck = governance.precheck_action(
        profile=agenda_profile,
        action_type=payload.action_type,
        mode=payload.mode,
    )
    if not bool(precheck.get("allowed")):
        telemetry.log_event(
            user_id=current_user.id,
            event_type="ai_autonomous_precheck_denied",
            entity_type="autonomous_commerce",
            entity_id=str(payload.offer_id),
            metadata={
                "action_type": payload.action_type,
                "mode": payload.mode,
                "reason": precheck.get("reason"),
            },
            event_domain="autonomous_commerce",
            event_source="/api/ai/agenda/autonomous-commerce/execute",
            request_id=request_id,
            idempotency_key=f"precheck:{payload.action_type}:{payload.mode}:{payload.offer_id}",
            commit=True,
        )
        raise HTTPException(status_code=403, detail=str(precheck.get("reason") or "Execucao bloqueada pelas politicas de governanca."))

    if str(payload.mode or "commit").strip().lower() == "commit":
        if current_user.role != "admin" and not bool(current_user.is_superuser):
            profile_service = ProfileService(db)
            domain_profile = profile_service.get_or_create_profile(current_user)
            can_publish, reason = profile_service.can_publish_offer(domain_profile)
            if not can_publish:
                telemetry.log_event(
                    user_id=current_user.id,
                    event_type="ai_autonomous_permission_denied",
                    entity_type="autonomous_commerce",
                    entity_id=str(payload.offer_id),
                    metadata={
                        "action_type": payload.action_type,
                        "mode": payload.mode,
                        "reason": reason,
                    },
                    event_domain="autonomous_commerce",
                    event_source="/api/ai/agenda/autonomous-commerce/execute",
                    request_id=request_id,
                    idempotency_key=f"permission:{payload.action_type}:{payload.mode}:{payload.offer_id}",
                    commit=True,
                )
                raise HTTPException(status_code=403, detail=reason or "Perfil nao autorizado para executar automacao comercial.")

    market_ai = MarketIntelligenceAI(db)
    market_snapshot = market_ai.build_market_snapshot(user_id=current_user.id, profile=agenda_profile)
    autonomous_ai = AutonomousCommerceAI(db)

    result = autonomous_ai.execute_transactional_action(
        user_id=current_user.id,
        profile=agenda_profile,
        market_snapshot=market_snapshot,
        action_type=payload.action_type,
        offer_id=payload.offer_id,
        mode=payload.mode,
        buyer_user_id=payload.buyer_user_id,
    )

    decision = governance.evaluate_transaction_result(
        profile=agenda_profile,
        action_type=payload.action_type,
        mode=payload.mode,
        result=result,
    )

    telemetry.log_decision(
        user_id=current_user.id,
        action_type=str(payload.action_type),
        entity_type="autonomous_commerce",
        entity_id=str(payload.offer_id),
        decision_payload=decision,
        metadata={
            "result": {
                "committed": bool(result.get("committed")),
                "event_id": result.get("event_id"),
                "already_executed": bool(result.get("already_executed")),
                "rolled_back": bool(result.get("rolled_back")),
            },
            "requested_mode": payload.mode,
            "action_type": payload.action_type,
            "buyer_user_id": payload.buyer_user_id,
            "subscription_plan": capabilities.get("plan"),
            "governance_snapshot": result.get("governance_snapshot", {}),
        },
        request_id=request_id,
        idempotency_key=(
            f"decision:{payload.action_type}:{payload.mode}:{payload.offer_id}:"
            f"{result.get('event_id') or 'none'}:{int(bool(result.get('committed')))}"
        ),
        commit=False,
    )

    review_item_payload: dict | None = None
    if bool(decision.get("requires_human_review")):
        review_row, created = review_queue_service.enqueue_review(
            user_id=current_user.id,
            action_type=str(payload.action_type),
            entity_id=str(payload.offer_id),
            decision=decision,
            context={
                "result": {
                    "committed": bool(result.get("committed")),
                    "event_id": result.get("event_id"),
                    "message": result.get("message"),
                },
                "buyer_user_id": payload.buyer_user_id,
                "mode": payload.mode,
            },
        )
        review_item_payload = {
            "created": bool(created),
            "item": review_queue_service.to_payload(review_row),
        }

    if not bool(result.get("committed")):
        db.commit()
        raise HTTPException(status_code=409, detail=str(result.get("message") or "Falha na execução transacional."))

    db.commit()
    response = dict(result)
    response["governance"] = decision
    response["review_queue"] = review_item_payload
    return response


@router.get("/agenda/profile")
def get_agenda_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_account_roles(
        current_user,
        allowed_roles={
            ACCOUNT_ROLE_OWNER,
            ACCOUNT_ROLE_MANAGER,
            ACCOUNT_ROLE_ANALYST,
            ACCOUNT_ROLE_VIEWER,
        },
        detail="Acesso restrito a membros da conta",
    )

    profile = _load_agenda_profile(db, current_user.id)
    capabilities = _resolve_user_ai_capabilities(db, current_user)
    return {
        "profile": profile,
        "subscription_capabilities": {
            "plan": capabilities.get("plan"),
            "allowed_autonomy_modes": list(capabilities.get("allowed_autonomy_modes") or ["assistida"]),
            "max_auto_execute_per_day": int(capabilities.get("max_auto_execute_per_day", 0) or 0),
            "allow_auto_negotiation": bool(capabilities.get("allow_auto_negotiation")),
            "allow_auto_flash_auction": bool(capabilities.get("allow_auto_flash_auction")),
        },
    }


@router.post("/agenda/profile")
def save_agenda_profile(
    payload: AgendaProfileIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_account_roles(
        current_user,
        allowed_roles={
            ACCOUNT_ROLE_OWNER,
            ACCOUNT_ROLE_MANAGER,
        },
        detail="Acesso restrito para alteração de perfil de autonomia da conta",
    )

    profile = payload.model_dump()
    capabilities = _resolve_user_ai_capabilities(db, current_user)
    allowed_modes = set(capabilities.get("allowed_autonomy_modes") or ["assistida"])

    if profile.get("autonomy_mode") not in allowed_modes:
        raise HTTPException(
            status_code=403,
            detail="Modo de autonomia não permitido para o plano atual.",
        )

    max_auto_exec = int(capabilities.get("max_auto_execute_per_day", 0) or 0)
    if int(profile.get("auto_execute_limit_per_day", 0) or 0) > max_auto_exec:
        raise HTTPException(
            status_code=403,
            detail=f"auto_execute_limit_per_day excede o limite do plano ({max_auto_exec}/dia).",
        )

    if bool(profile.get("auto_negotiation_enabled")) and not bool(capabilities.get("allow_auto_negotiation")):
        raise HTTPException(
            status_code=403,
            detail="Auto negociação não disponível para o plano atual.",
        )

    if bool(profile.get("auto_flash_auction_enabled")) and not bool(capabilities.get("allow_auto_flash_auction")):
        raise HTTPException(
            status_code=403,
            detail="Leilão relâmpago não disponível para o plano atual.",
        )

    profile["onboarding_complete"] = True
    profile["plan_capabilities"] = {
        "plan": capabilities.get("plan"),
        "max_auto_execute_per_day": max_auto_exec,
        "allowed_autonomy_modes": list(allowed_modes),
    }

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
    market_ai = MarketIntelligenceAI(db)
    market_snapshot = market_ai.build_market_snapshot(user_id=current_user.id, profile=profile)
    autonomous_ai = AutonomousCommerceAI(db)
    autonomous_plan = autonomous_ai.build_autonomous_plan(
        user_id=current_user.id,
        profile=profile,
        market_snapshot=market_snapshot,
    )

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

    market_actions = market_snapshot.get("recommended_actions", []) if isinstance(market_snapshot, dict) else []
    for item in market_actions:
        if isinstance(item, dict):
            actions.append(item)

    autonomous_actions = autonomous_plan.get("recommended_actions", []) if isinstance(autonomous_plan, dict) else []
    for item in autonomous_actions:
        if isinstance(item, dict):
            actions.append(item)

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

    market_automation = market_ai.materialize_guardrail_automations(
        user_id=current_user.id,
        profile=profile,
        market_snapshot=market_snapshot,
    )

    autonomous_automation = autonomous_ai.materialize_guardrail_automations(
        user_id=current_user.id,
        profile=profile,
        autonomous_plan=autonomous_plan,
    )

    market_notifications_created = 0
    for item in market_automation.get("automations", []):
        offer_id = str(item.get("offer_id") or "")
        if not offer_id:
            continue
        if _create_notification_once(
            db,
            user_id=current_user.id,
            title="Agenda IA: execução autônoma preparada",
            message=(
                f"{item.get('title', 'Ação de mercado criada')} "
                f"com score {float(item.get('score', 0.0)):.1f}/100."
            ),
            resource_key=f"market_auto:{offer_id}",
        ):
            market_notifications_created += 1

    autonomous_notifications_created = 0
    for item in autonomous_automation.get("automations", []):
        offer_id = str(item.get("offer_id") or "")
        automation_type = str(item.get("type") or "automation")
        if not offer_id:
            continue

        if _create_notification_once(
            db,
            user_id=current_user.id,
            title="Agenda IA: automação comercial criada",
            message=(
                f"Execução {automation_type} preparada para oferta {offer_id}. "
                "Revise os detalhes e confirme no painel da agenda."
            ),
            resource_key=f"autonomous_auto:{automation_type}:{offer_id}",
        ):
            autonomous_notifications_created += 1

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

    if (
        proactive_created
        or predictive_created
        or market_notifications_created
        or autonomous_notifications_created
        or int(market_automation.get("events_created", 0))
        or int(autonomous_automation.get("events_created", 0))
    ):
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
        "market_intelligence": market_snapshot,
        "autonomous_commerce": autonomous_plan,
        "decision_mode": profile.get("autonomy_mode", "assistida"),
        "decision_weights": weights,
        "actions": scored_actions,
        "proactive_alerts_created": proactive_created,
        "predictive_alerts_created": predictive_created,
        "market_automation_events_created": int(market_automation.get("events_created", 0)),
        "market_automation_notifications_created": market_notifications_created,
        "market_automations": market_automation.get("automations", []),
        "autonomous_automation_events_created": int(autonomous_automation.get("events_created", 0)),
        "autonomous_automation_notifications_created": autonomous_notifications_created,
        "autonomous_automations": autonomous_automation.get("automations", []),
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
            "autonomous_actions": len(autonomous_actions),
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
