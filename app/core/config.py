"""
Configuracoes do aplicativo WallFruits.
"""
import json
from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações da aplicação com validação"""
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:Wallfruits%402026@localhost:5432/wallfruits_db"
    DB_ECHO: bool = False
    
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
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    
    # File Upload
    UPLOAD_DIRECTORY: str = "static/uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS: list[str] = ["jpg", "jpeg", "png", "gif"]
    
    # Security
    DEBUG: bool = False
    
    class Config:
        """Configuração do Pydantic"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

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

    @field_validator("CORS_ORIGINS", "ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_string_list(cls, value: Any):
        return cls._parse_list(value)


# Cache para carregar settings uma única vez
@lru_cache()
def get_settings() -> Settings:
    """Retorna instância de Settings em cache"""
    settings = Settings()
    
    # Validações adicionais
    if settings.SECRET_KEY == "wallfruits_super_secret_key_change_in_production":
        import sys
        print("AVISO: Usando SECRET_KEY padrao! Configure uma chave segura no .env", file=sys.stderr)
    
    return settings


# Instância global
settings = get_settings()
