from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    supabase_user_id = Column(String(64), unique=True, index=True, nullable=True)

    # Novos campos para marketplace
    role = Column(String(50), default="buyer", nullable=False)  # buyer, producer, admin (legado)
    platform_role = Column(
        String(30),
        default="none",
        nullable=False,
        index=True,
    )  # none, staff_support, staff_ops, staff_admin
    account_role = Column(
        String(30),
        default="account_owner",
        nullable=False,
        index=True,
    )  # account_viewer, account_analyst, account_manager, account_owner
    account_scope_id = Column(String(64), nullable=True, index=True)  # tenant/logical account scope
    phone = Column(String(20))
    location = Column(String(150))
    bio = Column(Text)
    profile_image = Column(String(500))  # URL da imagem de perfil

    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)

    rating = Column(Integer, default=0)  # Rating de 0-5
    total_reviews = Column(Integer, default=0)

    # Preferencias de pagamento (usadas em checkout e upgrades de assinatura)
    payment_billing_name = Column(String(150))
    payment_billing_phone = Column(String(30))
    payment_billing_address_line1 = Column(String(255))
    payment_billing_address_line2 = Column(String(255))
    payment_billing_city = Column(String(120))
    payment_billing_state = Column(String(10))
    payment_billing_zip = Column(String(20))
    payment_billing_country = Column(String(60), default="BR")

    payment_pix_key_type = Column(String(20))
    payment_pix_key = Column(String(160))
    payment_pix_holder_name = Column(String(150))

    payment_card_holder_name = Column(String(150))
    payment_card_last4 = Column(String(4))
    payment_card_brand = Column(String(30))
    payment_card_exp_month = Column(Integer)
    payment_card_exp_year = Column(Integer)

    payment_default_method = Column(String(20), default="card")
    payment_use_for_subscriptions = Column(Boolean, default=True)
    payment_updated_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))

    # Relacionamentos
    offers = relationship("Offer", back_populates="owner", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="buyer", cascade="all, delete-orphan")
    reviews = relationship(
        "Review",
        foreign_keys="Review.reviewer_id",
        back_populates="reviewer",
        cascade="all, delete-orphan"
    )
    received_reviews = relationship(
        "Review",
        foreign_keys="Review.reviewed_user_id",
        back_populates="reviewed_user"
    )
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    profile = relationship(
        "Profile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="Profile.user_id",
    )
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    wallet = relationship("Wallet", back_populates="user", uselist=False, cascade="all, delete-orphan")