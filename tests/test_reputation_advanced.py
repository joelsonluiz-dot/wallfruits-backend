"""
Testes de reputação avançada: score ponderado, contestação, invalidação.
"""
import os
import unittest
from decimal import Decimal
from uuid import uuid4

os.environ.setdefault("REDIS_ENABLED", "false")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient

from app.auth.jwt_handler import create_access_token
from app.core.domain_enums import ContestationStatus, NegotiationStatus
from app.database.connection import SessionLocal
from app.main import app
from app.models.negotiation import Negotiation
from app.models.offer import Offer
from app.models.profile import Profile
from app.models.reputation_review import ReputationReview
from app.models.review_contestation import ReviewContestation
from app.models.user import User
from app.services.reputation_service import ReputationService


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"user_id": user.id, "email": user.email})
    return {"Authorization": f"Bearer {token}"}


class TestWeightedReputation(unittest.TestCase):
    """Testes do cálculo de reputação ponderada."""

    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def _seed(self):
        suffix = uuid4().hex[:8]
        seller = User(name="Seller", email=f"seller_rep_{suffix}@t.l", password="x", role="producer", is_active=True)
        buyer = User(name="Buyer", email=f"buyer_rep_{suffix}@t.l", password="x", role="buyer", is_active=True)
        buyer2 = User(name="Buyer2", email=f"buyer2_rep_{suffix}@t.l", password="x", role="buyer", is_active=True)
        self.db.add_all([seller, buyer, buyer2])
        self.db.flush()

        seller_profile = Profile(user_id=seller.id, profile_type="producer", validation_status="approved")
        buyer_profile = Profile(user_id=buyer.id, profile_type="buyer", validation_status="approved")
        buyer2_profile = Profile(user_id=buyer2.id, profile_type="buyer", validation_status="approved")
        self.db.add_all([seller_profile, buyer_profile, buyer2_profile])
        self.db.flush()

        offer = Offer(
            user_id=seller.id,
            owner_profile_id=seller_profile.id,
            product_name="Café",
            quantity=Decimal("100"),
            price=Decimal("10.00"),
            unit="kg",
            status="active",
            visibility="public",
            min_order=Decimal("1"),
        )
        self.db.add(offer)
        self.db.flush()

        return {
            "seller": seller,
            "buyer": buyer,
            "buyer2": buyer2,
            "seller_profile": seller_profile,
            "buyer_profile": buyer_profile,
            "buyer2_profile": buyer2_profile,
            "offer": offer,
        }

    def _create_completed_negotiation(self, ctx, buyer_profile, price, qty):
        neg = Negotiation(
            offer_id=ctx["offer"].id,
            buyer_profile_id=buyer_profile.id,
            seller_profile_id=ctx["seller_profile"].id,
            proposed_price=Decimal(str(price)),
            quantity=Decimal(str(qty)),
            status=NegotiationStatus.COMPLETED.value,
        )
        self.db.add(neg)
        self.db.flush()
        return neg

    def test_weighted_score_single_review(self):
        ctx = self._seed()
        neg = self._create_completed_negotiation(ctx, ctx["buyer_profile"], 10, 100)
        review = ReputationReview(
            negotiation_id=neg.id,
            reviewer_profile_id=ctx["buyer_profile"].id,
            reviewed_profile_id=ctx["seller_profile"].id,
            rating=4,
        )
        self.db.add(review)
        self.db.flush()

        service = ReputationService(self.db)
        service._recalculate_profile_reputation_score(ctx["seller_profile"].id)

        self.db.flush()
        self.db.refresh(ctx["seller_profile"])
        self.assertEqual(float(ctx["seller_profile"].reputation_score), 4.0)
        self.db.rollback()

    def test_weighted_score_multiple_reviews_different_values(self):
        """Review de negociação de maior valor deve ter mais peso."""
        ctx = self._seed()

        # Neg 1: R$10 * 10 = R$100, rating 2
        neg1 = self._create_completed_negotiation(ctx, ctx["buyer_profile"], 10, 10)
        r1 = ReputationReview(
            negotiation_id=neg1.id,
            reviewer_profile_id=ctx["buyer_profile"].id,
            reviewed_profile_id=ctx["seller_profile"].id,
            rating=2,
        )

        # Neg 2: R$10 * 90 = R$900, rating 5
        neg2 = self._create_completed_negotiation(ctx, ctx["buyer2_profile"], 10, 90)
        r2 = ReputationReview(
            negotiation_id=neg2.id,
            reviewer_profile_id=ctx["buyer2_profile"].id,
            reviewed_profile_id=ctx["seller_profile"].id,
            rating=5,
        )

        self.db.add_all([r1, r2])
        self.db.flush()

        service = ReputationService(self.db)
        service._recalculate_profile_reputation_score(ctx["seller_profile"].id)
        self.db.flush()
        self.db.refresh(ctx["seller_profile"])

        # Weighted: (2*100 + 5*900) / (100+900) = (200+4500)/1000 = 4.7
        self.assertEqual(float(ctx["seller_profile"].reputation_score), 4.7)
        self.db.rollback()

    def test_invalidated_reviews_excluded_from_score(self):
        ctx = self._seed()

        neg1 = self._create_completed_negotiation(ctx, ctx["buyer_profile"], 10, 10)
        r1 = ReputationReview(
            negotiation_id=neg1.id,
            reviewer_profile_id=ctx["buyer_profile"].id,
            reviewed_profile_id=ctx["seller_profile"].id,
            rating=1,
            is_invalidated=True,  # Invalidada
        )

        neg2 = self._create_completed_negotiation(ctx, ctx["buyer2_profile"], 10, 10)
        r2 = ReputationReview(
            negotiation_id=neg2.id,
            reviewer_profile_id=ctx["buyer2_profile"].id,
            reviewed_profile_id=ctx["seller_profile"].id,
            rating=5,
        )

        self.db.add_all([r1, r2])
        self.db.flush()

        service = ReputationService(self.db)
        service._recalculate_profile_reputation_score(ctx["seller_profile"].id)
        self.db.flush()
        self.db.refresh(ctx["seller_profile"])

        # Só a review r2 (rating=5) conta
        self.assertEqual(float(ctx["seller_profile"].reputation_score), 5.0)
        self.db.rollback()

    def test_summary_has_weighted_fields(self):
        ctx = self._seed()
        neg = self._create_completed_negotiation(ctx, ctx["buyer_profile"], 20, 5)
        r = ReputationReview(
            negotiation_id=neg.id,
            reviewer_profile_id=ctx["buyer_profile"].id,
            reviewed_profile_id=ctx["seller_profile"].id,
            rating=4,
        )
        self.db.add(r)
        self.db.flush()

        service = ReputationService(self.db)
        summary = service.get_profile_summary(profile_id=ctx["seller_profile"].id)

        self.assertIn("weighted_average_rating", summary)
        self.assertIn("total_negotiated_value", summary)
        self.assertIn("contestations", summary)
        self.assertEqual(summary["weighted_average_rating"], 4.0)
        self.assertEqual(summary["total_negotiated_value"], 100.0)  # 20*5
        self.assertEqual(summary["contestations"]["total"], 0)
        self.db.rollback()


class TestContestationService(unittest.TestCase):
    """Testes do fluxo de contestação."""

    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def _seed_with_review(self):
        suffix = uuid4().hex[:8]
        seller = User(name="Seller", email=f"seller_c_{suffix}@t.l", password="x", role="producer", is_active=True)
        buyer = User(name="Buyer", email=f"buyer_c_{suffix}@t.l", password="x", role="buyer", is_active=True)
        admin = User(name="Admin", email=f"admin_c_{suffix}@t.l", password="x", role="admin", is_active=True, is_superuser=True)
        self.db.add_all([seller, buyer, admin])
        self.db.flush()

        seller_profile = Profile(user_id=seller.id, profile_type="producer", validation_status="approved")
        buyer_profile = Profile(user_id=buyer.id, profile_type="buyer", validation_status="approved")
        self.db.add_all([seller_profile, buyer_profile])
        self.db.flush()

        offer = Offer(
            user_id=seller.id,
            owner_profile_id=seller_profile.id,
            product_name="Soja",
            quantity=Decimal("500"),
            price=Decimal("5.00"),
            unit="kg",
            status="active",
            visibility="public",
            min_order=Decimal("1"),
        )
        self.db.add(offer)
        self.db.flush()

        neg = Negotiation(
            offer_id=offer.id,
            buyer_profile_id=buyer_profile.id,
            seller_profile_id=seller_profile.id,
            proposed_price=Decimal("5.00"),
            quantity=Decimal("100"),
            status=NegotiationStatus.COMPLETED.value,
        )
        self.db.add(neg)
        self.db.flush()

        review = ReputationReview(
            negotiation_id=neg.id,
            reviewer_profile_id=buyer_profile.id,
            reviewed_profile_id=seller_profile.id,
            rating=2,
        )
        self.db.add(review)
        self.db.flush()

        return {
            "seller": seller,
            "buyer": buyer,
            "admin": admin,
            "seller_profile": seller_profile,
            "buyer_profile": buyer_profile,
            "offer": offer,
            "negotiation": neg,
            "review": review,
        }

    def test_create_contestation_success(self):
        ctx = self._seed_with_review()
        service = ReputationService(self.db)
        contestation = service.create_contestation(
            current_user=ctx["seller"],
            review_id=ctx["review"].id,
            reason="A avaliação não condiz com a transação realizada",
        )
        self.assertIsNotNone(contestation.id)
        self.assertEqual(contestation.status, ContestationStatus.PENDING.value)
        self.assertEqual(contestation.review_id, ctx["review"].id)
        self.db.rollback()

    def test_only_reviewed_can_contest(self):
        ctx = self._seed_with_review()
        service = ReputationService(self.db)
        with self.assertRaises(ValueError) as cm:
            service.create_contestation(
                current_user=ctx["buyer"],  # reviewer, não o reviewed
                review_id=ctx["review"].id,
                reason="Tentando contestar minha própria review",
            )
        self.assertIn("Somente o avaliado", str(cm.exception))
        self.db.rollback()

    def test_no_duplicate_pending_contestation(self):
        ctx = self._seed_with_review()
        service = ReputationService(self.db)
        service.create_contestation(
            current_user=ctx["seller"],
            review_id=ctx["review"].id,
            reason="Primeira contestação válida aqui",
        )
        with self.assertRaises(ValueError) as cm:
            service.create_contestation(
                current_user=ctx["seller"],
                review_id=ctx["review"].id,
                reason="Segunda contestação que deveria falhar",
            )
        self.assertIn("Já existe", str(cm.exception))
        self.db.rollback()

    def test_admin_accept_invalidates_review(self):
        ctx = self._seed_with_review()
        service = ReputationService(self.db)

        # Recalcular score inicial (rating=2)
        service._recalculate_profile_reputation_score(ctx["seller_profile"].id)
        self.db.flush()
        self.db.refresh(ctx["seller_profile"])
        initial_score = float(ctx["seller_profile"].reputation_score)
        self.assertEqual(initial_score, 2.0)

        contestation = service.create_contestation(
            current_user=ctx["seller"],
            review_id=ctx["review"].id,
            reason="Avaliação injusta, entrega foi realizada corretamente",
        )

        result = service.review_contestation(
            contestation_id=contestation.id,
            admin_user=ctx["admin"],
            new_status=ContestationStatus.ACCEPTED.value,
            review_notes="Evidências confirmam a contestação",
        )

        self.assertEqual(result.status, ContestationStatus.ACCEPTED.value)
        self.assertIsNotNone(result.reviewed_at)
        self.assertEqual(result.reviewed_by_user_id, ctx["admin"].id)

        # Review deve estar invalidada
        self.db.flush()
        self.db.refresh(ctx["review"])
        self.assertTrue(ctx["review"].is_invalidated)

        # Score deve ser recalculado (sem reviews válidas = 0)
        self.db.flush()
        self.db.refresh(ctx["seller_profile"])
        self.assertEqual(float(ctx["seller_profile"].reputation_score), 0.0)
        self.db.rollback()

    def test_admin_reject_keeps_review(self):
        ctx = self._seed_with_review()
        service = ReputationService(self.db)

        contestation = service.create_contestation(
            current_user=ctx["seller"],
            review_id=ctx["review"].id,
            reason="Tentativa de contestação sem fundamento",
        )

        result = service.review_contestation(
            contestation_id=contestation.id,
            admin_user=ctx["admin"],
            new_status=ContestationStatus.REJECTED.value,
            review_notes="Sem evidências suficientes",
        )

        self.assertEqual(result.status, ContestationStatus.REJECTED.value)

        # Review NÃO deve estar invalidada
        self.db.flush()
        self.db.refresh(ctx["review"])
        self.assertFalse(ctx["review"].is_invalidated)
        self.db.rollback()

    def test_cannot_review_already_resolved(self):
        ctx = self._seed_with_review()
        service = ReputationService(self.db)

        contestation = service.create_contestation(
            current_user=ctx["seller"],
            review_id=ctx["review"].id,
            reason="Contestação que será resolvida",
        )
        service.review_contestation(
            contestation_id=contestation.id,
            admin_user=ctx["admin"],
            new_status=ContestationStatus.REJECTED.value,
        )

        with self.assertRaises(ValueError) as cm:
            service.review_contestation(
                contestation_id=contestation.id,
                admin_user=ctx["admin"],
                new_status=ContestationStatus.ACCEPTED.value,
            )
        self.assertIn("já foi revisada", str(cm.exception))
        self.db.rollback()

    def test_list_pending_contestations(self):
        ctx = self._seed_with_review()
        service = ReputationService(self.db)

        service.create_contestation(
            current_user=ctx["seller"],
            review_id=ctx["review"].id,
            reason="Contestação pendente para listagem",
        )

        pending = service.list_pending_contestations()
        self.assertTrue(len(pending) >= 1)
        self.db.rollback()


class TestContestationAPI(unittest.TestCase):
    """Testes das rotas HTTP de contestação."""

    @classmethod
    def setUpClass(cls):
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    def _seed_with_review(self):
        db = SessionLocal()
        suffix = uuid4().hex[:8]

        seller = User(name="Seller", email=f"seller_api_{suffix}@t.l", password="x", role="producer", is_active=True)
        buyer = User(name="Buyer", email=f"buyer_api_{suffix}@t.l", password="x", role="buyer", is_active=True)
        admin = User(name="Admin", email=f"admin_api_{suffix}@t.l", password="x", role="admin", is_active=True, is_superuser=True)
        db.add_all([seller, buyer, admin])
        db.commit()
        for u in [seller, buyer, admin]:
            db.refresh(u)

        seller_profile = Profile(user_id=seller.id, profile_type="producer", validation_status="approved")
        buyer_profile = Profile(user_id=buyer.id, profile_type="buyer", validation_status="approved")
        db.add_all([seller_profile, buyer_profile])
        db.commit()
        for p in [seller_profile, buyer_profile]:
            db.refresh(p)

        offer = Offer(
            user_id=seller.id,
            owner_profile_id=seller_profile.id,
            product_name="Milho",
            quantity=Decimal("200"),
            price=Decimal("8.00"),
            unit="kg",
            status="active",
            visibility="public",
            min_order=Decimal("1"),
        )
        db.add(offer)
        db.commit()
        db.refresh(offer)

        neg = Negotiation(
            offer_id=offer.id,
            buyer_profile_id=buyer_profile.id,
            seller_profile_id=seller_profile.id,
            proposed_price=Decimal("8.00"),
            quantity=Decimal("50"),
            status=NegotiationStatus.COMPLETED.value,
        )
        db.add(neg)
        db.commit()
        db.refresh(neg)

        review = ReputationReview(
            negotiation_id=neg.id,
            reviewer_profile_id=buyer_profile.id,
            reviewed_profile_id=seller_profile.id,
            rating=1,
        )
        db.add(review)
        db.commit()
        db.refresh(review)

        db.close()
        return {
            "seller": seller,
            "buyer": buyer,
            "admin": admin,
            "review": review,
        }

    def test_create_contestation_api(self):
        ctx = self._seed_with_review()
        seller_h = _auth_headers(ctx["seller"])

        resp = self.client.post(
            f"/api/reputation/reviews/{ctx['review'].id}/contest",
            json={"reason": "A transação ocorreu corretamente, avaliação injusta"},
            headers=seller_h,
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        data = resp.json()
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["review_id"], str(ctx["review"].id))

    def test_my_contestations_api(self):
        ctx = self._seed_with_review()
        seller_h = _auth_headers(ctx["seller"])

        # Criar contestação primeiro
        self.client.post(
            f"/api/reputation/reviews/{ctx['review'].id}/contest",
            json={"reason": "Review injusta que precisa ser contestada"},
            headers=seller_h,
        )

        resp = self.client.get("/api/reputation/my/contestations", headers=seller_h)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(len(data) >= 1)

    def test_admin_review_contestation_api(self):
        ctx = self._seed_with_review()
        seller_h = _auth_headers(ctx["seller"])
        admin_h = _auth_headers(ctx["admin"])

        # Criar
        create_resp = self.client.post(
            f"/api/reputation/reviews/{ctx['review'].id}/contest",
            json={"reason": "Avaliação completamente descabida e sem sentido"},
            headers=seller_h,
        )
        self.assertEqual(create_resp.status_code, 201)
        contestation_id = create_resp.json()["id"]

        # Admin aceita
        review_resp = self.client.patch(
            f"/api/reputation/admin/contestations/{contestation_id}",
            json={"status": "accepted", "review_notes": "Contestação procedente"},
            headers=admin_h,
        )
        self.assertEqual(review_resp.status_code, 200)
        self.assertEqual(review_resp.json()["status"], "accepted")

    def test_summary_api_with_weighted_fields(self):
        ctx = self._seed_with_review()
        # Precisamos do profile_id do seller. Buscar via DB.
        db = SessionLocal()
        from app.models.profile import Profile
        profile = db.query(Profile).filter(Profile.user_id == ctx["seller"].id).first()
        db.close()

        resp = self.client.get(f"/api/reputation/profiles/{profile.id}/summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("weighted_average_rating", data)
        self.assertIn("total_negotiated_value", data)
        self.assertIn("contestations", data)


if __name__ == "__main__":
    unittest.main()
