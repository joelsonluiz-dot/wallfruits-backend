from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from decimal import Decimal

from app.database.connection import get_db
from app.models import Transaction, Offer, User
from app.schemas import TransactionCreate, TransactionResponse, TransactionUpdate
from app.core.auth_middleware import get_current_user

router = APIRouter(
    prefix="/transactions",
    tags=["transactions"]
)


# -----------------------------
# CREATE TRANSACTION (COMPRAR)
# -----------------------------
@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # Verificar se a oferta existe e está ativa
    offer = db.query(Offer).filter(
        Offer.id == transaction.offer_id,
        Offer.status == "active"
    ).first()

    if not offer:
        raise HTTPException(404, "Oferta não encontrada ou não está disponível")

    # Verificar se o usuário não está comprando sua própria oferta
    if offer.user_id == current_user.id:
        raise HTTPException(400, "Não é possível comprar sua própria oferta")

    # Verificar quantidade disponível
    if transaction.quantity > offer.quantity:
        raise HTTPException(400, f"Quantidade solicitada ({transaction.quantity}) maior que disponível ({offer.quantity})")

    # Calcular valores
    unit_price = offer.price
    total_price = unit_price * transaction.quantity

    # Criar transação
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
        payment_method=transaction.payment_method
    )

    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)

    # Reservar estoque no momento da compra (qualquer método de entrega)
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
    limit: int = Query(20, ge=1, le=100)
):

    query = db.query(Transaction)

    if type == "purchases":
        query = query.filter(Transaction.buyer_id == current_user.id)
    elif type == "sales":
        query = query.join(Offer).filter(Offer.user_id == current_user.id)
    else:  # all
        query = query.filter(
            (Transaction.buyer_id == current_user.id) |
            (Transaction.offer_id.in_(
                db.query(Offer.id).filter(Offer.user_id == current_user.id)
            ))
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
    limit: int = Query(20, ge=1, le=100)
):

    base_query = db.query(Transaction)

    if type == "purchases":
        base_query = base_query.filter(Transaction.buyer_id == current_user.id)
    elif type == "sales":
        base_query = base_query.join(Offer).filter(Offer.user_id == current_user.id)
    else:
        base_query = base_query.filter(
            (Transaction.buyer_id == current_user.id) |
            (Transaction.offer_id.in_(
                db.query(Offer.id).filter(Offer.user_id == current_user.id)
            ))
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
            "page_total_value": float(total_value)
        },
        "items": items
    }


# -----------------------------
# GET TRANSACTION
# -----------------------------
@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()

    if not transaction:
        raise HTTPException(404, "Transação não encontrada")

    # Verificar se o usuário tem permissão para ver esta transação
    offer = transaction.offer
    if (transaction.buyer_id != current_user.id and
        offer.user_id != current_user.id and
        current_user.role != "admin"):
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
    db: Session = Depends(get_db)
):

    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()

    if not transaction:
        raise HTTPException(404, "Transação não encontrada")

    # Verificar permissões
    offer = transaction.offer
    is_buyer = transaction.buyer_id == current_user.id
    is_seller = offer.user_id == current_user.id
    is_admin = current_user.role == "admin"

    if not (is_buyer or is_seller or is_admin):
        raise HTTPException(403, "Acesso negado")

    old_status = transaction.status

    # Regras de atualização de status
    if update_data.status:
        current_status = transaction.status

        # Comprador pode confirmar pedido
        if update_data.status == "confirmed" and is_buyer and current_status == "pending":
            pass  # Permitido
        # Vendedor pode marcar como concluída
        elif update_data.status == "completed" and (is_seller or is_admin) and current_status in ["confirmed", "paid"]:
            pass  # Permitido
        # Cancelamento por comprador/vendedor/admin
        elif update_data.status == "cancelled" and current_status in ["pending", "confirmed"]:
            if not (is_buyer or is_seller or is_admin):
                raise HTTPException(403, "Acesso negado")
        # Admin pode alterar qualquer status
        elif not is_admin:
            raise HTTPException(400, f"Transição de status não permitida: {current_status} -> {update_data.status}")

    # Atualizar campos
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(transaction, field, value)

    # Se a transação foi cancelada, devolver estoque reservado
    if old_status in ["pending", "confirmed"] and transaction.status == "cancelled":
        offer.quantity += transaction.quantity
        if offer.status == "sold" and offer.quantity > 0:
            offer.status = "active"

    db.commit()
    db.refresh(transaction)

    return transaction