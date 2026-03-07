import redis
import json
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("redis_cache")


try:
    if not settings.REDIS_ENABLED:
        logger.warning("Redis desabilitado por configuracao (REDIS_ENABLED=false)")
        r = None
    else:
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.ping()
        logger.info("Redis conectado com sucesso")
except Exception as e:
    logger.error(f"Erro ao conectar no Redis: {e}")
    r = None


def set_cache(key: str, value: str, expire: Optional[int] = None):
    """
    Salva valor no Redis
    """
    if not r:
        return

    try:
        if expire:
            r.setex(key, expire, value)
        else:
            r.set(key, value)
    except Exception as e:
        logger.error(f"Erro ao salvar cache: {e}")


def get_cache(key: str) -> Optional[str]:
    """
    Recupera valor do Redis
    """
    if not r:
        return None

    try:
        return r.get(key)
    except Exception as e:
        logger.error(f"Erro ao buscar cache: {e}")
        return None


def delete_cache(key: str):
    """
    Remove chave do Redis
    """
    if not r:
        return

    try:
        r.delete(key)
    except Exception as e:
        logger.error(f"Erro ao deletar cache: {e}")