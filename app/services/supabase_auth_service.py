import json
import logging
import time
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jose import jwk, jwt
from jose.utils import base64url_decode

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
    )


def supabase_password_auth_enabled() -> bool:
    """Login/senha no Supabase exige anon key configurada."""
    return bool(
        supabase_auth_enabled()
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
    }

    if api_key:
        headers["apikey"] = api_key

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
    if not supabase_password_auth_enabled():
        raise SupabaseAuthError("Supabase Auth nao esta habilitado", status_code=400)

    return _request(
        "POST",
        "/token?grant_type=password",
        body={"email": email, "password": password},
    )


def get_oauth_authorize_url(*, provider: str, redirect_to: str) -> str:
    """Monta URL de authorize do Supabase Auth para provedores OAuth."""
    if not supabase_auth_enabled():
        raise SupabaseAuthError("Supabase Auth nao esta habilitado", status_code=400)

    normalized_provider = (provider or "").strip().lower()
    if normalized_provider not in {"google"}:
        raise SupabaseAuthError("Provedor OAuth nao suportado", status_code=400)

    base_url = settings.SUPABASE_URL.strip().rstrip("/")
    query = urlencode(
        {
            "provider": normalized_provider,
            "redirect_to": redirect_to,
        }
    )
    return f"{base_url}/auth/v1/authorize?{query}"


def create_user_with_password(
    *,
    email: str,
    password: str,
    user_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not supabase_auth_enabled():
        raise SupabaseAuthError("Supabase Auth nao esta habilitado", status_code=400)

    if not settings.SUPABASE_SERVICE_ROLE_KEY.strip() and not settings.SUPABASE_ANON_KEY.strip():
        raise SupabaseAuthError(
            "Supabase Auth sem chave API configurada (anon/service role)",
            status_code=400,
        )

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

    try:
        return _request("GET", "/user", bearer_token=access_token)
    except SupabaseAuthError as primary_exc:
        # Fallback seguro: valida assinatura JWT via JWKS publico do projeto.
        claims = _decode_and_verify_token_claims(access_token)
        sub = claims.get("sub")
        email = claims.get("email")

        if not sub or not email:
            raise primary_exc

        user_metadata = claims.get("user_metadata")
        if not isinstance(user_metadata, dict):
            user_metadata = {}

        return {
            "id": str(sub),
            "email": str(email),
            "user_metadata": user_metadata,
        }


def _fetch_jwks() -> dict[str, Any]:
    base_url = settings.SUPABASE_URL.strip().rstrip("/")
    if not base_url:
        raise SupabaseAuthError("SUPABASE_URL nao configurada", status_code=500)

    request = Request(
        url=f"{base_url}/auth/v1/.well-known/jwks.json",
        method="GET",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            payload = _json_loads(raw)
            if not isinstance(payload.get("keys"), list):
                raise SupabaseAuthError("JWKS inválido do Supabase", status_code=502)
            return payload
    except HTTPError as exc:
        raise SupabaseAuthError(f"Falha ao obter JWKS do Supabase ({exc.code})", status_code=502)
    except URLError as exc:
        raise SupabaseAuthError(f"Falha de rede ao obter JWKS: {exc.reason}", status_code=503)


def _decode_and_verify_token_claims(access_token: str) -> dict[str, Any]:
    """Valida assinatura/exp/iss de JWT do Supabase usando JWKS público."""
    try:
        unverified_header = jwt.get_unverified_header(access_token)
        kid = unverified_header.get("kid")
        if not kid:
            raise SupabaseAuthError("Token sem kid", status_code=401)

        jwks_payload = _fetch_jwks()
        jwk_data = next((k for k in jwks_payload["keys"] if k.get("kid") == kid), None)
        if not jwk_data:
            raise SupabaseAuthError("Chave pública do token não encontrada", status_code=401)

        key = jwk.construct(jwk_data)
        message, encoded_sig = access_token.rsplit(".", 1)
        decoded_sig = base64url_decode(encoded_sig.encode("utf-8"))
        if not key.verify(message.encode("utf-8"), decoded_sig):
            raise SupabaseAuthError("Assinatura JWT inválida", status_code=401)

        claims = jwt.get_unverified_claims(access_token)
        exp = claims.get("exp")
        if not isinstance(exp, (int, float)) or exp < time.time():
            raise SupabaseAuthError("Token expirado", status_code=401)

        base_url = settings.SUPABASE_URL.strip().rstrip("/")
        expected_iss = f"{base_url}/auth/v1"
        iss = claims.get("iss")
        if isinstance(iss, str) and iss and iss != expected_iss:
            raise SupabaseAuthError("Issuer inválido no token", status_code=401)

        return claims
    except SupabaseAuthError:
        raise
    except Exception as exc:
        raise SupabaseAuthError(f"Falha ao validar token Supabase: {exc}", status_code=401)


def update_password(access_token: str, new_password: str) -> dict[str, Any]:
    if not supabase_auth_enabled():
        raise SupabaseAuthError("Supabase Auth nao esta habilitado", status_code=400)

    return _request(
        "PUT",
        "/user",
        body={"password": new_password},
        bearer_token=access_token,
    )


def delete_user_by_id(user_id: str) -> dict[str, Any]:
    if not supabase_auth_enabled():
        raise SupabaseAuthError("Supabase Auth nao esta habilitado", status_code=400)

    if not settings.SUPABASE_SERVICE_ROLE_KEY.strip():
        raise SupabaseAuthError(
            "SUPABASE_SERVICE_ROLE_KEY nao configurada para remover usuario",
            status_code=500,
        )

    return _request(
        "DELETE",
        f"/admin/users/{user_id}",
        use_service_role=True,
    )
