from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(160), nullable=False, index=True)
    descricao = Column(Text, nullable=False)
    preco = Column(String(40), nullable=False)
    local = Column(String(140), nullable=False)
    imagem = Column(String(700), nullable=False)
    ficha_tecnica = Column(JSON, default={})
    is_active = Column(Boolean, default=True, index=True)

    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    created_by = relationship("User", backref="services_created")