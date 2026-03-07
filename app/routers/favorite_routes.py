from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database.connection import get_db
from app.models import Favorite, Offer, User
from app.schemas import FavoriteCreate, FavoriteResponse, FavoriteUpdate
from app.core.auth_middleware import get_current_user

router = APIRouter(
    prefix="/favorites",
    tags=["favorites"]
)


# -----------------------------
# ADD TO FAVORITES
# -----------------------------
@router.post("/", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
def add_to_favorites(
    favorite: FavoriteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # Verificar se a oferta existe
    offer = db.query(Offer).filter(Offer.id == favorite.offer_id).first()
    if not offer:
        raise HTTPException(404, "Oferta não encontrada")

    # Verificar se já está nos favoritos
    existing = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.offer_id == favorite.offer_id
    ).first()

    if existing:
        raise HTTPException(400, "Esta oferta já está nos seus favoritos")

    # Criar favorito
    new_favorite = Favorite(
        user_id=current_user.id,
        offer_id=favorite.offer_id,
        notes=favorite.notes
    )

    db.add(new_favorite)

    # Incrementar contador de favoritos da oferta
    offer.favorites_count += 1

    db.commit()
    db.refresh(new_favorite)

    return new_favorite


# -----------------------------
# GET MY FAVORITES
# -----------------------------
@router.get("/my", response_model=List[FavoriteResponse])
def get_my_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20
):

    favorites = db.query(Favorite).filter(
        Favorite.user_id == current_user.id
    ).order_by(Favorite.created_at.desc()).offset(skip).limit(limit).all()

    return favorites


# -----------------------------
# REMOVE FROM FAVORITES
# -----------------------------
@router.delete("/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_favorites(
    offer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    favorite = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.offer_id == offer_id
    ).first()

    if not favorite:
        raise HTTPException(404, "Favorito não encontrado")

    # Decrementar contador de favoritos da oferta
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if offer and offer.favorites_count > 0:
        offer.favorites_count -= 1

    db.delete(favorite)
    db.commit()


# -----------------------------
# UPDATE FAVORITE NOTES
# -----------------------------
@router.put("/{offer_id}", response_model=FavoriteResponse)
def update_favorite_notes(
    offer_id: UUID,
    update_data: FavoriteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    favorite = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.offer_id == offer_id
    ).first()

    if not favorite:
        raise HTTPException(404, "Favorito não encontrado")

    # Atualizar notas
    if update_data.notes is not None:
        favorite.notes = update_data.notes

    db.commit()
    db.refresh(favorite)

    return favorite


# -----------------------------
# CHECK IF OFFER IS FAVORITED
# -----------------------------
@router.get("/check/{offer_id}")
def check_favorite(
    offer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    favorite = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.offer_id == offer_id
    ).first()

    return {
        "is_favorited": favorite is not None,
        "notes": favorite.notes if favorite else None
    }