import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, unquote, urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger("supabase_storage")


class SupabaseStorageError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def supabase_storage_enabled() -> bool:
    return bool(settings.SUPABASE_STORAGE_ENABLED)


def _normalized_base_url(value: str) -> str:
    return (value or "").strip().rstrip("/")


def _storage_base_url() -> str:
    base_url = _normalized_base_url(settings.SUPABASE_URL)
    if not base_url:
        raise SupabaseStorageError("SUPABASE_URL nao configurada", status_code=500)
    return f"{base_url}/storage/v1"


def _service_role_key() -> str:
    api_key = (settings.SUPABASE_SERVICE_ROLE_KEY or "").strip()
    if not api_key:
        raise SupabaseStorageError("SUPABASE_SERVICE_ROLE_KEY nao configurada", status_code=500)
    return api_key


def storage_bucket() -> str:
    bucket = (settings.SUPABASE_STORAGE_BUCKET or "").strip()
    if not bucket:
        raise SupabaseStorageError("SUPABASE_STORAGE_BUCKET nao configurada", status_code=500)
    if "/" in bucket:
        raise SupabaseStorageError("SUPABASE_STORAGE_BUCKET invalida", status_code=500)
    return bucket


def build_public_object_url(*, bucket: str, object_path: str) -> str:
    base_public = _normalized_base_url(settings.SUPABASE_STORAGE_PUBLIC_BASE_URL) or _normalized_base_url(
        settings.SUPABASE_URL
    )
    if not base_public:
        raise SupabaseStorageError("SUPABASE_URL nao configurada", status_code=500)

    normalized_object_path = (object_path or "").lstrip("/")
    encoded_path = quote(normalized_object_path, safe="/")
    return f"{base_public}/storage/v1/object/public/{bucket}/{encoded_path}"


def try_parse_public_object_url(url: str) -> tuple[str, str] | None:
    raw = (url or "").strip()
    if not raw:
        return None

    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return None

    marker = "/storage/v1/object/public/"
    path = parsed.path or ""
    idx = path.find(marker)
    if idx < 0:
        return None

    rest = path[idx + len(marker) :].lstrip("/")
    if not rest:
        return None

    parts = rest.split("/", 1)
    bucket = parts[0]
    object_path = parts[1] if len(parts) > 1 else ""
    return bucket, unquote(object_path)


@dataclass(frozen=True)
class UploadedObject:
    filename: str
    object_path: str
    public_url: str


async def upload_public_object(*, bucket: str, object_path: str, content: bytes, content_type: str | None) -> None:
    if not supabase_storage_enabled():
        raise SupabaseStorageError("Supabase Storage nao esta habilitado", status_code=400)

    normalized_object_path = (object_path or "").lstrip("/")
    if not normalized_object_path:
        raise SupabaseStorageError("Caminho do objeto vazio", status_code=400)

    url = f"{_storage_base_url()}/object/{bucket}/{quote(normalized_object_path, safe='/')}"
    api_key = _service_role_key()

    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": content_type or "application/octet-stream",
        # Para objetos versionados por UUID, upsert nao e necessario.
        "x-upsert": "false",
    }

    timeout = float(settings.SUPABASE_STORAGE_TIMEOUT_SECONDS)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, content=content, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raw_error = (exc.response.text or "").strip()
        logger.warning("Supabase Storage upload HTTPError %s: %s", status, raw_error[:500])
        raise SupabaseStorageError(
            f"Erro ao enviar arquivo para o Storage (HTTP {status})",
            status_code=502 if status >= 500 else status,
        )
    except httpx.RequestError as exc:
        logger.error("Falha de rede ao acessar Supabase Storage: %s", exc)
        raise SupabaseStorageError("Falha de conexao com Supabase Storage", status_code=503)


async def delete_object(*, bucket: str, object_path: str) -> None:
    if not supabase_storage_enabled():
        raise SupabaseStorageError("Supabase Storage nao esta habilitado", status_code=400)

    normalized_object_path = (object_path or "").lstrip("/")
    if not normalized_object_path:
        raise SupabaseStorageError("Caminho do objeto vazio", status_code=400)

    url = f"{_storage_base_url()}/object/{bucket}/{quote(normalized_object_path, safe='/')}"
    api_key = _service_role_key()

    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
    }

    timeout = float(settings.SUPABASE_STORAGE_TIMEOUT_SECONDS)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.delete(url, headers=headers)
            # 404 e ok (objeto ja nao existe)
            if response.status_code == 404:
                return
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raw_error = (exc.response.text or "").strip()
        logger.warning("Supabase Storage delete HTTPError %s: %s", status, raw_error[:500])
        raise SupabaseStorageError(
            f"Erro ao deletar arquivo no Storage (HTTP {status})",
            status_code=502 if status >= 500 else status,
        )
    except httpx.RequestError as exc:
        logger.error("Falha de rede ao acessar Supabase Storage: %s", exc)
        raise SupabaseStorageError("Falha de conexao com Supabase Storage", status_code=503)


def safe_json(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    return {}
