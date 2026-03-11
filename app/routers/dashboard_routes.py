from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_, text
from typing import Dict, List
from datetime import datetime, timedelta

from app.database.connection import get_db
from app.database.connection import Base
from app.models import User, Offer, Transaction, Review, Favorite, Message
from app.core.auth_middleware import get_current_user
from app.services.profile_service import ProfileService

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"]
)


# -----------------------------
# USER DASHBOARD
# -----------------------------
@router.get("/my-dashboard")
def get_user_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile_service = ProfileService(db)
    current_profile = profile_service.get_or_create_profile(current_user)

    owner_filter = or_(
        Offer.owner_profile_id == current_profile.id,
        and_(Offer.owner_profile_id.is_(None), Offer.user_id == current_user.id),
    )

    seller_offer_ids = db.query(Offer.id).filter(owner_filter)

    # Estatísticas básicas
    total_offers = db.query(func.count(Offer.id)).filter(owner_filter).scalar()

    active_offers = db.query(func.count(Offer.id)).filter(
        owner_filter,
        Offer.status == "active"
    ).scalar()

    total_sales = db.query(func.count(Transaction.id)).join(Offer).filter(
        owner_filter
    ).scalar()

    total_purchases = db.query(func.count(Transaction.id)).filter(
        Transaction.buyer_id == current_user.id
    ).scalar()

    favorites_count = db.query(func.count(Favorite.id)).filter(
        Favorite.user_id == current_user.id
    ).scalar()

    unread_messages = db.query(func.count(Message.id)).filter(
        Message.receiver_id == current_user.id,
        Message.is_read == False
    ).scalar()

    # Receita total
    total_revenue = db.query(func.sum(Transaction.total_price)).join(Offer).filter(
        owner_filter,
        Transaction.status == "completed"
    ).scalar() or 0

    # Gasto total
    total_spent = db.query(func.sum(Transaction.total_price)).filter(
        Transaction.buyer_id == current_user.id,
        Transaction.status == "completed"
    ).scalar() or 0

    # Ofertas recentes
    recent_offers = db.query(Offer).filter(
        owner_filter
    ).order_by(desc(Offer.created_at)).limit(5).all()

    # Transações recentes
    recent_transactions = db.query(Transaction).filter(
        or_(
            Transaction.buyer_id == current_user.id,
            Transaction.offer_id.in_(seller_offer_ids)
        )
    ).order_by(desc(Transaction.created_at)).limit(5).all()

    # Quebra de ofertas por status
    offers_by_status = db.query(
        Offer.status,
        func.count(Offer.id)
    ).filter(
        owner_filter
    ).group_by(Offer.status).all()

    # Atividade dos ultimos 7 dias
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_sales = db.query(
        func.date(Transaction.created_at).label("date"),
        func.count(Transaction.id).label("count"),
        func.sum(Transaction.total_price).label("value")
    ).join(Offer).filter(
        owner_filter,
        Transaction.created_at >= seven_days_ago
    ).group_by(func.date(Transaction.created_at)).order_by(func.date(Transaction.created_at)).all()

    completion_rate = 0.0
    if total_sales > 0:
        completed_sales = db.query(func.count(Transaction.id)).join(Offer).filter(
            owner_filter,
            Transaction.status == "completed"
        ).scalar()
        completion_rate = (completed_sales / total_sales) * 100

    return {
        "user": {
            "id": current_user.id,
            "name": current_user.name,
            "role": current_user.role,
            "rating": current_user.rating,
            "is_verified": current_user.is_verified
        },
        "stats": {
            "total_offers": total_offers,
            "active_offers": active_offers,
            "total_sales": total_sales,
            "total_purchases": total_purchases,
            "total_revenue": float(total_revenue),
            "total_spent": float(total_spent),
            "favorites_count": favorites_count,
            "unread_messages": unread_messages,
            "completion_rate": round(completion_rate, 2)
        },
        "offers_by_status": dict(offers_by_status),
        "weekly_activity": [
            {
                "date": str(item[0]),
                "transactions": int(item[1] or 0),
                "total_value": float(item[2] or 0)
            }
            for item in recent_sales
        ],
        "recent_offers": [
            {
                "id": str(offer.id),
                "product_name": offer.product_name,
                "price": float(offer.price),
                "status": offer.status,
                "created_at": offer.created_at
            } for offer in recent_offers
        ],
        "recent_transactions": [
            {
                "id": str(tx.id),
                "type": "sale"
                if (
                    tx.offer.owner_profile_id == current_profile.id
                    or (tx.offer.owner_profile_id is None and tx.offer.user_id == current_user.id)
                )
                else "purchase",
                "product_name": tx.offer.product_name,
                "total_price": float(tx.total_price),
                "status": tx.status,
                "created_at": tx.created_at
            } for tx in recent_transactions
        ]
    }


# -----------------------------
# ADMIN DASHBOARD
# -----------------------------
@router.get("/admin")
def get_admin_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if current_user.role != "admin":
        raise HTTPException(403, "Acesso negado")

    # Estatísticas gerais
    total_users = db.query(func.count(User.id)).scalar()
    total_offers = db.query(func.count(Offer.id)).scalar()
    total_transactions = db.query(func.count(Transaction.id)).scalar()

    # Usuários por role
    users_by_role = db.query(
        User.role,
        func.count(User.id)
    ).group_by(User.role).all()

    # Ofertas por status
    offers_by_status = db.query(
        Offer.status,
        func.count(Offer.id)
    ).group_by(Offer.status).all()

    # Transações por status
    transactions_by_status = db.query(
        Transaction.status,
        func.count(Transaction.id)
    ).group_by(Transaction.status).all()

    # Receita total
    total_revenue = db.query(func.sum(Transaction.total_price)).filter(
        Transaction.status == "completed"
    ).scalar() or 0

    # Usuários ativos (últimos 30 dias)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    active_users = db.query(func.count(func.distinct(Transaction.buyer_id))).filter(
        Transaction.created_at >= thirty_days_ago
    ).scalar()

    # Top produtos
    top_products = db.query(
        Offer.product_name,
        func.count(Transaction.id).label('sales_count'),
        func.sum(Transaction.total_price).label('total_revenue')
    ).join(Transaction).filter(
        Transaction.status == "completed"
    ).group_by(Offer.product_name).order_by(desc('sales_count')).limit(10).all()

    return {
        "overview": {
            "total_users": total_users,
            "total_offers": total_offers,
            "total_transactions": total_transactions,
            "total_revenue": float(total_revenue),
            "active_users_30d": active_users
        },
        "breakdown": {
            "users_by_role": dict(users_by_role),
            "offers_by_status": dict(offers_by_status),
            "transactions_by_status": dict(transactions_by_status)
        },
        "top_products": [
            {
                "product_name": product,
                "sales_count": count,
                "total_revenue": float(revenue or 0)
            } for product, count, revenue in top_products
        ]
    }


@router.post("/admin/purge")
def purge_platform_data(
    confirmation: str = Query(..., description="Digite APAGAR TUDO para confirmar"),
    keep_admins: bool = Query(True, description="Mantém contas admin ativas"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Apaga dados da plataforma de forma irreversível (somente admin)."""
    if current_user.role != "admin":
        raise HTTPException(403, "Acesso negado")

    if confirmation.strip().upper() != "APAGAR TUDO":
        raise HTTPException(400, "Confirmação inválida. Digite exatamente: APAGAR TUDO")

    users_deleted = 0
    with db.begin():
        # Remove registros de todas as tabelas aplicando ordem reversa para respeitar FKs.
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in {"alembic_version"}:
                continue

            if keep_admins and table.name == "users":
                result = db.execute(text("DELETE FROM users WHERE role <> 'admin'"))
                users_deleted = int(result.rowcount or 0)
                continue

            db.execute(table.delete())

    return {
        "message": "Limpeza concluída com sucesso.",
        "keep_admins": keep_admins,
        "users_deleted": users_deleted,
    }


# -----------------------------
# SALES REPORT
# -----------------------------
@router.get("/reports/sales")
def get_sales_report(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = 30
):

    if current_user.role not in ["producer", "admin"]:
        raise HTTPException(403, "Apenas produtores podem acessar relatórios de vendas")

    start_date = datetime.utcnow() - timedelta(days=days)
    profile_service = ProfileService(db)
    current_profile = profile_service.get_or_create_profile(current_user)

    owner_filter = or_(
        Offer.owner_profile_id == current_profile.id,
        and_(Offer.owner_profile_id.is_(None), Offer.user_id == current_user.id),
    )

    # Vendas por período
    sales_by_period = db.query(
        func.date(Transaction.created_at).label('date'),
        func.count(Transaction.id).label('sales_count'),
        func.sum(Transaction.total_price).label('total_revenue')
    ).join(Offer).filter(
        owner_filter,
        Transaction.created_at >= start_date,
        Transaction.status == "completed"
    ).group_by(func.date(Transaction.created_at)).order_by('date').all()

    # Top produtos vendidos
    top_sold_products = db.query(
        Offer.product_name,
        func.count(Transaction.id).label('sales_count'),
        func.sum(Transaction.total_price).label('total_revenue')
    ).join(Transaction).filter(
        owner_filter,
        Transaction.created_at >= start_date,
        Transaction.status == "completed"
    ).group_by(Offer.product_name).order_by(desc('sales_count')).limit(10).all()

    # Receita total no período
    total_revenue = db.query(func.sum(Transaction.total_price)).join(Offer).filter(
        owner_filter,
        Transaction.created_at >= start_date,
        Transaction.status == "completed"
    ).scalar() or 0

    return {
        "period_days": days,
        "total_revenue": float(total_revenue),
        "sales_by_period": [
            {
                "date": str(date),
                "sales_count": count,
                "total_revenue": float(revenue or 0)
            } for date, count, revenue in sales_by_period
        ],
        "top_products": [
            {
                "product_name": product,
                "sales_count": count,
                "total_revenue": float(revenue or 0)
            } for product, count, revenue in top_sold_products
        ]
    }


# -----------------------------
# MARKET INSIGHTS
# -----------------------------
@router.get("/insights")
def get_market_insights(db: Session = Depends(get_db)):

    # Preços médios por categoria
    avg_prices_by_category = db.query(
        Offer.category,
        func.avg(Offer.price).label('avg_price'),
        func.count(Offer.id).label('offer_count')
    ).filter(
        Offer.category.isnot(None),
        Offer.status == "active"
    ).group_by(Offer.category).order_by(desc('offer_count')).all()

    # Produtos mais procurados (por visualizações)
    popular_products = db.query(
        Offer.product_name,
        func.sum(Offer.views).label('total_views'),
        func.avg(Offer.price).label('avg_price')
    ).filter(Offer.status == "active").group_by(Offer.product_name).order_by(desc('total_views')).limit(10).all()

    # Atividade recente (últimas 24h)
    yesterday = datetime.utcnow() - timedelta(days=1)

    new_offers_24h = db.query(func.count(Offer.id)).filter(
        Offer.created_at >= yesterday
    ).scalar()

    new_transactions_24h = db.query(func.count(Transaction.id)).filter(
        Transaction.created_at >= yesterday
    ).scalar()

    return {
        "price_insights": [
            {
                "category": category or "Sem categoria",
                "avg_price": float(avg_price or 0),
                "offer_count": count
            } for category, avg_price, count in avg_prices_by_category
        ],
        "popular_products": [
            {
                "product_name": product,
                "total_views": int(views or 0),
                "avg_price": float(avg_price or 0)
            } for product, views, avg_price in popular_products
        ],
        "recent_activity": {
            "new_offers_24h": new_offers_24h,
            "new_transactions_24h": new_transactions_24h
        }
    }