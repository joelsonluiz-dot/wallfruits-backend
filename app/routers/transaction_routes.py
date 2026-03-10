from decimal import Decimal
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.core.domain_permissions import enforce_negotiation_policy
from app.database.connection import get_db
from app.models import Offer, Transaction, User
from app.schemas import TransactionCreate, TransactionResponse, TransactionUpdate
from app.services.profile_service import ProfileService
from app.services.notification_service import create_notification

router = APIRouter(
    prefix="/transactions",
    tags=["transactions"],
)


def _seller_offer_scope(*, current_user: User, current_profile_id):
    return or_(
        Offer.owner_profile_id == current_profile_id,
        and_(Offer.owner_profile_id.is_(None), Offer.user_id == current_user.id),
    )


# -----------------------------
# CREATE TRANSACTION (COMPRAR)
# -----------------------------
@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction: TransactionCreate,
    _policy_guard: None = Depends(enforce_negotiation_policy),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

    unit_price = offer.price
    total_price = unit_price * transaction.quantity

    new_transaction = Transaction(
        buyer_id=current_user.id,
        offer_id=transaction.offer_id,
        quantity=transaction.quantity,
        unit_price=unit_price,
        total_price=total_price,
        delivery_method=transaction.delivery_method,
        delivery_address=transaction.delivery_address,
        delivery_date=transaction.delivery_date,
        notes=transaction.notes,
        payment_method=transaction.payment_method,
    )

    db.add(new_transaction)

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

    db.commit()
    db.refresh(new_transaction)

    offer.quantity -= transaction.quantity
    if offer.quantity <= 0:
        offer.status = "sold"

    db.commit()

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

    db.commit()
    db.refresh(transaction)

    return transaction
