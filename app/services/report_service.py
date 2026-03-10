from datetime import datetime, timezone
import unicodedata
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.domain_enums import ReportStatus, ValidationStatus
from app.models.offer import Offer
from app.models.profile import Profile
from app.models.report import Report
from app.models.user import User
from app.services.profile_service import ProfileService


class ReportService:
    AUTO_SUSPEND_PENDING_THRESHOLD = 3
    SEVERE_KEYWORDS = {
        "fraude",
        "golpe",
        "estelionato",
        "roubo",
        "ameaça",
        "ameaca",
        "falso",
        "falsificacao",
    }

    def __init__(self, db: Session):
        self.db = db
        self.profile_service = ProfileService(db)

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value.lower())
        return "".join(ch for ch in normalized if not unicodedata.combining(ch))

    def _is_severe_reason(self, reason: str) -> bool:
        normalized = self._normalize_text(reason)
        return any(keyword in normalized for keyword in self.SEVERE_KEYWORDS)

    def _resolve_report_target(
        self,
        *,
        reported_profile_id: UUID | None,
        reported_offer_id: UUID | None,
    ) -> tuple[UUID | None, UUID | None]:
        target_profile_id = reported_profile_id

        if reported_offer_id:
            offer = self.db.query(Offer).filter(Offer.id == reported_offer_id).first()
            if not offer:
                raise ValueError("Oferta denunciada não encontrada")

            if not target_profile_id:
                if offer.owner_profile_id:
                    target_profile_id = offer.owner_profile_id
                else:
                    owner_profile = self.profile_service.get_or_create_profile(offer.owner)
                    offer.owner_profile_id = owner_profile.id
                    target_profile_id = owner_profile.id

        if not target_profile_id and not reported_offer_id:
            raise ValueError("Informe perfil ou oferta para denúncia")

        return target_profile_id, reported_offer_id

    def _auto_suspend_if_needed(self, *, reported_profile_id: UUID | None, reason: str) -> None:
        if not reported_profile_id:
            return

        if not self._is_severe_reason(reason):
            return

        pending_reports = (
            self.db.query(func.count(Report.id))
            .filter(
                Report.reported_profile_id == reported_profile_id,
                Report.status.in_([ReportStatus.PENDING.value, ReportStatus.UNDER_REVIEW.value]),
            )
            .scalar()
            or 0
        )

        if pending_reports < self.AUTO_SUSPEND_PENDING_THRESHOLD:
            return

        profile = self.db.query(Profile).filter(Profile.id == reported_profile_id).first()
        if not profile:
            return

        if profile.validation_status == ValidationStatus.SUSPENDED.value:
            return

        profile.validation_status = ValidationStatus.SUSPENDED.value
        stamp = datetime.now(timezone.utc).isoformat()
        note = f"[AUTO_SUSPENSAO] {pending_reports} denuncias graves pendentes em {stamp}."
        profile.validation_notes = f"{(profile.validation_notes or '').strip()} {note}".strip()

    def create_report(
        self,
        *,
        current_user: User,
        reported_profile_id: UUID | None,
        reported_offer_id: UUID | None,
        reason: str,
    ) -> Report:
        reporter_profile = self.profile_service.get_or_create_profile(current_user)
        target_profile_id, target_offer_id = self._resolve_report_target(
            reported_profile_id=reported_profile_id,
            reported_offer_id=reported_offer_id,
        )

        if target_profile_id and target_profile_id == reporter_profile.id:
            raise ValueError("Não é permitido denunciar o próprio perfil")

        report = Report(
            reporter_profile_id=reporter_profile.id,
            reported_profile_id=target_profile_id,
            reported_offer_id=target_offer_id,
            reason=reason,
            status=ReportStatus.PENDING.value,
        )

        self.db.add(report)
        self.db.flush()
        self._auto_suspend_if_needed(reported_profile_id=target_profile_id, reason=reason)

        self.db.commit()
        self.db.refresh(report)
        return report

    def list_my_reports(self, *, current_user: User, skip: int, limit: int) -> list[Report]:
        reporter_profile = self.profile_service.get_or_create_profile(current_user)
        return (
            self.db.query(Report)
            .filter(Report.reporter_profile_id == reporter_profile.id)
            .order_by(Report.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_reports(self, *, status: str | None, skip: int, limit: int) -> list[Report]:
        query = self.db.query(Report)
        if status:
            query = query.filter(Report.status == status)

        return query.order_by(Report.created_at.desc()).offset(skip).limit(limit).all()

    def get_report_or_fail(self, report_id: UUID) -> Report:
        report = self.db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise ValueError("Denúncia não encontrada")
        return report

    def review_report(
        self,
        *,
        report: Report,
        reviewer: User,
        status: str,
        resolution_notes: str | None,
    ) -> Report:
        allowed_statuses = {
            ReportStatus.PENDING.value,
            ReportStatus.UNDER_REVIEW.value,
            ReportStatus.RESOLVED.value,
            ReportStatus.DISMISSED.value,
        }
        if status not in allowed_statuses:
            raise ValueError("Status de denúncia inválido")

        report.status = status
        report.reviewed_by_user_id = reviewer.id
        report.reviewed_at = datetime.now(timezone.utc)
        report.resolution_notes = resolution_notes

        self.db.commit()
        self.db.refresh(report)
        return report
