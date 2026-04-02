from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from urllib.parse import unquote

from app.database.connection import get_db
from app.models.user import User
from app.auth.jwt_handler import decode_token

security = HTTPBearer(auto_error=False)
AUTH_COOKIE_NAME = "wf_auth_token"


def _resolve_token_from_request(
    credentials: Optional[HTTPAuthorizationCredentials],
    request: Request | None,
) -> str | None:
    if credentials and credentials.credentials:
        return str(credentials.credentials).strip() or None

    cookie_token = str((request.cookies.get(AUTH_COOKIE_NAME) if request else "") or "").strip()
    if cookie_token:
        return unquote(cookie_token)

    return None


def _normalize_email(email: str | None) -> str | None:
    if not isinstance(email, str):
        return None
    normalized = email.strip().lower()
    return normalized or None


def _resolve_user_from_payload(db: Session, payload: dict) -> Optional[User]:
    user_id = payload.get("user_id")
    if user_id:
        return db.query(User).filter(User.id == user_id).first()

    supabase_user_id = payload.get("supabase_user_id")
    if supabase_user_id:
        user = db.query(User).filter(User.supabase_user_id == supabase_user_id).first()
        if user:
            return user

    email = payload.get("email")
    normalized_email = _normalize_email(email)
    if normalized_email:
        return db.query(User).filter(User.email == normalized_email).first()

    return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    request: Request = None,
    db: Session = Depends(get_db)
) -> User:
    """
    Middleware para obter usuário atual do token JWT
    """
    token = _resolve_token_from_request(credentials, request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação necessário"
        )

    try:
        payload = decode_token(token)
        user = _resolve_user_from_payload(db, payload)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Conta desativada"
            )

        return user

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado"
        )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    request: Request = None,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Middleware opcional para obter usuário atual do token JWT
    """
    token = _resolve_token_from_request(credentials, request)
    if not token:
        return None

    try:
        payload = decode_token(token)
        user = _resolve_user_from_payload(db, payload)

        if not user or not user.is_active:
            return None

        return user
    except Exception:
        return None


def require_role(required_role: str):
    """
    Decorator para verificar roles do usuário
    """
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in [required_role, "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Role '{required_role}' necessário"
            )
        return current_user
    return role_checker


def require_producer_or_admin(current_user: User = Depends(get_current_user)):
    """
    Verifica se usuário é produtor ou admin
    """
    if current_user.role not in ["producer", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas produtores podem criar ofertas"
        )
    return current_user


async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Autenticação opcional - retorna usuário se token válido, None caso contrário
    """
    if not credentials:
        return None

    try:
        payload = decode_token(credentials.credentials)
        user = _resolve_user_from_payload(db, payload)
        if user and user.is_active:
            return user

    except Exception:
        pass

    return None


def get_user_from_token(token: str, db: Session) -> User:
    """Resolve um usuário ativo a partir de um token JWT bruto."""
    payload = decode_token(token)
    user = _resolve_user_from_payload(db, payload)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta desativada"
        )

    return user