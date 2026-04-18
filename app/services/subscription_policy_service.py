from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.domain_enums import SubscriptionStatus
from app.models.subscription import Subscription


_PLAN_RANK = {
    "none": 0,
    "basic": 1,
    "pro": 2,
    "premium": 3,
    "enterprise": 4,
}

_PLAN_CAPABILITIES: dict[str, dict[str, Any]] = {
    "none": {
        "allowed_autonomy_modes": ["assistida"],
        "max_auto_execute_per_day": 0,
        "allow_auto_negotiation": False,
        "allow_auto_flash_auction": False,
        "allow_business_os_marketing_loop": False,
        "allow_business_os_persist": False,
    },
    "basic": {
        "allowed_autonomy_modes": ["assistida"],
        "max_auto_execute_per_day": 0,
        "allow_auto_negotiation": False,
        "allow_auto_flash_auction": False,
        "allow_business_os_marketing_loop": False,
        "allow_business_os_persist": False,
    },
    "pro": {
        "allowed_autonomy_modes": ["assistida", "semi_autonoma"],
        "max_auto_execute_per_day": 2,
        "allow_auto_negotiation": True,
        "allow_auto_flash_auction": False,
        "allow_business_os_marketing_loop": True,
        "allow_business_os_persist": False,
    },
    "premium": {
        "allowed_autonomy_modes": ["assistida", "semi_autonoma", "autonoma"],
        "max_auto_execute_per_day": 6,
        "allow_auto_negotiation": True,
        "allow_auto_flash_auction": True,
        "allow_business_os_marketing_loop": True,
        "allow_business_os_persist": True,
    },
    "enterprise": {
        "allowed_autonomy_modes": ["assistida", "semi_autonoma", "autonoma"],
        "max_auto_execute_per_day": 20,
        "allow_auto_negotiation": True,
        "allow_auto_flash_auction": True,
        "allow_business_os_marketing_loop": True,
        "allow_business_os_persist": True,
    },
}


def normalize_plan(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _PLAN_RANK:
        return normalized
    return "none"


def capabilities_for_plan(plan: str | None) -> dict[str, Any]:
    normalized = normalize_plan(plan)
    payload = dict(_PLAN_CAPABILITIES.get(normalized, _PLAN_CAPABILITIES["none"]))
    payload["plan"] = normalized
    payload["rank"] = int(_PLAN_RANK.get(normalized, 0))
    return payload


def is_plan_at_least(plan: str | None, minimum_plan: str) -> bool:
    normalized_plan = normalize_plan(plan)
    normalized_min = normalize_plan(minimum_plan)
    return int(_PLAN_RANK.get(normalized_plan, 0)) >= int(_PLAN_RANK.get(normalized_min, 0))


def get_latest_subscription(db: Session, user_id: int) -> Subscription | None:
    return (
        db.query(Subscription)
        .filter(Subscription.user_id == int(user_id))
        .order_by(Subscription.created_at.desc())
        .first()
    )


def resolve_user_plan(db: Session, user_id: int) -> str:
    row = get_latest_subscription(db, user_id)
    if row is None:
        return "none"

    status = str(row.status or "").strip().lower()
    if status not in {
        SubscriptionStatus.ACTIVE.value,
        "active",
    }:
        return "none"

    end_date = row.end_date
    if end_date is not None:
        now = datetime.now(timezone.utc)
        end_safe = end_date if end_date.tzinfo is not None else end_date.replace(tzinfo=timezone.utc)
        if end_safe < now:
            return "none"

    return normalize_plan(str(row.plan_type or "none"))


def capabilities_for_user(db: Session, user_id: int) -> dict[str, Any]:
    plan = resolve_user_plan(db, user_id)
    return capabilities_for_plan(plan)


def require_minimum_plan(
    *,
    db: Session,
    user_id: int,
    minimum_plan: str,
    detail: str | None = None,
) -> dict[str, Any]:
    capabilities = capabilities_for_user(db, user_id)
    plan = str(capabilities.get("plan") or "none")

    if is_plan_at_least(plan, minimum_plan):
        return capabilities

    normalized_min = normalize_plan(minimum_plan)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail or f"Recurso disponível apenas para plano {normalized_min} ou superior.",
    )
