from enum import Enum


class ProfileType(str, Enum):
    VISITOR = "visitor"
    PRODUCER = "producer"
    BROKER = "broker"
    COMPANY = "company"


class ValidationStatus(str, Enum):
    PENDING = "pending_validation"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class SubscriptionPlanType(str, Enum):
    BASIC = "basic"
    PRO = "pro"
    PREMIUM = "premium"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    EXPIRED = "expired"


class OfferVisibility(str, Enum):
    PUBLIC = "public"
    PREMIUM_ONLY = "premium_only"


class OfferLifecycleStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    SUSPENDED = "suspended"


class NegotiationStatus(str, Enum):
    OPEN = "open"
    COUNTERED = "countered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELED = "canceled"
    COMPLETED = "completed"


class IntermediationStatus(str, Enum):
    EM_VALIDACAO = "em_validacao"
    VALIDADA = "validada"
    REJEITADA = "rejeitada"


class WalletTransactionType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class WalletTransactionSource(str, Enum):
    NEGOTIATION = "negotiation"
    BONUS = "bonus"
    REFUND = "refund"
    RAFFLE = "raffle"


class ReportStatus(str, Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class RaffleStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    DRAWN = "drawn"


class PointSource(str, Enum):
    NEGOTIATION_COMPLETED = "negotiation_completed"
    REVIEW_GIVEN = "review_given"
    REVIEW_RECEIVED = "review_received"
    OFFER_PUBLISHED = "offer_published"
    FIRST_SALE = "first_sale"
    RAFFLE_TICKET = "raffle_ticket"
    BONUS = "bonus"
    ADMIN_ADJUSTMENT = "admin_adjustment"


class ContestationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
