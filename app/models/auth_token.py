"""Token de uso único para reset de senha e verificação de e-mail."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database.connection import Base


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(128), unique=True, nullable=False, index=True)
    token_type = Column(String(20), nullable=False)   # password_reset | email_verify
    used = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    @classmethod
    def new_reset(cls, user_id: int, hours: int = 1) -> "AuthToken":
        return cls(
            user_id=user_id,
            token=uuid.uuid4().hex + uuid.uuid4().hex,  # 64 chars hex
            token_type="password_reset",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=hours),
        )

    @classmethod
    def new_verify(cls, user_id: int, hours: int = 24) -> "AuthToken":
        return cls(
            user_id=user_id,
            token=uuid.uuid4().hex + uuid.uuid4().hex,
            token_type="email_verify",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=hours),
        )

    def is_valid(self) -> bool:
        return (
            not self.used
            and datetime.now(timezone.utc) < self.expires_at.replace(tzinfo=timezone.utc)
        )
