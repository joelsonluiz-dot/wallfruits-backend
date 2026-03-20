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
from app.core.auth_middleware import get_current_user, optional_auth
from app.core.domain_permissions import require_approved_offer_publisher
from app.services.profile_service import ProfileService

logger = logging.getLogger("offer_logger")

router = APIRouter(
    prefix="/offers",
    tags=["offers"]
)


def _can_view_private_contact(*, db: Session, current_user: Optional[User], owner_user_id: int) -> bool:
    if not current_user:
        return False
    if current_user.id == owner_user_id or current_user.role == "admin":
        return True
    return ProfileService(db).is_premium(current_user.id)


def _apply_offer_visibility_policy(*, db: Session, offer: Offer, current_user: Optional[User]) -> None:
    can_view_private = _can_view_private_contact(
        db=db,
        current_user=current_user,
        owner_user_id=offer.owner.id,
    )

    restriction_message = (
        "Dados de contato e endereço detalhado são exclusivos para assinantes Premium."
        if not can_view_private
        else None
    )

    offer.owner_data = {
        "id": offer.owner.id,
        "name": offer.owner.name,
        "email": offer.owner.email if can_view_private else None,
        "profile_image": offer.owner.profile_image,
        "rating": offer.owner.rating,
        "total_reviews": offer.owner.total_reviews,
        "location": offer.owner.location if can_view_private else None,
        "is_verified": offer.owner.is_verified,
        "contact_locked": not can_view_private,
        "contact_lock_reason": restriction_message,
    }

    offer.contact_locked = not can_view_private
    offer.private_address_locked = not can_view_private
    offer.restriction_message = restriction_message

    if not can_view_private:
        offer.property_address = None

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
@router.post("", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
async def create_offer(
    offer: OfferCreate,
    current_user: User = Depends(require_approved_offer_publisher),
    db: Session = Depends(get_db)
):

    profile = ProfileService(db).get_or_create_profile(current_user)

    new_offer = Offer(
        **offer.dict(),
        user_id=current_user.id,
        owner_profile_id=profile.id,
        public_price=offer.public_price or offer.price,
        private_price=offer.private_price,
        visibility=offer.visibility or "public",
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
        pattern="^(active|sold|paused|expired|closed|suspended)$"
    )
):
    profile_service = ProfileService(db)
    current_profile = profile_service.get_or_create_profile(current_user)

    query = db.query(Offer).filter(
        or_(
            Offer.owner_profile_id == current_profile.id,
            and_(Offer.owner_profile_id.is_(None), Offer.user_id == current_user.id),
        )
    )

    if status_filter:
        query = query.filter(Offer.status == status_filter)

    offers = query.order_by(desc(Offer.created_at)).offset(skip).limit(limit).all()

    return offers


# -----------------------------
# GET OFFERS (AVANÇADO)
# -----------------------------
@router.get("", response_model=PaginatedOfferResponse)
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
    # Cache apenas para usuário anônimo para evitar vazamento de visão entre perfis.
    cache_key = None
    if current_user is None:
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
        _apply_offer_visibility_policy(db=db, offer=offer, current_user=current_user)

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
    if cache_key:
        set_cache(cache_key, json.dumps(response.model_dump(mode="json")), 300)

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
    is_owner = False
    if current_user:
        previous_owner_profile_id = offer.owner_profile_id
        profile_service = ProfileService(db)
        is_owner = profile_service.is_offer_owner(offer=offer, user=current_user)

        if previous_owner_profile_id is None and offer.owner_profile_id is not None:
            db.commit()

    if not is_owner:
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

    _apply_offer_visibility_policy(db=db, offer=offer, current_user=current_user)

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

    profile_service = ProfileService(db)

    # Verificar se o usuário é o dono da oferta ou admin
    if not profile_service.is_offer_owner(offer=offer, user=current_user):
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

    profile_service = ProfileService(db)

    # Verificar se o usuário é o dono da oferta ou admin
    if not profile_service.is_offer_owner(offer=offer, user=current_user):
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