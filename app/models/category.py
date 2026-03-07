from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(100), unique=True, nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)

    # Hierarquia (categoria pai)
    parent_id = Column(Integer, ForeignKey("categories.id"), index=True)

    # Metadata
    icon = Column(String(200))  # URL do ícone
    color = Column(String(7))   # Hex color code
    is_active = Column(Boolean, default=True)

    # Estatísticas
    offer_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    parent = relationship("Category", remote_side=[id], backref="subcategories")
    offers = relationship("Offer", backref="category_obj")