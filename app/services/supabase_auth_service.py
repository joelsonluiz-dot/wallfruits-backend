import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings

logger = logging.getLogger("supabase_auth")


class SupabaseAuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def supabase_auth_enabled() -> bool:
    return bool(
        settings.SUPABASE_AUTH_ENABLED
        and settings.SUPABASE_URL.strip()
        and settings.SUPABASE_ANON_KEY.strip()
    )


def _json_loads(raw: str) -> dict[str, Any]:
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    return {}


def _extract_error_message(payload: dict[str, Any], fallback: str) -> str:
    for key in ("msg", "error_description", "error", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value

    nested_error = payload.get("error")
    if isinstance(nested_error, dict):
        nested_message = nested_error.get("message")
        if isinstance(nested_message, str) and nested_message.strip():
            return nested_message

    return fallback


def _build_headers(
    *,
    use_service_role: bool,
    bearer_token: str | None,
) -> dict[str, str]:
    if use_service_role:
        api_key = settings.SUPABASE_SERVICE_ROLE_KEY.strip()
        if not api_key:
            raise SupabaseAuthError(
                "SUPABASE_SERVICE_ROLE_KEY nao configurada para operacao admin",
                status_code=500,
            )
    else:
        api_key = settings.SUPABASE_ANON_KEY.strip()

    headers = {
        "Content-Type": "application/json",
        "apikey": api_key,
    }

    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    elif use_service_role:
        headers["Authorization"] = f"Bearer {api_key}"

    return headers


def _request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    use_service_role: bool = False,
    bearer_token: str | None = None,
) -> dict[str, Any]:
    base_url = settings.SUPABASE_URL.strip().rstrip("/")
    if not base_url:
        raise SupabaseAuthError("SUPABASE_URL nao configurada", status_code=500)

    url = f"{base_url}/auth/v1{path}"
    payload_bytes = json.dumps(body).encode("utf-8") if body is not None else None

    request = Request(
        url=url,
        data=payload_bytes,
        method=method,
        headers=_build_headers(
            use_service_role=use_service_role,
            bearer_token=bearer_token,
        ),
    )

    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return _json_loads(raw)
    except HTTPError as exc:
        raw_error = exc.read().decode("utf-8") if exc.fp else ""
        payload = _json_loads(raw_error)
        message = _extract_error_message(payload, f"Erro Supabase ({exc.code})")
        logger.warning("Supabase auth HTTPError %s: %s", exc.code, message)
        raise SupabaseAuthError(message, status_code=exc.code)
    except URLError as exc:
        logger.error("Falha de rede ao acessar Supabase Auth: %s", exc.reason)
        raise SupabaseAuthError("Falha de conexao com Supabase Auth", status_code=503)


def sign_in_with_password(email: str, password: str) -> dict[str, Any]:
    if not supabase_auth_enabled():
        raise SupabaseAuthError("Supabase Auth nao esta habilitado", status_code=400)

    return _request(
        "POST",
        "/token?grant_type=password",
        body={"email": email, "password": password},
    )


def create_user_with_password(
    *,
    email: str,
    password: str,
    user_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not supabase_auth_enabled():
        raise SupabaseAuthError("Supabase Auth nao esta habilitado", status_code=400)

    if settings.SUPABASE_SERVICE_ROLE_KEY.strip():
        payload: dict[str, Any] = {
            "email": email,
            "password": password,
            "email_confirm": True,
        }
        if user_metadata:
            payload["user_metadata"] = user_metadata

        response = _request(
            "POST",
            "/admin/users",
            body=payload,
            use_service_role=True,
        )
        return response.get("user", response)

    payload = {
        "email": email,
        "password": password,
    }
    if user_metadata:
        payload["data"] = user_metadata

    response = _request("POST", "/signup", body=payload)
    return response.get("user", response)


def get_user_from_access_token(access_token: str) -> dict[str, Any]:
    if not supabase_auth_enabled():
        raise SupabaseAuthError("Supabase Auth nao esta habilitado", status_code=400)

    return _request("GET", "/user", bearer_token=access_token)


def update_password(access_token: str, new_password: str) -> dict[str, Any]:
    if not supabase_auth_enabled():
        raise SupabaseAuthError("Supabase Auth nao esta habilitado", status_code=400)

    return _request(
        "PUT",
        "/user",
        body={"password": new_password},
        bearer_token=access_token,
    )
