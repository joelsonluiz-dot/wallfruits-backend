from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_, text
from typing import Any, Dict, List
from datetime import datetime, timedelta

from app.database.connection import get_db
from app.database.connection import Base
from app.models import User, Offer, Transaction, Review, Favorite, Message, Negotiation
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


@router.get("/admin/users")
def list_users_for_admin(
    search: str | None = Query(default=None, description="Filtro por nome/email"),
    limit: int = Query(default=200, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista usuários para gestão administrativa."""
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(403, "Acesso negado")

    query = db.query(User)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(User.name.ilike(term), User.email.ilike(term)))

    users = query.order_by(desc(User.created_at)).limit(limit).all()
    return {
        "items": [
            {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "is_active": bool(user.is_active),
                "is_verified": bool(user.is_verified),
                "is_superuser": bool(user.is_superuser),
                "created_at": user.created_at,
                "last_login": user.last_login,
            }
            for user in users
        ]
    }


@router.patch("/admin/users/{user_id}")
def update_user_by_admin(
    user_id: int,
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permite ao admin ajustar role e status de contas."""
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(403, "Acesso negado")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(404, "Usuário não encontrado")

    allowed_roles = {"buyer", "producer", "supplier", "admin"}

    if "role" in payload and payload["role"] is not None:
        next_role = str(payload["role"]).strip().lower()
        if next_role not in allowed_roles:
            raise HTTPException(400, "Role inválida")
        target_user.role = next_role
        if next_role == "admin":
            target_user.is_superuser = True

    if "is_active" in payload and payload["is_active"] is not None:
        next_is_active = bool(payload["is_active"])
        if target_user.id == current_user.id and not next_is_active:
            raise HTTPException(400, "Você não pode desativar sua própria conta admin")
        target_user.is_active = next_is_active

    if "is_verified" in payload and payload["is_verified"] is not None:
        target_user.is_verified = bool(payload["is_verified"])

    if "is_superuser" in payload and payload["is_superuser"] is not None:
        target_user.is_superuser = bool(payload["is_superuser"])
        if target_user.is_superuser:
            target_user.role = "admin"

    db.commit()
    db.refresh(target_user)

    return {
        "message": "Conta atualizada com sucesso",
        "user": {
            "id": target_user.id,
            "name": target_user.name,
            "email": target_user.email,
            "role": target_user.role,
            "is_active": bool(target_user.is_active),
            "is_verified": bool(target_user.is_verified),
            "is_superuser": bool(target_user.is_superuser),
        },
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


@router.get("/strategy")
def get_strategy_center(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resumo estratégico para tomada de decisão operacional e de crescimento."""
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Acesso restrito")

    total_users = db.query(func.count(User.id)).scalar() or 0
    total_offers = db.query(func.count(Offer.id)).scalar() or 0
    active_offers = db.query(func.count(Offer.id)).filter(Offer.status == "active").scalar() or 0
    total_transactions = db.query(func.count(Transaction.id)).scalar() or 0
    completed_transactions = db.query(func.count(Transaction.id)).filter(Transaction.status == "completed").scalar() or 0
    total_revenue = db.query(func.sum(Transaction.total_price)).filter(Transaction.status == "completed").scalar() or 0

    yesterday = datetime.utcnow() - timedelta(days=1)
    new_offers_24h = db.query(func.count(Offer.id)).filter(Offer.created_at >= yesterday).scalar() or 0
    new_transactions_24h = db.query(func.count(Transaction.id)).filter(Transaction.created_at >= yesterday).scalar() or 0

    avg_prices_by_category = db.query(
        Offer.category,
        func.avg(Offer.price).label("avg_price"),
        func.count(Offer.id).label("offer_count"),
    ).filter(
        Offer.category.isnot(None),
        Offer.status == "active",
    ).group_by(Offer.category).order_by(desc("offer_count")).limit(8).all()

    popular_products = db.query(
        Offer.product_name,
        func.sum(Offer.views).label("total_views"),
        func.avg(Offer.price).label("avg_price"),
    ).filter(
        Offer.status == "active",
    ).group_by(Offer.product_name).order_by(desc("total_views")).limit(8).all()

    conversion_rate = (completed_transactions / total_transactions * 100) if total_transactions else 0.0
    offer_utilization = (completed_transactions / active_offers * 100) if active_offers else 0.0

    health_score = min(
        100.0,
        round(
            min(active_offers * 2.5, 25)
            + min(conversion_rate * 1.2, 35)
            + min((new_transactions_24h * 4), 20)
            + min((new_offers_24h * 2), 20),
            2,
        ),
    )

    recommendations = []
    if active_offers < 10:
        recommendations.append("Aumentar base ativa de ofertas para melhorar liquidez do marketplace.")
    if conversion_rate < 30:
        recommendations.append("Melhorar conversão com respostas mais rápidas em mensagens e negociação.")
    if new_transactions_24h < 3:
        recommendations.append("Executar campanha comercial diária para acelerar volume transacional.")
    if total_users > 0 and (active_offers / max(total_users, 1)) < 0.35:
        recommendations.append("Ativar produtores inativos com incentivo de publicação e destaque inicial.")
    if not recommendations:
        recommendations.append("Operação saudável. Priorize expansão regional e parcerias B2B para escala.")

    return {
        "north_star": {
            "total_users": int(total_users),
            "active_offers": int(active_offers),
            "total_transactions": int(total_transactions),
            "completed_transactions": int(completed_transactions),
            "total_revenue": float(total_revenue),
            "conversion_rate": round(conversion_rate, 2),
            "offer_utilization": round(offer_utilization, 2),
            "health_score": health_score,
        },
        "recent_activity": {
            "new_offers_24h": int(new_offers_24h),
            "new_transactions_24h": int(new_transactions_24h),
        },
        "opportunities": {
            "categories": [
                {
                    "category": category or "Sem categoria",
                    "avg_price": float(avg_price or 0),
                    "offer_count": int(count or 0),
                }
                for category, avg_price, count in avg_prices_by_category
            ],
            "popular_products": [
                {
                    "product_name": product,
                    "total_views": int(views or 0),
                    "avg_price": float(avg_price or 0),
                }
                for product, views, avg_price in popular_products
            ],
        },
        "recommendations": recommendations,
    }


@router.get("/funnel")
def get_commercial_funnel(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Funil comercial oficial: visitante -> mensagem -> negociação -> transação concluída."""
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Acesso restrito")

    since = datetime.utcnow() - timedelta(days=days)

    visitors = db.query(func.sum(Offer.views)).filter(Offer.created_at >= since).scalar() or 0

    messages = db.query(func.count(Message.id)).filter(
        Message.created_at >= since,
        Message.offer_id.isnot(None),
    ).scalar() or 0

    negotiations = db.query(func.count(Negotiation.id)).filter(
        Negotiation.created_at >= since,
    ).scalar() or 0

    completed_transactions = db.query(func.count(Transaction.id)).filter(
        Transaction.created_at >= since,
        Transaction.status == "completed",
    ).scalar() or 0

    def _rate(current: int, previous: int) -> float:
        if previous <= 0:
            return 0.0
        return round((current / previous) * 100, 2)

    conv_visit_to_msg = _rate(messages, visitors)
    conv_msg_to_neg = _rate(negotiations, messages)
    conv_neg_to_tx = _rate(completed_transactions, negotiations)
    conv_total = _rate(completed_transactions, visitors)

    stage_pairs = [
        ("visitante->mensagem", conv_visit_to_msg),
        ("mensagem->negociacao", conv_msg_to_neg),
        ("negociacao->conclusao", conv_neg_to_tx),
    ]
    bottleneck = min(stage_pairs, key=lambda item: item[1])[0]

    return {
        "window_days": days,
        "stages": {
            "visitors": int(visitors),
            "messages": int(messages),
            "negotiations": int(negotiations),
            "completed_transactions": int(completed_transactions),
        },
        "conversion": {
            "visit_to_message": conv_visit_to_msg,
            "message_to_negotiation": conv_msg_to_neg,
            "negotiation_to_completed": conv_neg_to_tx,
            "visitor_to_completed": conv_total,
        },
        "bottleneck": bottleneck,
    }