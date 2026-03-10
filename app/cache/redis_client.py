import redis
import json
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("redis_cache")


_redis_client: redis.Redis | None = None


def _create_client() -> redis.Redis:
    timeout = max(settings.HEALTHCHECK_TIMEOUT_SECONDS, 0.1)
    return redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=timeout,
        socket_timeout=timeout,
        retry_on_timeout=True,
    )


def get_redis_client() -> redis.Redis | None:
    global _redis_client

    if not settings.REDIS_ENABLED:
        return None

    if _redis_client is None:
        try:
            _redis_client = _create_client()
        except Exception as exc:
            logger.error("Erro ao criar cliente Redis: %s", exc)
            _redis_client = None
            return None

    try:
        _redis_client.ping()
        return _redis_client
    except Exception as exc:
        logger.warning("Cliente Redis desconectado, recriando: %s", exc)
        try:
            _redis_client = _create_client()
            _redis_client.ping()
            return _redis_client
        except Exception as reconnect_exc:
            logger.error("Falha ao reconectar Redis: %s", reconnect_exc)
            _redis_client = None
            return None


def check_redis_connection() -> tuple[bool, str]:
    client = get_redis_client()
    if client is None:
        if settings.REDIS_ENABLED:
            return False, "Redis indisponível"
        return True, "desabilitado"

    try:
        client.ping()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


try:
    if not settings.REDIS_ENABLED:
        logger.warning("Redis desabilitado por configuracao (REDIS_ENABLED=false)")
        r = None
    else:
        r = get_redis_client()
        if r:
            logger.info("Redis conectado com sucesso")
        else:
            logger.warning("Redis habilitado, mas indisponível")
except Exception as e:
    logger.error(f"Erro ao conectar no Redis: {e}")
    r = None


def set_cache(key: str, value: str, expire: Optional[int] = None):
    """
    Salva valor no Redis
    """
    client = get_redis_client()
    if not client:
        return

    try:
        if expire:
            client.setex(key, expire, value)
        else:
            client.set(key, value)
    except Exception as e:
        logger.error(f"Erro ao salvar cache: {e}")


def get_cache(key: str) -> Optional[str]:
    """
    Recupera valor do Redis
    """
    client = get_redis_client()
    if not client:
        return None

    try:
        return client.get(key)
    except Exception as e:
        logger.error(f"Erro ao buscar cache: {e}")
        return None


def delete_cache(key: str):
    """
    Remove chave do Redis
    """
    client = get_redis_client()
    if not client:
        return

    try:
        client.delete(key)
    except Exception as e:
        logger.error(f"Erro ao deletar cache: {e}")