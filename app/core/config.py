"""
Configuracoes do aplicativo WallFruits.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

# Carrega .env explicitamente para scripts iniciados fora da raiz do projeto.
load_dotenv(ENV_FILE, override=False)


class Settings(BaseSettings):
    """Configurações da aplicação com validação"""
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:Wallfruits%402026@localhost:5432/wallfruits_db"
    DB_ECHO: bool = False
    STARTUP_DB_RETRIES: int = 5
    STARTUP_DB_RETRY_DELAY_SECONDS: float = 2.0
    STRICT_STARTUP: bool = False
    HEALTHCHECK_TIMEOUT_SECONDS: float = 3.0

    # Supabase
    SUPABASE_AUTH_ENABLED: bool = False
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    
    # JWT
    SECRET_KEY: str = "wallfruits_super_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # API
    API_TITLE: str = "WallFruits API"
    API_DESCRIPTION: str = "Marketplace inteligente de frutas com WebSocket, Redis e IA"
    API_VERSION: str = "2.0.0"
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1"]
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = True

    # Webhooks de dominio
    INTERMEDIATION_WEBHOOK_URL: str = ""
    INTERMEDIATION_WEBHOOK_TIMEOUT_SECONDS: float = 5.0
    INTERMEDIATION_WEBHOOK_SECRET: str = ""
    INTERMEDIATION_WEBHOOK_MAX_RETRIES: int = 3

    # E-mail (Resend)
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "WallFruits <noreply@wallfruits.com.br>"
    EMAIL_ENABLED: bool = False
    FRONTEND_URL: str = "http://localhost:3000"

    # Pagamentos (Stripe)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_BASIC: str = ""   # price_xxxx do plano básico no Stripe
    STRIPE_PRICE_PREMIUM: str = "" # price_xxxx do plano premium no Stripe
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    
    # File Upload
    UPLOAD_DIRECTORY: str = "static/uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS: list[str] = ["jpg", "jpeg", "png", "gif"]
    MAX_CONTRACT_FILE_SIZE: int = 15 * 1024 * 1024  # 15 MB
    ALLOWED_CONTRACT_EXTENSIONS: list[str] = ["pdf", "doc", "docx", "png", "jpg", "jpeg"]
    CONTRACT_MAX_RETAINED_VERSIONS: int = 5
    
    # Security
    DEBUG: bool = False
    APP_ENV: str = "development"

    # Rate limit (camada de proteção básica por IP)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_MAX_REQUESTS: int = 180
    RATE_LIMIT_SENSITIVE_MAX_REQUESTS: int = 40
    RATE_LIMIT_TRUST_PROXY_HEADERS: bool = True
    
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @staticmethod
    def _parse_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []

            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass

            return [item.strip() for item in raw.split(",") if item.strip()]

        return []

    @field_validator("CORS_ORIGINS", "ALLOWED_HOSTS", "ALLOWED_CONTRACT_EXTENSIONS", mode="before")
    @classmethod
    def parse_string_list(cls, value: Any):
        return cls._parse_list(value)


# Cache para carregar settings uma única vez
@lru_cache()
def get_settings() -> Settings:
    """Retorna instância de Settings em cache"""
    settings = Settings()

    if not settings.DATABASE_URL.strip():
        raise RuntimeError("DATABASE_URL não configurada")

    if settings.STARTUP_DB_RETRIES < 1:
        raise RuntimeError("STARTUP_DB_RETRIES deve ser >= 1")

    if settings.STARTUP_DB_RETRY_DELAY_SECONDS < 0:
        raise RuntimeError("STARTUP_DB_RETRY_DELAY_SECONDS deve ser >= 0")

    if settings.HEALTHCHECK_TIMEOUT_SECONDS <= 0:
        raise RuntimeError("HEALTHCHECK_TIMEOUT_SECONDS deve ser > 0")

    if settings.RATE_LIMIT_WINDOW_SECONDS <= 0:
        raise RuntimeError("RATE_LIMIT_WINDOW_SECONDS deve ser > 0")

    if settings.RATE_LIMIT_MAX_REQUESTS < 1:
        raise RuntimeError("RATE_LIMIT_MAX_REQUESTS deve ser >= 1")

    if settings.RATE_LIMIT_SENSITIVE_MAX_REQUESTS < 1:
        raise RuntimeError("RATE_LIMIT_SENSITIVE_MAX_REQUESTS deve ser >= 1")

    if settings.INTERMEDIATION_WEBHOOK_TIMEOUT_SECONDS <= 0:
        raise RuntimeError("INTERMEDIATION_WEBHOOK_TIMEOUT_SECONDS deve ser > 0")

    if settings.INTERMEDIATION_WEBHOOK_MAX_RETRIES < 0:
        raise RuntimeError("INTERMEDIATION_WEBHOOK_MAX_RETRIES deve ser >= 0")

    if settings.MAX_CONTRACT_FILE_SIZE <= 0:
        raise RuntimeError("MAX_CONTRACT_FILE_SIZE deve ser > 0")

    if settings.CONTRACT_MAX_RETAINED_VERSIONS < 1:
        raise RuntimeError("CONTRACT_MAX_RETAINED_VERSIONS deve ser >= 1")

    if not settings.ALLOWED_CONTRACT_EXTENSIONS:
        raise RuntimeError("ALLOWED_CONTRACT_EXTENSIONS nao pode ser vazio")

    if settings.SUPABASE_AUTH_ENABLED:
        if not settings.SUPABASE_URL.strip():
            raise RuntimeError("Supabase Auth habilitado, mas falta SUPABASE_URL")
        if not settings.SUPABASE_ANON_KEY.strip():
            import sys
            print(
                "AVISO: SUPABASE_ANON_KEY ausente; login/senha via Supabase fica desativado, "
                "mas OAuth pode funcionar.",
                file=sys.stderr,
            )

    env_lower = settings.APP_ENV.strip().lower()
    if env_lower in {"prod", "production", "staging"} and settings.SECRET_KEY == "wallfruits_super_secret_key_change_in_production":
        raise RuntimeError("SECRET_KEY padrão não pode ser usada em produção")
    
    # Validações adicionais
    if settings.SECRET_KEY == "wallfruits_super_secret_key_change_in_production":
        import sys
        print("AVISO: Usando SECRET_KEY padrao! Configure uma chave segura no .env", file=sys.stderr)
    
    return settings


# Instância global
settings = get_settings()
