import logging
import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings

logger = logging.getLogger("database")

DATABASE_URL = (os.getenv("DATABASE_URL") or settings.DATABASE_URL or "").strip()

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não configurada. Defina no ambiente ou no arquivo .env")

IS_SQLITE = DATABASE_URL.startswith("sqlite")

# Configurar engine baseado no tipo de banco
if IS_SQLITE:
    # Configuração para SQLite
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.DB_ECHO
    )
else:
    # Configuração para PostgreSQL
    engine = create_engine(
        DATABASE_URL,
        echo=settings.DB_ECHO,
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 10,
            "options": "-c timezone=UTC"
        }
    )

# Tratamento de reconexão automática
@event.listens_for(engine, "connect")
def set_connection_defaults(dbapi_connection, connection_record):
    """Configurar pool_recycle para evitar 'gone away' errors"""
    del connection_record  # assinatura exigida pelo SQLAlchemy

    if not IS_SQLITE:
        cursor = dbapi_connection.cursor()
        cursor.execute("SET client_encoding='utf8'")
        cursor.close()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

Base = declarative_base()


def get_db():
    """Dependency para obter sessão do banco de dados"""
    db = SessionLocal()
    try:
        yield db
    except Exception as exc:
        logger.error(f"Erro ao acessar banco de dados: {exc}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


def _table_exists(conn, table_name: str) -> bool:
    if IS_SQLITE:
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).scalar()
        return result is not None

    result = conn.execute(
        text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    ).scalar()
    return result is not None


def _ensure_users_schema_compatibility() -> None:
    """Garante colunas necessárias para autenticação na tabela users."""
    if IS_SQLITE:
        sqlite_statements = {
            "role": "ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'buyer'",
            "phone": "ALTER TABLE users ADD COLUMN phone VARCHAR(20)",
            "location": "ALTER TABLE users ADD COLUMN location VARCHAR(150)",
            "bio": "ALTER TABLE users ADD COLUMN bio TEXT",
            "profile_image": "ALTER TABLE users ADD COLUMN profile_image VARCHAR(500)",
            "is_active": "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1",
            "is_verified": "ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 0",
            "rating": "ALTER TABLE users ADD COLUMN rating INTEGER DEFAULT 0",
            "total_reviews": "ALTER TABLE users ADD COLUMN total_reviews INTEGER DEFAULT 0",
            "created_at": "ALTER TABLE users ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "ALTER TABLE users ADD COLUMN updated_at DATETIME",
        }

        with engine.begin() as conn:
            if not _table_exists(conn, "users"):
                return

            existing_columns = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(users)"))
            }

            for column_name, statement in sqlite_statements.items():
                if column_name not in existing_columns:
                    conn.execute(text(statement))

        return

    user_statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'buyer'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS location VARCHAR(150)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_image VARCHAR(500)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS rating INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS total_reviews INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
    ]

    with engine.begin() as conn:
        if not _table_exists(conn, "users"):
            return

        for statement in user_statements:
            conn.execute(text(statement))


def ensure_auth_schema_compatibility() -> None:
    """Compatibilidade mínima necessária para fluxo de login/registro."""
    _ensure_users_schema_compatibility()


def _ensure_postgres_schema_compatibility() -> None:
    """Aplica ajustes de compatibilidade para bancos já existentes."""
    if IS_SQLITE:
        _ensure_users_schema_compatibility()
        return

    offer_statements = [
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS variety VARCHAR(100)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS quality_class VARCHAR(50)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS certification VARCHAR(100)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS box_weight_kg NUMERIC(10,2)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS price_per_kg NUMERIC(10,2)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS price_min_kg NUMERIC(10,2)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS price_avg_kg NUMERIC(10,2)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS price_max_kg NUMERIC(10,2)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS available_quantity NUMERIC(10,2)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS origin VARCHAR(100)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS target_market VARCHAR(100)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS maturation VARCHAR(50)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS shelf_life VARCHAR(50)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS harvest_date_actual DATE",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS reservation_start DATE",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS reservation_end DATE",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS property_name VARCHAR(200)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS property_address VARCHAR(300)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS ad_duration_days INTEGER DEFAULT 30",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS min_boxes_to_negotiate INTEGER DEFAULT 1",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS platform_fee NUMERIC(10,4) DEFAULT 0.03",
    ]

    _ensure_users_schema_compatibility()

    with engine.begin() as conn:
        if not _table_exists(conn, "offers"):
            return

        for statement in offer_statements:
            conn.execute(text(statement))


def init_db():
    """Inicializar o banco de dados criando todas as tabelas"""
    try:
        Base.metadata.create_all(bind=engine)
        _ensure_postgres_schema_compatibility()
        logger.info("Banco de dados inicializado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco de dados: {e}")
        raise