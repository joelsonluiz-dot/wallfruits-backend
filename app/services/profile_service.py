from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.domain_enums import ProfileType, ValidationStatus
from app.models.offer import Offer
from app.models.profile import Profile
from app.models.user import User
from app.repositories.profile_repository import ProfileRepository
from app.repositories.subscription_repository import SubscriptionRepository


ROLE_TO_PROFILE = {
    "buyer": ProfileType.VISITOR.value,
    "producer": ProfileType.PRODUCER.value,
}


class ProfileService:
    def __init__(self, db: Session):
        self.db = db
        self.profile_repo = ProfileRepository(db)
        self.subscription_repo = SubscriptionRepository(db)

    def get_or_create_profile(self, user: User) -> Profile:
        profile = self.profile_repo.by_user_id(user.id)
        if profile:
            return profile

        inferred_type = ROLE_TO_PROFILE.get(user.role, ProfileType.VISITOR.value)
        # Migração progressiva: perfis legados são criados como aprovados
        # para não bloquear fluxos existentes já em produção.
        inferred_status = ValidationStatus.APPROVED.value

        profile = Profile(
            user_id=user.id,
            profile_type=inferred_type,
            validation_status=inferred_status,
            phone=user.phone,
            city=(user.location or "").strip()[:100] or None,
        )
        self.profile_repo.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def ensure_offer_owner_profile(self, offer: Offer) -> Profile:
        if offer.owner_profile:
            return offer.owner_profile

        if offer.owner_profile_id:
            profile = self.db.query(Profile).filter(Profile.id == offer.owner_profile_id).first()
            if profile:
                return profile

        owner_user = offer.owner
        if owner_user is None and offer.user_id is not None:
            owner_user = self.db.query(User).filter(User.id == offer.user_id).first()

        if owner_user is None:
            raise ValueError("Oferta sem proprietário válido para resolver perfil")

        profile = self.get_or_create_profile(owner_user)
        offer.owner_profile_id = profile.id
        self.db.flush()
        return profile

    def is_offer_owner(self, *, offer: Offer, user: User) -> bool:
        if user.role == "admin" or user.is_superuser:
            return True

        current_profile = self.get_or_create_profile(user)

        if offer.owner_profile_id:
            return offer.owner_profile_id == current_profile.id

        if offer.user_id == user.id:
            offer.owner_profile_id = current_profile.id
            self.db.flush()
            return True

        return False

    def bootstrap_profile_for_new_user(self, user: User) -> Profile:
        profile_type = ROLE_TO_PROFILE.get(user.role, ProfileType.VISITOR.value)

        if profile_type == ProfileType.VISITOR.value:
            validation_status = ValidationStatus.APPROVED.value
        else:
            validation_status = ValidationStatus.PENDING.value

        profile = Profile(
            user_id=user.id,
            profile_type=profile_type,
            validation_status=validation_status,
            phone=user.phone,
            city=(user.location or "").strip()[:100] or None,
        )

        self.profile_repo.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def can_publish_offer(self, profile: Profile) -> tuple[bool, str | None]:
        if profile.profile_type not in {
            ProfileType.PRODUCER.value,
            ProfileType.BROKER.value,
            ProfileType.COMPANY.value,
        }:
            return False, "Somente produtor, corretor ou empresa podem publicar ofertas"

        if profile.validation_status != ValidationStatus.APPROVED.value:
            return False, "Perfil precisa estar aprovado para publicar ofertas"

        return True, None

    def is_premium(self, user_id: int) -> bool:
        active_sub = self.subscription_repo.get_active_by_user(user_id)
        if not active_sub:
            return False
        return active_sub.plan_type == "premium"

    def submit_documents(
        self,
        *,
        profile: Profile,
        document_type: str,
        document_number: str,
        document_front_url: str,
        document_back_url: str | None,
        document_selfie_url: str | None,
        proof_of_address_url: str | None,
    ) -> Profile:
        profile.document_type = document_type
        profile.document_number = document_number
        profile.document_front_url = document_front_url
        profile.document_back_url = document_back_url
        profile.document_selfie_url = document_selfie_url
        profile.proof_of_address_url = proof_of_address_url
        profile.submitted_at = datetime.now(timezone.utc)
        profile.validation_notes = None
        profile.validated_at = None
        profile.validated_by_user_id = None

        if profile.profile_type == ProfileType.VISITOR.value:
            profile.validation_status = ValidationStatus.APPROVED.value
        else:
            profile.validation_status = ValidationStatus.PENDING.value

        self.db.commit()
        self.db.refresh(profile)
        return profile

    def list_pending_validation(self) -> list[Profile]:
        return (
            self.db.query(Profile)
            .filter(Profile.validation_status == ValidationStatus.PENDING.value)
            .order_by(Profile.submitted_at.desc().nullslast(), Profile.created_at.desc())
            .all()
        )
