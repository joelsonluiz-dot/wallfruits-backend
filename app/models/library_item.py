from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class LibraryItem(Base):
    __tablename__ = "library_items"
    __table_args__ = (
        UniqueConstraint("user_id", "book_id", name="uq_library_items_user_book"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    book_id = Column(String(180), nullable=False, index=True)

    title = Column(String(300), nullable=False)
    author = Column(String(180), nullable=True)
    category = Column(String(120), nullable=True)
    read_time = Column(String(40), nullable=True)
    cover = Column(String(700), nullable=True)
    text = Column(Text, nullable=True)

    is_favorite = Column(Boolean, default=False, index=True)
    is_offline = Column(Boolean, default=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", backref="library_items")