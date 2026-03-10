from datetime import datetime, timezone
from decimal import Decimal
import logging
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.domain_enums import IntermediationStatus, NegotiationStatus, PointSource
from app.services.contract_retention import purge_old_versions
from app.services.gamification_service import GamificationService
from app.services.webhook_dispatcher import dispatch_webhook
from app.models.intermediation_contract import IntermediationContract
from app.models.intermediation_contract_version import IntermediationContractVersion
from app.models.intermediation_request import IntermediationRequest
from app.models.negotiation import Negotiation
from app.models.negotiation_message import NegotiationMessage
from app.models.offer import Offer
from app.models.user import User
from app.repositories.negotiation_message_repository import NegotiationMessageRepository
from app.repositories.negotiation_repository import NegotiationRepository
from app.services.profile_service import ProfileService


TERMINAL_NEGOTIATION_STATUSES = {
    NegotiationStatus.REJECTED.value,
    NegotiationStatus.CANCELED.value,
    NegotiationStatus.COMPLETED.value,
}

logger = logging.getLogger("negotiation_service")


class NegotiationService:
    def __init__(self, db: Session):
        self.db = db
        self.profile_service = ProfileService(db)
        self.gamification_service = GamificationService(db)
        self.negotiation_repo = NegotiationRepository(db)
        self.message_repo = NegotiationMessageRepository(db)

    def _emit_intermediation_webhook(
        self,
        *,
        event_type: str,
        request: IntermediationRequest,
        extra: dict | None = None,
    ) -> None:
        payload = {
            "intermediation_request": {
                "id": str(request.id),
                "negotiation_id": str(request.negotiation_id),
                "requester_profile_id": str(request.requester_profile_id),
                "status": request.status,
                "reviewed_by_user_id": request.reviewed_by_user_id,
                "reviewed_at": request.reviewed_at.isoformat() if request.reviewed_at else None,
            },
            "extra": extra or {},
        }
        dispatch_webhook(event_type=event_type, payload=payload)

    def _award_negotiation_points(self, negotiation: Negotiation) -> None:
        """Concede pontos de gamificação ao comprador e vendedor após conclusão."""
        ref = str(negotiation.id)
        for pid in (negotiation.buyer_profile_id, negotiation.seller_profile_id):
            if pid:
                try:
                    self.gamification_service.award_points(
                        profile_id=pid,
                        source=PointSource.NEGOTIATION_COMPLETED.value,
                        reference_id=ref,
                        description="Negociação concluída",
                    )
                except Exception as exc:
                    logger.warning("Gamificação falhou para perfil %s: %s", pid, exc)

    def _get_offer_or_fail(self, offer_id: UUID) -> Offer:
        offer = self.db.query(Offer).filter(Offer.id == offer_id).first()
        if not offer:
            raise ValueError("Oferta não encontrada")
        return offer

    def _get_participant_profile_id_or_fail(self, *, negotiation: Negotiation, user: User) -> UUID:
        if user.role == "admin" or user.is_superuser:
            profile = self.profile_service.get_or_create_profile(user)
            return profile.id

        profile = self.profile_service.get_or_create_profile(user)
        if profile.id not in {negotiation.buyer_profile_id, negotiation.seller_profile_id}:
            raise ValueError("Usuário não participa desta negociação")
        return profile.id

    def create_negotiation(
        self,
        *,
        user: User,
        offer_id: UUID,
        proposed_price: Decimal,
        quantity: Decimal,
        is_intermediated: bool,
        initial_message: str | None,
    ) -> Negotiation:
        buyer_profile = self.profile_service.get_or_create_profile(user)
        offer = self._get_offer_or_fail(offer_id)
        seller_profile = self.profile_service.ensure_offer_owner_profile(offer)

        if offer.status not in {"active"}:
            raise ValueError("Oferta não está disponível para negociação")

        if seller_profile.id == buyer_profile.id:
            raise ValueError("Não é possível negociar a própria oferta")

        if quantity <= 0:
            raise ValueError("Quantidade precisa ser maior que zero")

        if quantity > Decimal(offer.quantity):
            raise ValueError("Quantidade negociada maior que o volume disponível")

        min_order = Decimal(offer.min_order or 0)
        if min_order > 0 and quantity < min_order:
            raise ValueError(f"Quantidade mínima para esta oferta é {min_order}")

        user_is_premium = self.profile_service.is_premium(user.id)

        if offer.visibility == "premium_only" and not user_is_premium:
            raise ValueError("Oferta disponível apenas para usuários premium")

        if is_intermediated and not user_is_premium:
            raise ValueError("Intermediação é exclusiva para plano premium")

        negotiation = Negotiation(
            offer_id=offer.id,
            buyer_profile_id=buyer_profile.id,
            seller_profile_id=seller_profile.id,
            proposed_price=proposed_price,
            quantity=quantity,
            status=NegotiationStatus.OPEN.value,
            is_intermediated=is_intermediated,
        )

        self.negotiation_repo.add(negotiation)

        if initial_message:
            self.message_repo.add(
                NegotiationMessage(
                    negotiation_id=negotiation.id,
                    sender_profile_id=buyer_profile.id,
                    message_text=initial_message,
                    is_read=False,
                )
            )

        self.db.commit()
        self.db.refresh(negotiation)
        return negotiation

    def update_negotiation(
        self,
        *,
        negotiation: Negotiation,
        user: User,
        proposed_price: Decimal | None,
        quantity: Decimal | None,
        is_intermediated: bool | None,
    ) -> Negotiation:
        if negotiation.status in TERMINAL_NEGOTIATION_STATUSES | {NegotiationStatus.ACCEPTED.value}:
            raise ValueError("Negociação não pode ser editada no status atual")

        self._get_participant_profile_id_or_fail(negotiation=negotiation, user=user)

        offer = negotiation.offer or self._get_offer_or_fail(negotiation.offer_id)
        target_price = Decimal(proposed_price) if proposed_price is not None else Decimal(negotiation.proposed_price)
        target_quantity = Decimal(quantity) if quantity is not None else Decimal(negotiation.quantity)

        if target_price <= 0:
            raise ValueError("Preço proposto precisa ser maior que zero")

        if target_quantity <= 0:
            raise ValueError("Quantidade precisa ser maior que zero")

        if target_quantity > Decimal(offer.quantity):
            raise ValueError("Quantidade negociada maior que o volume disponível")

        min_order = Decimal(offer.min_order or 0)
        if min_order > 0 and target_quantity < min_order:
            raise ValueError(f"Quantidade mínima para esta oferta é {min_order}")

        target_is_intermediated = (
            negotiation.is_intermediated if is_intermediated is None else is_intermediated
        )

        if target_is_intermediated and user.role != "admin" and not user.is_superuser:
            if not self.profile_service.is_premium(user.id):
                raise ValueError("Intermediação é exclusiva para plano premium")

        negotiation.proposed_price = target_price
        negotiation.quantity = target_quantity
        negotiation.is_intermediated = target_is_intermediated

        self.db.commit()
        self.db.refresh(negotiation)
        return negotiation

    def delete_negotiation(self, *, negotiation: Negotiation, user: User) -> None:
        self._get_participant_profile_id_or_fail(negotiation=negotiation, user=user)

        if negotiation.status in {NegotiationStatus.ACCEPTED.value, NegotiationStatus.COMPLETED.value}:
            raise ValueError("Negociação aceita ou concluída não pode ser removida")

        linked_intermediation = (
            self.db.query(IntermediationRequest.id)
            .filter(IntermediationRequest.negotiation_id == negotiation.id)
            .first()
        )
        if linked_intermediation:
            raise ValueError("Negociação com intermediação vinculada não pode ser removida")

        self.negotiation_repo.delete(negotiation)
        self.db.commit()

    def list_for_user(self, *, user: User, status: str | None, skip: int, limit: int) -> list[Negotiation]:
        if user.role == "admin" or user.is_superuser:
            query = self.db.query(Negotiation)
            if status:
                query = query.filter(Negotiation.status == status)
            return query.order_by(Negotiation.created_at.desc()).offset(skip).limit(limit).all()

        profile = self.profile_service.get_or_create_profile(user)
        return self.negotiation_repo.list_for_profile(profile_id=profile.id, status=status, skip=skip, limit=limit)

    def get_for_user(self, *, negotiation_id: UUID, user: User) -> Negotiation:
        if user.role == "admin" or user.is_superuser:
            negotiation = self.negotiation_repo.get(negotiation_id)
        else:
            profile = self.profile_service.get_or_create_profile(user)
            negotiation = self.negotiation_repo.get_for_profile(negotiation_id=negotiation_id, profile_id=profile.id)

        if not negotiation:
            raise ValueError("Negociação não encontrada")

        return negotiation

    def update_status(self, *, negotiation: Negotiation, user: User, new_status: str) -> Negotiation:
        allowed_transitions = {
            NegotiationStatus.OPEN.value: {
                NegotiationStatus.COUNTERED.value,
                NegotiationStatus.ACCEPTED.value,
                NegotiationStatus.REJECTED.value,
                NegotiationStatus.CANCELED.value,
            },
            NegotiationStatus.COUNTERED.value: {
                NegotiationStatus.COUNTERED.value,
                NegotiationStatus.ACCEPTED.value,
                NegotiationStatus.REJECTED.value,
                NegotiationStatus.CANCELED.value,
            },
            NegotiationStatus.ACCEPTED.value: {
                NegotiationStatus.COMPLETED.value,
                NegotiationStatus.CANCELED.value,
            },
            NegotiationStatus.REJECTED.value: set(),
            NegotiationStatus.CANCELED.value: set(),
            NegotiationStatus.COMPLETED.value: set(),
        }

        if new_status == negotiation.status:
            return negotiation

        allowed = allowed_transitions.get(negotiation.status, set())
        if new_status not in allowed:
            raise ValueError(f"Transição inválida: {negotiation.status} -> {new_status}")

        self._get_participant_profile_id_or_fail(negotiation=negotiation, user=user)

        # Conclusão da negociação afeta estoque da oferta.
        if new_status == NegotiationStatus.COMPLETED.value:
            if user.role != "admin" and not user.is_superuser:
                actor_profile = self.profile_service.get_or_create_profile(user)
                if actor_profile.id != negotiation.seller_profile_id:
                    raise ValueError("Somente vendedor ou admin pode concluir negociação")

            if negotiation.is_intermediated:
                validated_request_with_contract = (
                    self.db.query(IntermediationRequest)
                    .join(
                        IntermediationContract,
                        IntermediationContract.intermediation_request_id == IntermediationRequest.id,
                    )
                    .filter(
                        IntermediationRequest.negotiation_id == negotiation.id,
                        IntermediationRequest.status == IntermediationStatus.VALIDADA.value,
                    )
                    .first()
                )
                if not validated_request_with_contract:
                    raise ValueError(
                        "Negociação intermediada exige contrato validado para conclusão"
                    )

            offer = negotiation.offer
            if not offer:
                offer = self._get_offer_or_fail(negotiation.offer_id)

            if Decimal(offer.quantity) < Decimal(negotiation.quantity):
                raise ValueError("Estoque insuficiente para concluir a negociação")

            offer.quantity = Decimal(offer.quantity) - Decimal(negotiation.quantity)
            if Decimal(offer.quantity) <= 0:
                offer.status = "closed"

            # Gamificação: pontos para comprador e vendedor
            self._award_negotiation_points(negotiation)

        negotiation.status = new_status
        self.db.commit()
        self.db.refresh(negotiation)
        return negotiation

    def counter_offer(
        self,
        *,
        negotiation: Negotiation,
        user: User,
        proposed_price: Decimal,
        quantity: Decimal | None,
        message: str | None,
    ) -> Negotiation:
        sender_profile_id = self._get_participant_profile_id_or_fail(negotiation=negotiation, user=user)

        if negotiation.status in TERMINAL_NEGOTIATION_STATUSES:
            raise ValueError("Negociação encerrada não aceita contraproposta")

        if proposed_price <= 0:
            raise ValueError("Preço da contraproposta deve ser maior que zero")

        target_quantity = Decimal(quantity) if quantity is not None else Decimal(negotiation.quantity)
        if target_quantity <= 0:
            raise ValueError("Quantidade da contraproposta deve ser maior que zero")

        offer = negotiation.offer or self._get_offer_or_fail(negotiation.offer_id)

        if target_quantity > Decimal(offer.quantity):
            raise ValueError("Quantidade da contraproposta maior que volume disponível")

        min_order = Decimal(offer.min_order or 0)
        if min_order > 0 and target_quantity < min_order:
            raise ValueError(f"Quantidade mínima para esta oferta é {min_order}")

        negotiation.proposed_price = proposed_price
        negotiation.quantity = target_quantity
        negotiation.status = NegotiationStatus.COUNTERED.value

        if message:
            self.message_repo.add(
                NegotiationMessage(
                    negotiation_id=negotiation.id,
                    sender_profile_id=sender_profile_id,
                    message_text=message,
                    is_read=False,
                )
            )

        self.db.commit()
        self.db.refresh(negotiation)
        return negotiation

    def add_message(self, *, negotiation: Negotiation, user: User, message_text: str) -> NegotiationMessage:
        sender_profile_id = self._get_participant_profile_id_or_fail(negotiation=negotiation, user=user)

        if negotiation.status in TERMINAL_NEGOTIATION_STATUSES:
            raise ValueError("Negociação encerrada não aceita novas mensagens")

        message = NegotiationMessage(
            negotiation_id=negotiation.id,
            sender_profile_id=sender_profile_id,
            message_text=message_text,
            is_read=False,
        )

        self.message_repo.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_messages(self, *, negotiation: Negotiation, user: User, mark_as_read: bool = True) -> list[NegotiationMessage]:
        profile_id = self._get_participant_profile_id_or_fail(negotiation=negotiation, user=user)

        messages = self.message_repo.list_by_negotiation(negotiation.id)
        changed = False

        if mark_as_read:
            for msg in messages:
                if msg.sender_profile_id != profile_id and not msg.is_read:
                    msg.is_read = True
                    changed = True

        if changed:
            self.db.commit()

        return messages

    def request_intermediation(self, *, negotiation: Negotiation, user: User, notes: str | None) -> IntermediationRequest:
        requester_profile = self.profile_service.get_or_create_profile(user)

        if requester_profile.id not in {negotiation.buyer_profile_id, negotiation.seller_profile_id}:
            raise ValueError("Usuário não participa desta negociação")

        if not self.profile_service.is_premium(user.id):
            raise ValueError("A intermediação é exclusiva para usuários premium")

        existing = (
            self.db.query(IntermediationRequest)
            .filter(
                IntermediationRequest.negotiation_id == negotiation.id,
                IntermediationRequest.status.in_(
                    [IntermediationStatus.EM_VALIDACAO.value, IntermediationStatus.VALIDADA.value]
                ),
            )
            .first()
        )
        if existing:
            raise ValueError("Já existe solicitação ativa de intermediação para esta negociação")

        request = IntermediationRequest(
            negotiation_id=negotiation.id,
            requester_profile_id=requester_profile.id,
            status=IntermediationStatus.EM_VALIDACAO.value,
            notes=notes,
        )
        self.db.add(request)
        negotiation.is_intermediated = True

        self.db.commit()
        self.db.refresh(request)

        self._emit_intermediation_webhook(
            event_type="intermediation_requested",
            request=request,
        )
        return request

    def _resolve_negotiation_access_from_intermediation(
        self,
        *,
        request: IntermediationRequest,
        user: User,
    ) -> Negotiation:
        negotiation = request.negotiation or self.negotiation_repo.get(request.negotiation_id)
        if not negotiation:
            raise ValueError("Negociação não encontrada")

        if user.role == "admin" or user.is_superuser:
            return negotiation

        profile = self.profile_service.get_or_create_profile(user)
        if profile.id not in {negotiation.buyer_profile_id, negotiation.seller_profile_id}:
            raise ValueError("Usuário não participa desta negociação")

        return negotiation

    def list_intermediation_for_negotiation(
        self,
        *,
        negotiation: Negotiation,
        user: User,
    ) -> list[IntermediationRequest]:
        self._get_participant_profile_id_or_fail(negotiation=negotiation, user=user)

        return (
            self.db.query(IntermediationRequest)
            .filter(IntermediationRequest.negotiation_id == negotiation.id)
            .order_by(IntermediationRequest.created_at.desc())
            .all()
        )

    def list_intermediation_requests(
        self,
        *,
        status: str | None,
        skip: int,
        limit: int,
    ) -> list[IntermediationRequest]:
        query = self.db.query(IntermediationRequest)
        if status:
            query = query.filter(IntermediationRequest.status == status)

        return query.order_by(IntermediationRequest.created_at.desc()).offset(skip).limit(limit).all()

    def get_intermediation_request_or_fail(self, request_id: UUID) -> IntermediationRequest:
        request = self.db.query(IntermediationRequest).filter(IntermediationRequest.id == request_id).first()
        if not request:
            raise ValueError("Solicitação de intermediação não encontrada")
        return request

    def get_intermediation_contract(
        self,
        *,
        request: IntermediationRequest,
        user: User,
    ) -> IntermediationContract:
        self._resolve_negotiation_access_from_intermediation(request=request, user=user)

        if not request.contract:
            raise ValueError("Contrato de intermediação não encontrado")

        return request.contract

    def upsert_intermediation_contract(
        self,
        *,
        request: IntermediationRequest,
        user: User,
        file_url: str,
        file_name: str | None,
        notes: str | None,
    ) -> IntermediationContract:
        self._resolve_negotiation_access_from_intermediation(request=request, user=user)

        if request.status != IntermediationStatus.VALIDADA.value:
            raise ValueError("Contrato só pode ser anexado após intermediação validada")

        contract = request.contract
        should_register_version = False

        if contract:
            normalized_notes = notes.strip() if isinstance(notes, str) else notes
            should_register_version = any(
                [
                    contract.file_url != file_url,
                    contract.file_name != file_name,
                    contract.notes != normalized_notes,
                    contract.uploaded_by_user_id != user.id,
                ]
            )

            contract.file_url = file_url
            contract.file_name = file_name
            contract.notes = normalized_notes
            contract.uploaded_by_user_id = user.id
        else:
            contract = IntermediationContract(
                intermediation_request_id=request.id,
                file_url=file_url,
                file_name=file_name,
                notes=notes,
                uploaded_by_user_id=user.id,
            )
            self.db.add(contract)
            self.db.flush()
            should_register_version = True

        if should_register_version:
            self._create_contract_version_snapshot(contract=contract, user_id=user.id)
            purge_old_versions(self.db, contract_id=contract.id)

        self.db.commit()
        self.db.refresh(contract)

        self._emit_intermediation_webhook(
            event_type="intermediation_contract_upserted",
            request=request,
            extra={
                "contract_id": str(contract.id),
                "uploaded_by_user_id": user.id,
            },
        )
        return contract

    def _create_contract_version_snapshot(
        self,
        *,
        contract: IntermediationContract,
        user_id: int,
    ) -> IntermediationContractVersion:
        current_version = (
            self.db.query(func.max(IntermediationContractVersion.version_number))
            .filter(IntermediationContractVersion.contract_id == contract.id)
            .scalar()
            or 0
        )
        next_version = int(current_version) + 1

        snapshot = IntermediationContractVersion(
            contract_id=contract.id,
            version_number=next_version,
            file_url=contract.file_url,
            file_name=contract.file_name,
            notes=contract.notes,
            uploaded_by_user_id=user_id,
        )
        self.db.add(snapshot)
        return snapshot

    def list_intermediation_contract_versions(
        self,
        *,
        request: IntermediationRequest,
        user: User,
        skip: int,
        limit: int,
    ) -> list[IntermediationContractVersion]:
        contract = self.get_intermediation_contract(request=request, user=user)

        return (
            self.db.query(IntermediationContractVersion)
            .filter(IntermediationContractVersion.contract_id == contract.id)
            .order_by(IntermediationContractVersion.version_number.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def review_intermediation_request(
        self,
        *,
        request: IntermediationRequest,
        reviewed_by_user: User,
        new_status: str,
        review_notes: str | None,
    ) -> IntermediationRequest:
        if new_status not in {
            IntermediationStatus.VALIDADA.value,
            IntermediationStatus.REJEITADA.value,
        }:
            raise ValueError("Status de revisão inválido")

        if request.status != IntermediationStatus.EM_VALIDACAO.value:
            raise ValueError("Solicitação já foi analisada")

        request.status = new_status
        request.review_notes = review_notes
        request.reviewed_by_user_id = reviewed_by_user.id
        request.reviewed_at = datetime.now(timezone.utc)

        negotiation = request.negotiation or self.negotiation_repo.get(request.negotiation_id)
        if negotiation:
            negotiation.is_intermediated = new_status == IntermediationStatus.VALIDADA.value

        self.db.commit()
        self.db.refresh(request)

        self._emit_intermediation_webhook(
            event_type="intermediation_reviewed",
            request=request,
            extra={
                "new_status": new_status,
                "reviewed_by_user_id": reviewed_by_user.id,
            },
        )
        return request
