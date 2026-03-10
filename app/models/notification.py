from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    notification_type = Column(String(50), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)

    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(80), nullable=True)

    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", foreign_keys=[user_id])
    actor = relationship("User", foreign_keys=[actor_user_id])
