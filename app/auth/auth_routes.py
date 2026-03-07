from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database.connection import get_db
from app.models.user import User
from app.schemas.user_schema import (
    UserCreate, UserLogin, UserResponse,
    UserUpdate, UserProfile
)
from app.core.auth_middleware import get_current_user

from app.auth.password_hash import hash_password, verify_password
from app.auth.jwt_handler import create_access_token

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)


# -----------------------
# REGISTER
# -----------------------
@router.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):

    existing_user = db.query(User).filter(User.email == user.email).first()

    if existing_user:
        raise HTTPException(400, "Email já cadastrado")

    if user.role == "admin":
        raise HTTPException(403, "Não é permitido registrar conta admin por esta rota")

    hashed_password = hash_password(user.password)

    new_user = User(
        name=user.name,
        email=user.email,
        password=hashed_password,
        role=user.role,
        phone=user.phone,
        location=user.location,
        bio=user.bio
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# -----------------------
# LOGIN
# -----------------------
@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):

    db_user = db.query(User).filter(User.email == user.email).first()

    if not db_user:
        raise HTTPException(401, "Credenciais inválidas")

    if not verify_password(user.password, db_user.password):
        raise HTTPException(401, "Credenciais inválidas")

    if not db_user.is_active:
        raise HTTPException(403, "Conta desativada")

    token = create_access_token({
        "user_id": db_user.id,
        "email": db_user.email,
        "role": db_user.role
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": db_user.id,
            "name": db_user.name,
            "email": db_user.email,
            "role": db_user.role
        }
    }


# -----------------------
# GET CURRENT USER PROFILE
# -----------------------
@router.get("/me", response_model=UserProfile)
def get_current_user_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    # Calcular estatísticas
    from sqlalchemy import func
    from app.models import Offer, Transaction, Favorite, Message

    # Total de ofertas
    total_offers = db.query(func.count(Offer.id)).filter(Offer.user_id == current_user.id).scalar()

    # Total de vendas (transações como vendedor)
    total_sales = db.query(func.count(Transaction.id)).join(Offer).filter(Offer.user_id == current_user.id).scalar()

    # Total de compras
    total_purchases = db.query(func.count(Transaction.id)).filter(Transaction.buyer_id == current_user.id).scalar()

    # Total de favoritos
    favorite_count = db.query(func.count(Favorite.id)).filter(Favorite.user_id == current_user.id).scalar()

    # Mensagens não lidas
    unread_messages = db.query(func.count(Message.id)).filter(
        Message.receiver_id == current_user.id,
        Message.is_read == False
    ).scalar()

    profile_data = {
        **current_user.__dict__,
        "total_offers": total_offers,
        "total_sales": total_sales,
        "total_purchases": total_purchases,
        "favorite_count": favorite_count,
        "unread_messages": unread_messages
    }

    return profile_data


# -----------------------
# UPDATE USER PROFILE
# -----------------------
@router.put("/me", response_model=UserResponse)
def update_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    for field, value in user_update.dict(exclude_unset=True).items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)

    return current_user


# -----------------------
# CHANGE PASSWORD
# -----------------------
@router.post("/change-password")
def change_password(
    current_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if not verify_password(current_password, current_user.password):
        raise HTTPException(400, "Senha atual incorreta")

    if len(new_password) < 6:
        raise HTTPException(400, "Nova senha deve ter pelo menos 6 caracteres")

    current_user.password = hash_password(new_password)
    db.commit()

    return {"message": "Senha alterada com sucesso"}