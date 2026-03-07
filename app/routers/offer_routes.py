from fastapi import APIRouter, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, desc
from typing import List, Optional
from uuid import UUID
import logging
import time
import json
import math

from app.database.connection import get_db
from app.models import Offer, User, Favorite
from app.schemas import (
    OfferCreate, OfferUpdate, OfferResponse, PaginatedOfferResponse,
    OfferSearchFilters
)
from app.cache.redis_client import get_cache, set_cache
from app.core.auth_middleware import get_current_user, require_producer_or_admin, optional_auth

logger = logging.getLogger("offer_logger")

router = APIRouter(
    prefix="/offers",
    tags=["offers"]
)

# -----------------------------
# WebSocket Manager
# -----------------------------
class SmartConnectionManager:

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.groups: dict = {}
        self.alert_queue: dict = {}

    async def connect(self, websocket: WebSocket, group: Optional[str] = None):
        await websocket.accept()
        self.active_connections.append(websocket)

        if group:
            self.groups.setdefault(group, []).append(websocket)

    def disconnect(self, websocket: WebSocket):

        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        for group in self.groups.values():
            if websocket in group:
                group.remove(websocket)

    async def queue_alert(self, message: dict, group: Optional[str] = None):

        target_group = group or "global"
        self.alert_queue.setdefault(target_group, []).append(message)

    async def broadcast_alerts(self, group: Optional[str] = None):

        target_group = group or "global"
        messages = self.alert_queue.get(target_group, [])

        if not messages:
            return

        connections = self.groups.get(group, self.active_connections)

        for conn in connections:
            for msg in messages:
                await conn.send_json(msg)

        self.alert_queue[target_group] = []


manager = SmartConnectionManager()


@router.websocket("/ws/notifications/{group_name}")
async def websocket_endpoint(websocket: WebSocket, group_name: Optional[str] = None):

    await manager.connect(websocket, group_name)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# -----------------------------
# CREATE OFFER
# -----------------------------
@router.post("/", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
async def create_offer(
    offer: OfferCreate,
    current_user: User = Depends(require_producer_or_admin),
    db: Session = Depends(get_db)
):

    new_offer = Offer(
        **offer.dict(),
        user_id=current_user.id
    )

    if isinstance(offer.images, list):
        new_offer.images = json.dumps(offer.images)

    db.add(new_offer)
    db.commit()
    db.refresh(new_offer)

    await manager.queue_alert({
        "event": "offer_created",
        "offer_id": str(new_offer.id),
        "product_name": new_offer.product_name,
        "location": new_offer.location,
        "price": float(new_offer.price),
        "owner": {
            "id": current_user.id,
            "name": current_user.name
        }
    }, group=new_offer.location)

    await manager.broadcast_alerts(new_offer.location)

    return new_offer


# -----------------------------
# GET MY OFFERS
# -----------------------------
@router.get("/my", response_model=List[OfferResponse])
def get_my_offers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(
        None,
        pattern="^(active|sold|paused|expired)$"
    )
):

    query = db.query(Offer).filter(Offer.user_id == current_user.id)

    if status_filter:
        query = query.filter(Offer.status == status_filter)

    offers = query.order_by(desc(Offer.created_at)).offset(skip).limit(limit).all()

    return offers


# -----------------------------
# GET OFFERS (AVANÇADO)
# -----------------------------
@router.get("/", response_model=PaginatedOfferResponse)
def get_offers(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(optional_auth),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    location: Optional[str] = None,
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    organic: Optional[bool] = None,
    quality_grade: Optional[str] = None,
    latitude: Optional[float] = Query(None, ge=-90, le=90),
    longitude: Optional[float] = Query(None, ge=-180, le=180),
    radius: Optional[float] = Query(None, ge=0.1, le=100),  # Raio em km
    sort_by: str = Query("created_at", pattern="^(created_at|price|views|rating)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$")
):

    # Criar chave de cache baseada nos filtros
    cache_key = f"offers:{skip}:{limit}:{search}:{category}:{location}:{min_price}:{max_price}:{organic}:{quality_grade}:{latitude}:{longitude}:{radius}:{sort_by}:{sort_order}"

    cached = get_cache(cache_key)
    if cached:
        return json.loads(cached)

    query = db.query(Offer).filter(Offer.status == "active")

    # Filtros de texto
    if search:
        query = query.filter(
            or_(
                Offer.product_name.ilike(f"%{search}%"),
                Offer.description.ilike(f"%{search}%"),
                Offer.location.ilike(f"%{search}%")
            )
        )

    if category:
        query = query.filter(Offer.category.ilike(f"%{category}%"))

    if location:
        query = query.filter(Offer.location.ilike(f"%{location}%"))

    # Filtros numéricos
    if min_price is not None:
        query = query.filter(Offer.price >= min_price)

    if max_price is not None:
        query = query.filter(Offer.price <= max_price)

    # Filtros booleanos
    if organic is not None:
        query = query.filter(Offer.organic == organic)

    if quality_grade:
        query = query.filter(Offer.quality_grade == quality_grade)

    # Filtro geográfico (se coordenadas fornecidas)
    if latitude and longitude and radius:
        # Fórmula de Haversine para calcular distância
        # Esta é uma simplificação - em produção usaria PostGIS
        query = query.filter(
            and_(
                Offer.latitude.isnot(None),
                Offer.longitude.isnot(None)
            )
        )

    # Ordenação
    order_column = getattr(Offer, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(order_column))
    else:
        query = query.order_by(order_column)

    # Contagem total (antes da paginação)
    total = query.count()

    # Aplicar paginação
    offers = query.offset(skip).limit(limit).all()

    # Adicionar dados do proprietário e verificar se está nos favoritos do usuário
    for offer in offers:
        # Dados do proprietário
        offer.owner_data = {
            "id": offer.owner.id,
            "name": offer.owner.name,
            "rating": offer.owner.rating,
            "location": offer.owner.location
        }

        # Verificar se está nos favoritos (se usuário logado)
        if current_user:
            favorite = db.query(Favorite).filter(
                Favorite.user_id == current_user.id,
                Favorite.offer_id == offer.id
            ).first()
            offer.is_favorited = favorite is not None
        else:
            offer.is_favorited = False

    # Estatísticas avançadas
    stats_query = db.query(
        func.count(Offer.id),
        func.avg(Offer.price),
        func.sum(Offer.quantity),
        func.min(Offer.price),
        func.max(Offer.price)
    ).filter(Offer.status == "active")

    if search:
        stats_query = stats_query.filter(
            or_(
                Offer.product_name.ilike(f"%{search}%"),
                Offer.description.ilike(f"%{search}%")
            )
        )

    stats = stats_query.one()

    response = PaginatedOfferResponse(
        total=total,
        skip=skip,
        limit=limit,
        offers=offers,
        stats={
            "total_offers": stats[0] or 0,
            "avg_price": float(stats[1] or 0),
            "total_quantity": float(stats[2] or 0),
            "min_price": float(stats[3] or 0),
            "max_price": float(stats[4] or 0),
            "filters_applied": {
                "search": search,
                "category": category,
                "location": location,
                "price_range": f"{min_price or 0} - {max_price or '∞'}",
                "organic": organic,
                "quality_grade": quality_grade,
                "geographic": bool(latitude and longitude and radius)
            }
        }
    )

    # Cache por 5 minutos
    set_cache(cache_key, json.dumps(response.dict()), 300)

    return response


# -----------------------------
# GET OFFER
# -----------------------------
@router.get("/{offer_id}", response_model=OfferResponse)
def get_offer(
    offer_id: UUID,
    current_user: Optional[User] = Depends(optional_auth),
    db: Session = Depends(get_db)
):

    offer = db.query(Offer).filter(Offer.id == offer_id).first()

    if not offer:
        raise HTTPException(404, "Oferta não encontrada")

    # Incrementar visualizações (exceto para o próprio dono)
    if not current_user or current_user.id != offer.user_id:
        offer.views += 1
        db.commit()

    # Verificar se está nos favoritos do usuário
    is_favorited = False
    if current_user:
        favorite = db.query(Favorite).filter(
            Favorite.user_id == current_user.id,
            Favorite.offer_id == offer.id
        ).first()
        is_favorited = favorite is not None

    # Adicionar dados do proprietário
    offer.owner_data = {
        "id": offer.owner.id,
        "name": offer.owner.name,
        "rating": offer.owner.rating,
        "total_reviews": offer.owner.total_reviews,
        "location": offer.owner.location,
        "is_verified": offer.owner.is_verified
    }

    offer.is_favorited = is_favorited

    return offer


# -----------------------------
# DELETE OFFER
# -----------------------------
@router.delete("/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_offer(
    offer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    offer = db.query(Offer).filter(Offer.id == offer_id).first()

    if not offer:
        raise HTTPException(404, "Oferta não encontrada")

    # Verificar se o usuário é o dono da oferta ou admin
    if offer.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Apenas o dono da oferta pode excluí-la")

    db.delete(offer)
    db.commit()


# -----------------------------
# UPDATE OFFER
# -----------------------------
@router.put("/{offer_id}", response_model=OfferResponse)
def update_offer(
    offer_id: UUID,
    offer_update: OfferUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    offer = db.query(Offer).filter(Offer.id == offer_id).first()

    if not offer:
        raise HTTPException(404, "Oferta não encontrada")

    # Verificar se o usuário é o dono da oferta ou admin
    if offer.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Apenas o dono da oferta pode editá-la")

    # Não permitir alterar status para vendido se não for através de uma transação
    if offer_update.status == "sold" and offer.status != "sold":
        raise HTTPException(400, "Status 'sold' só pode ser definido através de uma transação")

    # Atualizar campos
    for field, value in offer_update.dict(exclude_unset=True).items():
        if field == "images" and isinstance(value, list):
            value = json.dumps(value)
        setattr(offer, field, value)

    db.commit()
    db.refresh(offer)

    return offer