from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.database.connection import Base


class AgendaEvent(Base):
    __tablename__ = "agenda_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(40), nullable=False, default="task", index=True)  # reservation, task, meeting, reminder

    starts_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ends_at = Column(DateTime(timezone=True), nullable=False, index=True)

    location = Column(String(180), nullable=True)
    status = Column(String(30), nullable=False, default="scheduled", index=True)  # scheduled, completed, cancelled
    is_all_day = Column(Boolean, nullable=False, default=False)

    meta_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
