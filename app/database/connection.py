from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
import logging
import os

from app.core.config import settings

logger = logging.getLogger("database")

# Usar DATABASE_URL do environment se disponível
DATABASE_URL = os.getenv("DATABASE_URL", settings.DATABASE_URL)

# Configurar engine baseado no tipo de banco
if "sqlite" in DATABASE_URL:
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
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Configurar pool_recycle para evitar 'gone away' errors"""
    if "sqlite" not in str(dbapi_connection):
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
    except Exception as e:
        logger.error(f"Erro ao acessar banco de dados: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def _ensure_postgres_schema_compatibility() -> None:
    """Aplica ajustes de compatibilidade para bancos PostgreSQL já existentes."""
    if "sqlite" in DATABASE_URL:
        return

    # Em ambientes já provisionados, create_all nao adiciona colunas novas.
    # Este bloco evita falha 500 em registro/login por colunas ausentes na tabela users.
    statements = [
        # Users table
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
        # Offers table - new detail columns
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

    with engine.begin() as conn:
        for statement in statements:
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