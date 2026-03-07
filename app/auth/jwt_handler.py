from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException, status
import logging

from app.core.config import settings

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
        
        # Definir tempo de expiração
        if expires_delta:
            expire = datetime.now(timezone.utc) + timedelta(minutes=expires_delta)
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        
        to_encode.update({"exp": expire})
        
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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido ou expirado"
            )
        
        return payload
        
    except JWTError as e:
        logger.warning(f"Token invalido: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado"
        )
    except Exception as e:
        logger.error(f"Erro ao decodificar token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Erro ao validar token"
        )