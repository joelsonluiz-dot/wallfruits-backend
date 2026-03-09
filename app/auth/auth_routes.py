from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import logging

from app.core.config import settings
from app.database.connection import get_db, ensure_auth_schema_compatibility
from app.models.user import User
from app.schemas.user_schema import (
    UserCreate, UserLogin, UserResponse,
    UserUpdate, UserProfile
)
from app.core.auth_middleware import get_current_user
from app.services.supabase_auth_service import (
    SupabaseAuthError,
    create_user_with_password,
    sign_in_with_password,
    supabase_auth_enabled,
    update_password as update_supabase_password,
)

from app.auth.password_hash import hash_password, verify_password
from app.auth.jwt_handler import create_access_token

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

logger = logging.getLogger("wallfruits_api")
bearer_security = HTTPBearer(auto_error=False)


def _normalize_role(role: str | None) -> str:
    if role in {"buyer", "producer", "admin"}:
        return role
    return "buyer"


def _login_response(db_user: User, access_token: str) -> dict:
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": db_user.id,
            "name": db_user.name,
            "email": db_user.email,
            "role": db_user.role
        }
    }


def _get_or_create_local_user_from_supabase(
    *,
    db: Session,
    supabase_user_id: str,
    email: str,
    fallback_name: str,
    fallback_role: str,
    plaintext_password: str,
) -> User:
    db_user = db.query(User).filter(User.supabase_user_id == supabase_user_id).first()
    if not db_user:
        db_user = db.query(User).filter(User.email == email).first()

    if db_user:
        changed = False
        if not db_user.supabase_user_id:
            db_user.supabase_user_id = supabase_user_id
            changed = True
        if changed:
            db.commit()
            db.refresh(db_user)
        return db_user

    db_user = User(
        name=fallback_name,
        email=email,
        password=hash_password(plaintext_password),
        role=_normalize_role(fallback_role),
        supabase_user_id=supabase_user_id,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def ensure_auth_schema_ready() -> None:
    """Garante que colunas novas da tabela users existam antes das consultas."""
    try:
        ensure_auth_schema_compatibility()
    except Exception as exc:
        logger.error(f"Erro ao sincronizar schema de auth: {exc}", exc_info=True)
        raise HTTPException(500, "Erro ao preparar banco de dados")


# -----------------------
# REGISTER
# -----------------------
@router.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    ensure_auth_schema_ready()

    try:
        existing_user = db.query(User.id).filter(User.email == user.email).first()
    except SQLAlchemyError as e:
        logger.error(f"Erro ao consultar email existente: {e}", exc_info=True)
        raise HTTPException(500, "Erro ao validar email no banco")

    if existing_user:
        raise HTTPException(400, "Email já cadastrado")

    if user.role == "admin":
        raise HTTPException(403, "Não é permitido registrar conta admin por esta rota")

    supabase_user_id: str | None = None
    if supabase_auth_enabled():
        try:
            supabase_user = create_user_with_password(
                email=user.email,
                password=user.password,
                user_metadata={
                    "name": user.name,
                    "role": user.role,
                },
            )
            supabase_user_id = supabase_user.get("id")
            if not supabase_user_id:
                raise HTTPException(502, "Supabase Auth retornou usuario sem id")
        except SupabaseAuthError as exc:
            status_code = exc.status_code if exc.status_code >= 400 else 500
            raise HTTPException(status_code, exc.message)

    try:
        hashed_password = hash_password(user.password)
    except Exception as e:
        logger.error(f"Erro ao gerar hash da senha: {e}", exc_info=True)
        raise HTTPException(500, f"Erro ao processar senha: {type(e).__name__}")

    new_user = User(
        name=user.name,
        email=user.email,
        password=hashed_password,
        supabase_user_id=supabase_user_id,
        role=user.role,
        phone=user.phone,
        location=user.location,
        bio=user.bio
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao salvar usuário no banco: {e}", exc_info=True)
        raise HTTPException(500, f"Erro ao criar conta: {type(e).__name__}")

    return new_user


# -----------------------
# LOGIN
# -----------------------
@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    ensure_auth_schema_ready()

    if supabase_auth_enabled():
        try:
            auth_data = sign_in_with_password(user.email, user.password)
        except SupabaseAuthError as exc:
            if exc.status_code in {400, 401, 422}:
                raise HTTPException(401, "Credenciais inválidas")
            raise HTTPException(exc.status_code, exc.message)

        access_token = auth_data.get("access_token")
        supabase_user = auth_data.get("user") or {}
        supabase_user_id = supabase_user.get("id")
        email = supabase_user.get("email") or user.email
        metadata = supabase_user.get("user_metadata") or {}

        if not access_token or not supabase_user_id or not email:
            raise HTTPException(502, "Resposta de login do Supabase incompleta")

        try:
            db_user = _get_or_create_local_user_from_supabase(
                db=db,
                supabase_user_id=supabase_user_id,
                email=email,
                fallback_name=metadata.get("name") or email.split("@")[0],
                fallback_role=metadata.get("role") or "buyer",
                plaintext_password=user.password,
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Erro ao sincronizar usuario local com Supabase: {e}", exc_info=True)
            raise HTTPException(500, "Erro ao sincronizar usuário local")

        if not db_user.is_active:
            raise HTTPException(403, "Conta desativada")

        return _login_response(db_user, access_token)

    try:
        db_user = db.query(User).filter(User.email == user.email).first()
    except SQLAlchemyError as e:
        logger.error(f"Erro ao consultar usuario para login: {e}", exc_info=True)
        raise HTTPException(500, "Erro ao consultar usuário no banco")

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

    return _login_response(db_user, token)


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
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_security),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if len(new_password) < 6:
        raise HTTPException(400, "Nova senha deve ter pelo menos 6 caracteres")

    if supabase_auth_enabled() and credentials:
        try:
            update_supabase_password(credentials.credentials, new_password)
        except SupabaseAuthError as exc:
            if exc.status_code in {400, 401, 403}:
                raise HTTPException(401, "Token inválido para alterar senha no Supabase")
            raise HTTPException(exc.status_code, exc.message)
    else:
        if not verify_password(current_password, current_user.password):
            raise HTTPException(400, "Senha atual incorreta")

    current_user.password = hash_password(new_password)
    db.commit()

    return {"message": "Senha alterada com sucesso"}