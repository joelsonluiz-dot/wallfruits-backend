from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class BuyerClientPolicy(Base):
    __tablename__ = "buyer_client_policies"
    __table_args__ = (UniqueConstraint("user_id", name="uq_buyer_client_policy_user"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    max_clients = Column(Integer, default=20, nullable=False)
    slot_price = Column(Numeric(10, 2), default=19.90, nullable=False)
    slots_purchased = Column(Integer, default=0, nullable=False)
    slots_used = Column(Integer, default=0, nullable=False)

    compliance_status = Column(String(20), default="ok", nullable=False, index=True)
    purchase_restricted = Column(Boolean, default=False, nullable=False, index=True)
    restriction_reason = Column(String(500), nullable=True)
    restricted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", backref="buyer_client_policy", foreign_keys=[user_id])


class BuyerClient(Base):
    __tablename__ = "buyer_clients"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    name = Column(String(160), nullable=False)
    company_name = Column(String(200), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(30), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)

    management_scope = Column(String(30), default="joint", nullable=False, index=True)
    demand_summary = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", backref="buyer_clients", foreign_keys=[owner_user_id])


class BuyerClientSlotPurchase(Base):
    __tablename__ = "buyer_client_slot_purchases"
    __table_args__ = (
        UniqueConstraint("checkout_session_id", name="uq_slot_purchase_checkout_session"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)

    status = Column(String(20), default="pending", nullable=False, index=True)
    checkout_session_id = Column(String(120), nullable=True, index=True)
    stripe_payment_intent_id = Column(String(120), nullable=True, index=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", backref="buyer_client_slot_purchases", foreign_keys=[user_id])
