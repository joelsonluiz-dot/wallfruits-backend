from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, cast, String
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.core.domain_permissions import enforce_negotiation_policy
from app.database.connection import get_db
from app.models.buyer_client import BuyerClientPolicy
from app.models import Offer, Transaction, User
from app.models.agenda_event import AgendaEvent
from app.schemas import TransactionCreate, TransactionResponse, TransactionUpdate
from app.services.profile_service import ProfileService
from app.services.notification_service import create_notification
from app.services.agenda_proactive_service import (
    maybe_create_rule_notifications,
    emit_predictive_notifications_for_user,
    event_rule_hints,
)

router = APIRouter(
    prefix="/transactions",
    tags=["transactions"],
)


def _seller_offer_scope(*, current_user: User, current_profile_id):
    return or_(
        Offer.owner_profile_id == current_profile_id,
        and_(Offer.owner_profile_id.is_(None), Offer.user_id == current_user.id),
    )


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _find_transaction_agenda_events(db: Session, *, transaction_id: UUID):
    token = str(transaction_id)
    return (
        db.query(AgendaEvent)
        .filter(
            AgendaEvent.event_type == "reservation",
            cast(AgendaEvent.meta_json, String).like(f'%"transaction_id": "{token}"%'),
        )
        .all()
    )


def _create_transaction_agenda_events(
    db: Session,
    *,
    transaction: Transaction,
    offer: Offer,
    buyer_user: User,
    seller_user: User,
) -> None:
    starts_at = _as_utc(transaction.reservation_date or datetime.now(timezone.utc))
    ends_at = starts_at + timedelta(hours=1)

    pairs = [
        {
            "user": buyer_user,
            "role": "buyer",
            "counterparty": seller_user,
            "title": f"Reserva de compra: {offer.product_name}",
        },
        {
            "user": seller_user,
            "role": "seller",
            "counterparty": buyer_user,
            "title": f"Reserva recebida: {offer.product_name}",
        },
    ]

    for pair in pairs:
        meta = {
            "transaction_id": str(transaction.id),
            "offer_id": str(offer.id),
            "role": pair["role"],
            "counterparty_user_id": pair["counterparty"].id,
            "counterparty_name": pair["counterparty"].name,
            "quantity": float(transaction.quantity),
            "unit": offer.unit,
        }
        meta["rule_hints"] = event_rule_hints(starts_at, ends_at)

        item = AgendaEvent(
            user_id=pair["user"].id,
            title=pair["title"],
            description=(
                f"Reserva #{transaction.id} de {transaction.quantity} {offer.unit} de {offer.product_name}. "
                f"Contraparte: {pair['counterparty'].name}."
            ),
            event_type="reservation",
            starts_at=starts_at,
            ends_at=ends_at,
            status="scheduled",
            is_all_day=False,
            meta_json=meta,
        )
        db.add(item)
        db.flush()
        maybe_create_rule_notifications(db, user_id=pair["user"].id, event=item)

    emit_predictive_notifications_for_user(db, user_id=buyer_user.id)
    emit_predictive_notifications_for_user(db, user_id=seller_user.id)


def _sync_transaction_agenda_status(db: Session, *, transaction: Transaction, next_status: str | None) -> None:
    if not next_status:
        return

    status_map = {
        "pending": "scheduled",
        "confirmed": "scheduled",
        "completed": "completed",
        "cancelled": "cancelled",
    }
    agenda_status = status_map.get(next_status)
    if not agenda_status:
        return

    rows = _find_transaction_agenda_events(db, transaction_id=transaction.id)
    for row in rows:
        row.status = agenda_status


# -----------------------------
# CREATE TRANSACTION (COMPRAR)
# -----------------------------
@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction: TransactionCreate,
    _policy_guard: None = Depends(enforce_negotiation_policy),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client_policy = db.query(BuyerClientPolicy).filter(BuyerClientPolicy.user_id == current_user.id).first()
    if client_policy and client_policy.purchase_restricted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Acesso temporariamente restrito para compras por descumprimento contratual "
                "na gestão de clientes. Regularize com o suporte/admin."
            ),
        )

    profile_service = ProfileService(db)
    buyer_profile = profile_service.get_or_create_profile(current_user)

    offer = db.query(Offer).filter(
        Offer.id == transaction.offer_id,
        Offer.status == "active",
    ).first()

    if not offer:
        raise HTTPException(404, "Oferta não encontrada ou não está disponível")

    seller_profile = profile_service.ensure_offer_owner_profile(offer)
    if seller_profile.id == buyer_profile.id:
        raise HTTPException(400, "Não é possível comprar sua própria oferta")

    if transaction.quantity > offer.quantity:
        raise HTTPException(
            400,
            f"Quantidade solicitada ({transaction.quantity}) maior que disponível ({offer.quantity})",
        )

    if offer.min_order and transaction.quantity < offer.min_order:
        raise HTTPException(
            400,
            f"Quantidade minima para reserva: {offer.min_order}",
        )

    today = datetime.now(timezone.utc).date()
    if offer.reservation_start and today < offer.reservation_start:
        raise HTTPException(400, "Periodo de reserva ainda nao iniciado para esta oferta")

    if offer.reservation_end and today > offer.reservation_end:
        raise HTTPException(400, "Periodo de reserva encerrado para esta oferta")

    reservation_dt = transaction.reservation_date or datetime.now(timezone.utc)
    reservation_day = reservation_dt.date()
    if offer.reservation_start and reservation_day < offer.reservation_start:
        raise HTTPException(400, "Data da reserva fora do periodo permitido (antes do inicio)")
    if offer.reservation_end and reservation_day > offer.reservation_end:
        raise HTTPException(400, "Data da reserva fora do periodo permitido (apos o fim)")

    if transaction.delivery_method == "delivery" and not (transaction.delivery_address or "").strip():
        raise HTTPException(400, "Endereco de entrega e obrigatorio para entrega")

    unit_market = Decimal(str(offer.price_per_kg or offer.price or 0))
    unit_min = Decimal(str(offer.price_min_kg or unit_market))
    unit_max = Decimal(str(offer.price_max_kg or unit_market))

    pricing_mode = transaction.pricing_mode or "market"
    if pricing_mode == "min":
        unit_price = unit_min
    elif pricing_mode == "free":
        if transaction.offered_unit_price is None:
            raise HTTPException(400, "Preco livre deve ser informado")
        offered_price = Decimal(str(transaction.offered_unit_price))
        if offered_price < unit_min:
            raise HTTPException(400, f"Preco livre deve ser maior ou igual ao minimo ({unit_min})")
        unit_price = offered_price
    else:
        unit_price = unit_market

    quantity_dec = Decimal(str(transaction.quantity))
    total_price = (unit_price * quantity_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    fee_per_kg = Decimal("0.005")
    unit_text = (offer.unit or "").strip().lower()
    if "kg" in unit_text:
        quantity_in_kg = quantity_dec
    else:
        box_weight = Decimal(str(offer.box_weight_kg or 1))
        quantity_in_kg = quantity_dec * box_weight
    reservation_fee_total = (quantity_in_kg * fee_per_kg).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    new_transaction = Transaction(
        buyer_id=current_user.id,
        offer_id=transaction.offer_id,
        quantity=transaction.quantity,
        unit_price=unit_price,
        total_price=total_price,
        delivery_method=transaction.delivery_method,
        delivery_address=transaction.delivery_address,
        delivery_date=transaction.delivery_date,
        reservation_date=reservation_dt,
        pricing_mode=pricing_mode,
        negotiated_unit_price=unit_price,
        reservation_fee_per_kg=fee_per_kg,
        reservation_fee_total=reservation_fee_total,
        contact_name=(transaction.contact_name or "").strip() or None,
        contact_phone=(transaction.contact_phone or "").strip() or None,
        contact_address=(transaction.contact_address or "").strip() or None,
        reservation_metadata={
            "price_min_kg": float(unit_min),
            "price_market_kg": float(unit_market),
            "price_max_kg": float(unit_max),
            "quantity_in_kg": float(quantity_in_kg),
        },
        notes=transaction.notes,
        payment_method=transaction.payment_method,
    )

    db.add(new_transaction)
    db.flush()

    seller_user = offer.owner or db.query(User).filter(User.id == offer.user_id).first()
    if seller_user is None:
        raise HTTPException(500, "Nao foi possivel localizar o usuario da oferta")

    offer.quantity -= transaction.quantity
    if offer.quantity <= 0:
        offer.status = "sold"

    _create_transaction_agenda_events(
        db,
        transaction=new_transaction,
        offer=offer,
        buyer_user=current_user,
        seller_user=seller_user,
    )

    create_notification(
        db,
        user_id=offer.user_id,
        actor_user_id=current_user.id,
        notification_type="reservation",
        title="Nova reserva recebida",
        message=f"{current_user.name} reservou {transaction.quantity} {offer.unit} de {offer.product_name}.",
        resource_type="transaction",
        resource_id=str(new_transaction.id),
    )

    create_notification(
        db,
        user_id=current_user.id,
        actor_user_id=offer.user_id,
        notification_type="reservation",
        title="Reserva registrada",
        message=f"Sua reserva de {transaction.quantity} {offer.unit} de {offer.product_name} foi registrada com sucesso.",
        resource_type="transaction",
        resource_id=str(new_transaction.id),
    )

    db.commit()
    db.refresh(new_transaction)

    return new_transaction


# -----------------------------
# GET MY TRANSACTIONS
# -----------------------------
@router.get("/my", response_model=List[TransactionResponse])
def get_my_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    type: str = Query("all", pattern="^(all|purchases|sales)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    profile_service = ProfileService(db)
    current_profile = profile_service.get_or_create_profile(current_user)
    seller_scope = _seller_offer_scope(
        current_user=current_user,
        current_profile_id=current_profile.id,
    )

    seller_offer_ids = db.query(Offer.id).filter(seller_scope)

    query = db.query(Transaction)

    if type == "purchases":
        query = query.filter(Transaction.buyer_id == current_user.id)
    elif type == "sales":
        query = query.join(Offer).filter(seller_scope)
    else:
        query = query.filter(
            (Transaction.buyer_id == current_user.id)
            | (Transaction.offer_id.in_(seller_offer_ids))
        )

    transactions = query.order_by(Transaction.created_at.desc()).offset(skip).limit(limit).all()
    return transactions


# -----------------------------
# TRANSACTION HISTORY SUMMARY
# -----------------------------
@router.get("/history")
def get_transaction_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    type: str = Query("all", pattern="^(all|purchases|sales)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    profile_service = ProfileService(db)
    current_profile = profile_service.get_or_create_profile(current_user)
    seller_scope = _seller_offer_scope(
        current_user=current_user,
        current_profile_id=current_profile.id,
    )

    seller_offer_ids = db.query(Offer.id).filter(seller_scope)

    base_query = db.query(Transaction)

    if type == "purchases":
        base_query = base_query.filter(Transaction.buyer_id == current_user.id)
    elif type == "sales":
        base_query = base_query.join(Offer).filter(seller_scope)
    else:
        base_query = base_query.filter(
            (Transaction.buyer_id == current_user.id)
            | (Transaction.offer_id.in_(seller_offer_ids))
        )

    total_count = base_query.count()
    items = base_query.order_by(Transaction.created_at.desc()).offset(skip).limit(limit).all()

    status_counts = {}
    total_value = Decimal("0")

    for item in items:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1
        total_value += item.total_price

    return {
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "filters": {"type": type},
        "summary": {
            "status_counts": status_counts,
            "page_total_value": float(total_value),
        },
        "items": items,
    }


# -----------------------------
# GET TRANSACTION
# -----------------------------
@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile_service = ProfileService(db)

    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()

    if not transaction:
        raise HTTPException(404, "Transação não encontrada")

    offer = transaction.offer
    is_seller = profile_service.is_offer_owner(offer=offer, user=current_user)

    if (
        transaction.buyer_id != current_user.id
        and not is_seller
        and current_user.role != "admin"
    ):
        raise HTTPException(403, "Acesso negado")

    return transaction


# -----------------------------
# UPDATE TRANSACTION STATUS
# -----------------------------
@router.put("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: UUID,
    update_data: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile_service = ProfileService(db)

    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()

    if not transaction:
        raise HTTPException(404, "Transação não encontrada")

    offer = transaction.offer
    is_buyer = transaction.buyer_id == current_user.id
    is_seller = profile_service.is_offer_owner(offer=offer, user=current_user)
    is_admin = current_user.role == "admin"

    if not (is_buyer or is_seller or is_admin):
        raise HTTPException(403, "Acesso negado")

    old_status = transaction.status
    seller_user = offer.owner or db.query(User).filter(User.id == offer.user_id).first()

    if update_data.status:
        current_status = transaction.status

        if update_data.status == "confirmed" and is_buyer and current_status == "pending":
            pass
        elif update_data.status == "completed" and (is_seller or is_admin) and current_status in ["confirmed", "paid"]:
            pass
        elif update_data.status == "cancelled" and current_status in ["pending", "confirmed"]:
            if not (is_buyer or is_seller or is_admin):
                raise HTTPException(403, "Acesso negado")
        elif not is_admin:
            raise HTTPException(
                400,
                f"Transição de status não permitida: {current_status} -> {update_data.status}",
            )

    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(transaction, field, value)

    if old_status in ["pending", "confirmed"] and transaction.status == "cancelled":
        offer.quantity += transaction.quantity
        if offer.status == "sold" and offer.quantity > 0:
            offer.status = "active"

    if transaction.status != old_status:
        _sync_transaction_agenda_status(db, transaction=transaction, next_status=transaction.status)

        if seller_user is not None:
            if transaction.status == "confirmed":
                create_notification(
                    db,
                    user_id=offer.user_id,
                    actor_user_id=current_user.id,
                    notification_type="reservation_confirmed",
                    title="Reserva confirmada",
                    message=f"A reserva de {transaction.quantity} {offer.unit} de {offer.product_name} foi confirmada.",
                    resource_type="transaction",
                    resource_id=str(transaction.id),
                )
                create_notification(
                    db,
                    user_id=transaction.buyer_id,
                    actor_user_id=offer.user_id,
                    notification_type="reservation_confirmed",
                    title="Sua reserva foi confirmada",
                    message=f"A reserva de {offer.product_name} foi confirmada.",
                    resource_type="transaction",
                    resource_id=str(transaction.id),
                )

            if transaction.status == "completed":
                create_notification(
                    db,
                    user_id=offer.user_id,
                    actor_user_id=current_user.id,
                    notification_type="reservation_completed",
                    title="Reserva concluida",
                    message=f"A reserva de {offer.product_name} foi concluida.",
                    resource_type="transaction",
                    resource_id=str(transaction.id),
                )
                create_notification(
                    db,
                    user_id=transaction.buyer_id,
                    actor_user_id=offer.user_id,
                    notification_type="reservation_completed",
                    title="Compra concluida",
                    message=f"Sua reserva de {offer.product_name} foi marcada como concluida.",
                    resource_type="transaction",
                    resource_id=str(transaction.id),
                )

            if transaction.status == "cancelled":
                create_notification(
                    db,
                    user_id=offer.user_id,
                    actor_user_id=current_user.id,
                    notification_type="reservation_cancelled",
                    title="Reserva cancelada",
                    message=f"A reserva de {offer.product_name} foi cancelada.",
                    resource_type="transaction",
                    resource_id=str(transaction.id),
                )
                create_notification(
                    db,
                    user_id=transaction.buyer_id,
                    actor_user_id=offer.user_id,
                    notification_type="reservation_cancelled",
                    title="Sua reserva foi cancelada",
                    message=f"A reserva de {offer.product_name} foi cancelada.",
                    resource_type="transaction",
                    resource_id=str(transaction.id),
                )

        emit_predictive_notifications_for_user(db, user_id=transaction.buyer_id)
        if offer.user_id != transaction.buyer_id:
            emit_predictive_notifications_for_user(db, user_id=offer.user_id)

    db.commit()
    db.refresh(transaction)

    return transaction
