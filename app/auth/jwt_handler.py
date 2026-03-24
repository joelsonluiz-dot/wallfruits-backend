from datetime import datetime, timedelta, timezone
from uuid import uuid4
from jose import jwt, JWTError
from fastapi import HTTPException, status
import logging

from app.core.config import settings
from app.services.supabase_auth_service import (
    SupabaseAuthError,
    get_user_from_access_token,
    supabase_auth_enabled,
)

logger = logging.getLogger("jwt")


def create_access_token(data: dict, expires_delta: int | None = None) -> str:
    """
    Cria token JWT com payload fornecido
    
    Args:
        data: Dados a codificar no token
        expires_delta: Minutos para expiração (padrão: config)
    
    Returns:
        Token JWT codificado
    """
    try:
        to_encode = data.copy()
        now = datetime.now(timezone.utc)
        
        # Definir tempo de expiração
        if expires_delta:
            expire = now + timedelta(minutes=expires_delta)
        else:
            expire = now + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        
        to_encode.update(
            {
                "exp": expire,
                "iat": now,
                "nbf": now,
                "jti": uuid4().hex,
                "token_type": "access",
            }
        )
        
        # Codificar token
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.SECRET_KEY, 
            algorithm=settings.ALGORITHM
        )
        
        logger.debug(f"Token criado para user_id: {data.get('user_id')}")
        return encoded_jwt
        
    except Exception as e:
        logger.error(f"Erro ao criar token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao gerar token de autenticação"
        )


def decode_token(token: str) -> dict:
    """
    Decodifica e valida token JWT
    
    Args:
        token: Token JWT a validar
    
    Returns:
        Payload do token decodificado
        
    Raises:
        HTTPException: Se token inválido/expirado
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        user_id: str = payload.get("user_id")
        if user_id is None:
            raise JWTError("payload sem user_id")

        token_type = payload.get("token_type")
        if token_type and token_type != "access":
            raise JWTError("token_type invalido")

        email = payload.get("email")
        if isinstance(email, str) and email.strip():
            payload["email"] = email.strip().lower()

        return payload
    except JWTError as e:
        logger.debug(f"Token local invalido, tentando Supabase: {e}")
    except Exception as e:
        logger.error(f"Erro ao decodificar token local: {e}")

    if supabase_auth_enabled():
        try:
            user_data = get_user_from_access_token(token)
            supabase_user_id = user_data.get("id")
            email = user_data.get("email")
            metadata = user_data.get("user_metadata") or {}

            if not supabase_user_id or not email:
                raise SupabaseAuthError("Token Supabase sem dados obrigatorios", status_code=401)

            return {
                "supabase_user_id": supabase_user_id,
                "email": str(email).strip().lower(),
                "role": metadata.get("role"),
                "token_type": "access",
            }
        except SupabaseAuthError as e:
            logger.warning(f"Token Supabase invalido: {e.message}")
        except Exception as e:
            logger.error(f"Erro ao validar token Supabase: {e}")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado"
    )