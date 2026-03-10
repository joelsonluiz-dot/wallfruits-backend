"""
Dispatcher centralizado para webhooks com:
- Assinatura HMAC-SHA256 para autenticidade
- Retry com backoff exponencial
- Idempotência via event_id único por disparo
"""
import hashlib
import hmac
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings

logger = logging.getLogger("webhook_dispatcher")

_DEFAULT_BACKOFF_BASE = 2.0  # segundos
_DEFAULT_BACKOFF_FACTOR = 2  # multiplicador


def _sign_payload(body: bytes, secret: str) -> str:
    """Gera assinatura HMAC-SHA256 hex do body usando o secret."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _do_send(
    *,
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout: float,
    max_retries: int,
) -> bool:
    """
    Envia POST com retry e backoff exponencial.
    Retorna True se entregue com sucesso, False caso contrário.
    """
    attempts = max_retries + 1  # 1 tentativa original + retries
    for attempt in range(attempts):
        req = Request(url=url, data=body, method="POST", headers=headers)
        try:
            with urlopen(req, timeout=timeout):
                if attempt > 0:
                    logger.info(
                        "Webhook entregue na tentativa %d/%d",
                        attempt + 1,
                        attempts,
                    )
                return True
        except HTTPError as exc:
            status = exc.code
            # Não faz retry em erros 4xx (exceto 429 Too Many Requests)
            if 400 <= status < 500 and status != 429:
                logger.warning(
                    "Webhook rejeitado com HTTP %d — sem retry", status
                )
                return False
            logger.warning(
                "Webhook HTTP %d (tentativa %d/%d)",
                status,
                attempt + 1,
                attempts,
            )
        except URLError as exc:
            logger.warning(
                "Webhook URLError: %s (tentativa %d/%d)",
                exc.reason,
                attempt + 1,
                attempts,
            )
        except Exception as exc:
            logger.warning(
                "Webhook falhou: %s (tentativa %d/%d)",
                exc,
                attempt + 1,
                attempts,
            )

        # Backoff antes da próxima tentativa (exceto na última)
        if attempt < attempts - 1:
            delay = _DEFAULT_BACKOFF_BASE * (_DEFAULT_BACKOFF_FACTOR ** attempt)
            logger.debug("Webhook retry em %.1fs", delay)
            time.sleep(delay)

    logger.error("Webhook esgotou %d tentativas para %s", attempts, url)
    return False


def dispatch_webhook(
    *,
    event_type: str,
    payload: dict,
    url: str | None = None,
    secret: str | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
    background: bool = True,
) -> str:
    """
    Dispara webhook com assinatura HMAC, idempotência e retry.

    Retorna o event_id (UUID) gerado para rastreabilidade.

    Headers enviados:
      - Content-Type: application/json
      - X-WallFruits-Event: <event_type>
      - X-WallFruits-Delivery: <event_id>  (idempotência)
      - X-WallFruits-Timestamp: <ISO 8601 UTC>
      - X-WallFruits-Signature: sha256=<hex>  (se secret configurado)
    """
    webhook_url = (url or settings.INTERMEDIATION_WEBHOOK_URL).strip()
    if not webhook_url:
        return ""

    webhook_secret = secret if secret is not None else settings.INTERMEDIATION_WEBHOOK_SECRET.strip()
    webhook_timeout = timeout if timeout is not None else max(settings.INTERMEDIATION_WEBHOOK_TIMEOUT_SECONDS, 0.1)
    webhook_retries = max_retries if max_retries is not None else settings.INTERMEDIATION_WEBHOOK_MAX_RETRIES

    event_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    envelope = {
        "event_id": event_id,
        "event": event_type,
        "occurred_at": timestamp,
        **payload,
    }

    body = json.dumps(envelope, default=str).encode("utf-8")

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "X-WallFruits-Event": event_type,
        "X-WallFruits-Delivery": event_id,
        "X-WallFruits-Timestamp": timestamp,
    }

    if webhook_secret:
        sig = _sign_payload(body, webhook_secret)
        headers["X-WallFruits-Signature"] = f"sha256={sig}"

    if background:
        thread = threading.Thread(
            target=_do_send,
            kwargs={
                "url": webhook_url,
                "body": body,
                "headers": headers,
                "timeout": webhook_timeout,
                "max_retries": webhook_retries,
            },
            daemon=True,
        )
        thread.start()
    else:
        _do_send(
            url=webhook_url,
            body=body,
            headers=headers,
            timeout=webhook_timeout,
            max_retries=webhook_retries,
        )

    return event_id
