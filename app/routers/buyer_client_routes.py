from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.core.config import settings
from app.database.connection import get_db
from app.models.buyer_client import BuyerClient, BuyerClientPolicy, BuyerClientSlotPurchase
from app.models.user import User
from app.services.payment_service import create_client_slots_checkout_session
from app.services.notification_service import create_notification

router = APIRouter(prefix="/buyer-clients", tags=["buyer-clients"])


class BuyerClientCreateIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    company_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=50)
    management_scope: str = Field(default="joint", pattern="^(buyer|wallfruits|joint)$")
    demand_summary: str | None = None
    notes: str | None = None


class BuyerClientUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    company_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=50)
    management_scope: str | None = Field(default=None, pattern="^(buyer|wallfruits|joint)$")
    demand_summary: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class BuySlotsIn(BaseModel):
    quantity: int = Field(..., ge=1, le=20)
    success_url: str | None = None
    cancel_url: str | None = None


class AdminPolicyUpdateIn(BaseModel):
    compliance_status: str = Field(..., pattern="^(ok|warning|violation)$")
    purchase_restricted: bool
    restriction_reason: str | None = Field(default=None, max_length=500)


def _ensure_policy(db: Session, user_id: int) -> BuyerClientPolicy:
    policy = db.query(BuyerClientPolicy).filter(BuyerClientPolicy.user_id == user_id).first()
    if policy:
        return policy

    policy = BuyerClientPolicy(user_id=user_id)
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def _is_admin(user: User) -> bool:
    return user.role == "admin" or bool(user.is_superuser)


def _policy_summary(policy: BuyerClientPolicy) -> dict:
    prepaid_available = max(0, int(policy.slots_purchased or 0) - int(policy.slots_used or 0))
    remaining_cap = max(0, int(policy.max_clients or 0) - int(policy.slots_used or 0))
    return {
        "max_clients": int(policy.max_clients or 0),
        "slot_price": float(policy.slot_price or 0),
        "slots_purchased": int(policy.slots_purchased or 0),
        "slots_used": int(policy.slots_used or 0),
        "prepaid_available": prepaid_available,
        "remaining_cap": remaining_cap,
        "compliance_status": policy.compliance_status,
        "purchase_restricted": bool(policy.purchase_restricted),
        "restriction_reason": policy.restriction_reason,
        "restricted_at": policy.restricted_at.isoformat() if policy.restricted_at else None,
    }


def _client_payload(item: BuyerClient) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "company_name": item.company_name,
        "email": item.email,
        "phone": item.phone,
        "city": item.city,
        "state": item.state,
        "management_scope": item.management_scope,
        "demand_summary": item.demand_summary,
        "notes": item.notes,
        "is_active": bool(item.is_active),
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _slot_purchase_payload(item: BuyerClientSlotPurchase) -> dict:
    return {
        "id": item.id,
        "quantity": int(item.quantity or 0),
        "unit_price": float(item.unit_price or 0),
        "total_amount": float(item.total_amount or 0),
        "status": item.status,
        "checkout_session_id": item.checkout_session_id,
        "paid_at": item.paid_at.isoformat() if item.paid_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("/dashboard")
def buyer_clients_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    policy = _ensure_policy(db, current_user.id)
    clients = (
        db.query(BuyerClient)
        .filter(BuyerClient.owner_user_id == current_user.id)
        .order_by(BuyerClient.created_at.desc(), BuyerClient.id.desc())
        .all()
    )
    purchases = (
        db.query(BuyerClientSlotPurchase)
        .filter(BuyerClientSlotPurchase.user_id == current_user.id)
        .order_by(BuyerClientSlotPurchase.created_at.desc(), BuyerClientSlotPurchase.id.desc())
        .limit(10)
        .all()
    )
    return {
        "policy": _policy_summary(policy),
        "clients": [_client_payload(item) for item in clients],
        "slot_purchases": [_slot_purchase_payload(item) for item in purchases],
        "total": len(clients),
    }


@router.post("/slots/purchase")
def purchase_client_slots(
    payload: BuySlotsIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    policy = _ensure_policy(db, current_user.id)

    if policy.purchase_restricted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito por compliance. Regularize para comprar novos slots.",
        )

    next_total_slots = int(policy.slots_purchased or 0) + int(payload.quantity)
    if next_total_slots > int(policy.max_clients or 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Limite maximo de {policy.max_clients} clientes atingido para este plano.",
        )

    success_url = payload.success_url or f"{settings.FRONTEND_URL}/clients/manage"
    cancel_url = payload.cancel_url or f"{settings.FRONTEND_URL}/clients/manage"

    total_amount = (Decimal(policy.slot_price or 0) * Decimal(payload.quantity)).quantize(Decimal("0.01"))

    purchase = BuyerClientSlotPurchase(
        user_id=current_user.id,
        quantity=int(payload.quantity),
        unit_price=Decimal(policy.slot_price or 0),
        total_amount=total_amount,
        status="pending",
    )
    db.add(purchase)
    db.flush()

    try:
        checkout = create_client_slots_checkout_session(
            user=current_user,
            quantity=payload.quantity,
            unit_price_brl=Decimal(policy.slot_price or 0),
            success_url=success_url,
            cancel_url=cancel_url,
            extra_metadata={"purchase_id": str(purchase.id)},
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    purchase.checkout_session_id = checkout["session_id"]
    db.commit()

    return {
        "ok": True,
        "mode": "checkout",
        "purchase_id": purchase.id,
        "quantity": payload.quantity,
        "amount_brl": float(total_amount),
        "checkout_url": checkout["checkout_url"],
        "session_id": checkout["session_id"],
        "message": "Checkout criado. O slot será liberado após confirmação do pagamento.",
    }


@router.post("")
def create_buyer_client(
    payload: BuyerClientCreateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    policy = _ensure_policy(db, current_user.id)

    if policy.purchase_restricted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito por compliance. Voce nao pode cadastrar novos clientes.",
        )

    slots_used = int(policy.slots_used or 0)
    max_clients = int(policy.max_clients or 0)
    prepaid_available = int(policy.slots_purchased or 0) - slots_used

    if slots_used >= max_clients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Limite contratual atingido: maximo de {max_clients} clientes cadastrados.",
        )

    if prepaid_available <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Sem slots pre-pagos. Compre slots de cliente para adicionar novos registros.",
        )

    item = BuyerClient(
        owner_user_id=current_user.id,
        name=payload.name.strip(),
        company_name=(payload.company_name or "").strip() or None,
        email=(payload.email or "").strip() or None,
        phone=(payload.phone or "").strip() or None,
        city=(payload.city or "").strip() or None,
        state=(payload.state or "").strip() or None,
        management_scope=payload.management_scope,
        demand_summary=payload.demand_summary,
        notes=payload.notes,
        is_active=True,
    )
    db.add(item)

    policy.slots_used = slots_used + 1
    db.commit()
    db.refresh(item)
    db.refresh(policy)

    return {
        "ok": True,
        "client": _client_payload(item),
        "policy": _policy_summary(policy),
    }


@router.patch("/{client_id}")
def update_buyer_client(
    client_id: int,
    payload: BuyerClientUpdateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(BuyerClient)
        .filter(BuyerClient.id == client_id, BuyerClient.owner_user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")

    if payload.name is not None:
        item.name = payload.name.strip()
    if payload.company_name is not None:
        item.company_name = (payload.company_name or "").strip() or None
    if payload.email is not None:
        item.email = (payload.email or "").strip() or None
    if payload.phone is not None:
        item.phone = (payload.phone or "").strip() or None
    if payload.city is not None:
        item.city = (payload.city or "").strip() or None
    if payload.state is not None:
        item.state = (payload.state or "").strip() or None
    if payload.management_scope is not None:
        item.management_scope = payload.management_scope
    if payload.demand_summary is not None:
        item.demand_summary = payload.demand_summary
    if payload.notes is not None:
        item.notes = payload.notes
    if payload.is_active is not None:
        item.is_active = bool(payload.is_active)

    db.commit()
    db.refresh(item)
    return {"ok": True, "client": _client_payload(item)}


@router.delete("/{client_id}")
def remove_buyer_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(BuyerClient)
        .filter(BuyerClient.id == client_id, BuyerClient.owner_user_id == current_user.id)
        .first()
    )
    if not item:
        return {"ok": True, "deleted": False}

    db.delete(item)
    db.commit()
    return {"ok": True, "deleted": True}


@router.patch("/admin/policy/{user_id}")
def admin_update_buyer_client_policy(
    user_id: int,
    payload: AdminPolicyUpdateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Somente admin pode ajustar compliance de clientes")

    policy = _ensure_policy(db, user_id)
    policy.compliance_status = payload.compliance_status
    policy.purchase_restricted = bool(payload.purchase_restricted)
    policy.restriction_reason = (payload.restriction_reason or "").strip() or None
    policy.restricted_at = datetime.now(timezone.utc) if policy.purchase_restricted else None
    db.commit()
    db.refresh(policy)

    if policy.purchase_restricted:
        create_notification(
            db,
            user_id=user_id,
            actor_user_id=current_user.id,
            notification_type="buyer_client_compliance",
            title="Acesso de clientes restrito por compliance",
            message=policy.restriction_reason or "Seu acesso para comprar/adicionar clientes foi restrito por descumprimento contratual.",
            resource_type="buyer_client_policy",
            resource_id=str(user_id),
        )
        db.commit()

    return {"ok": True, "policy": _policy_summary(policy)}
