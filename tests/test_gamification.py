"""
Testes de gamificação: pontos, níveis, badges, leaderboard e integração API.
"""
import os
import unittest
from uuid import uuid4

os.environ.setdefault("REDIS_ENABLED", "false")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient

from app.auth.jwt_handler import create_access_token
from app.database.connection import SessionLocal
from app.main import app
from app.models.badge import Badge
from app.models.offer import Offer
from app.models.profile import Profile
from app.models.user import User
from app.services.gamification_service import GamificationService, XP_PER_LEVEL, POINTS_TABLE


class TestGamificationService(unittest.TestCase):
    """Testes unitários do serviço de gamificação."""

    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def _create_user_and_profile(self, suffix: str | None = None):
        suffix = suffix or uuid4().hex[:8]
        user = User(
            name="Gamer",
            email=f"gamer_{suffix}@test.local",
            password="x",
            role="producer",
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()
        profile = Profile(
            user_id=user.id,
            profile_type="producer",
            validation_status="approved",
        )
        self.db.add(profile)
        self.db.flush()
        return user, profile

    def test_get_or_create_profile(self):
        _, profile = self._create_user_and_profile()
        service = GamificationService(self.db)
        gp = service.get_or_create_profile(profile.id)
        self.assertEqual(gp.total_points, 0)
        self.assertEqual(gp.level, 1)
        self.assertEqual(gp.xp, 0)

        # Segundo chamado retorna o mesmo
        gp2 = service.get_or_create_profile(profile.id)
        self.assertEqual(gp.id, gp2.id)
        self.db.rollback()

    def test_award_points(self):
        _, profile = self._create_user_and_profile()
        service = GamificationService(self.db)
        tx = service.award_points(
            profile_id=profile.id,
            source="negotiation_completed",
            reference_id="neg-123",
        )
        self.assertEqual(tx.amount, POINTS_TABLE["negotiation_completed"])

        gp = service.get_or_create_profile(profile.id)
        self.assertEqual(gp.total_points, 50)
        self.db.rollback()

    def test_custom_amount(self):
        _, profile = self._create_user_and_profile()
        service = GamificationService(self.db)
        tx = service.award_points(
            profile_id=profile.id,
            source="bonus",
            amount=200,
            description="Bônus especial",
        )
        self.assertEqual(tx.amount, 200)
        gp = service.get_or_create_profile(profile.id)
        self.assertEqual(gp.total_points, 200)
        self.db.rollback()

    def test_level_up(self):
        _, profile = self._create_user_and_profile()
        service = GamificationService(self.db)
        # Nível 1→2 exige 100 XP. Dar 150 pontos deve subir para nível 2 com 50 XP restante.
        service.award_points(
            profile_id=profile.id, source="bonus", amount=150,
        )
        gp = service.get_or_create_profile(profile.id)
        self.assertEqual(gp.level, 2)
        self.assertEqual(gp.xp, 50)
        self.db.rollback()

    def test_multi_level_up(self):
        _, profile = self._create_user_and_profile()
        service = GamificationService(self.db)
        # Nível 1→2 = 100, 2→3 = 200. Total 300 exato para chegar ao 3 com 0 XP.
        service.award_points(
            profile_id=profile.id, source="bonus", amount=300,
        )
        gp = service.get_or_create_profile(profile.id)
        self.assertEqual(gp.level, 3)
        self.assertEqual(gp.xp, 0)
        self.db.rollback()

    def test_negative_points_blocked_if_insufficient(self):
        _, profile = self._create_user_and_profile()
        service = GamificationService(self.db)
        with self.assertRaises(ValueError):
            service.award_points(
                profile_id=profile.id, source="raffle_ticket", amount=-50,
            )
        self.db.rollback()

    def test_badges_auto_unlock(self):
        _, profile = self._create_user_and_profile()
        service = GamificationService(self.db)
        service.ensure_default_badges()
        self.db.flush()

        # Concluir 1 negociação deve dar badge "first_negotiation"
        service.award_points(
            profile_id=profile.id,
            source="negotiation_completed",
            reference_id="neg-1",
        )
        self.db.flush()
        badges = service.get_user_badges(profile.id)
        badge_codes = {ub.badge.code for ub in badges}
        self.assertIn("first_negotiation", badge_codes)
        self.db.rollback()

    def test_leaderboard(self):
        _, p1 = self._create_user_and_profile("lb1")
        _, p2 = self._create_user_and_profile("lb2")
        service = GamificationService(self.db)
        service.award_points(profile_id=p1.id, source="bonus", amount=100)
        service.award_points(profile_id=p2.id, source="bonus", amount=200)

        lb = service.get_leaderboard(limit=10)
        self.assertGreaterEqual(len(lb), 2)
        # p2 tem mais pontos, deve vir primeiro
        self.assertEqual(lb[0]["profile_id"], str(p2.id))
        self.assertEqual(lb[0]["rank"], 1)
        self.db.rollback()

    def test_point_history(self):
        _, profile = self._create_user_and_profile()
        service = GamificationService(self.db)
        service.award_points(profile_id=profile.id, source="bonus", amount=10)
        service.award_points(profile_id=profile.id, source="bonus", amount=20)
        self.db.flush()

        history = service.get_point_history(profile.id)
        self.assertEqual(len(history), 2)
        # Verificar que ambos os valores estão presentes
        amounts = {h.amount for h in history}
        self.assertEqual(amounts, {10, 20})
        self.db.rollback()


class TestGamificationAPI(unittest.TestCase):
    """Testes de integração das rotas de gamificação."""

    @classmethod
    def setUpClass(cls):
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    @staticmethod
    def _auth_headers(user: User) -> dict[str, str]:
        token = create_access_token({"user_id": user.id, "email": user.email})
        return {"Authorization": f"Bearer {token}"}

    def _seed_user(self):
        db = SessionLocal()
        suffix = uuid4().hex[:8]
        user = User(
            name="API Gamer",
            email=f"apigamer_{suffix}@test.local",
            password="x",
            role="admin",
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        db.flush()
        profile = Profile(
            user_id=user.id,
            profile_type="producer",
            validation_status="approved",
        )
        db.add(profile)
        db.commit()
        db.refresh(user)
        db.refresh(profile)
        db.close()
        return user, profile

    def test_get_my_gamification(self):
        user, _ = self._seed_user()
        resp = self.client.get("/api/gamification/me", headers=self._auth_headers(user))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_points"], 0)
        self.assertEqual(data["level"], 1)

    def test_leaderboard_endpoint(self):
        resp = self.client.get("/api/gamification/leaderboard")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_badges_list(self):
        resp = self.client.get("/api/gamification/badges")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_admin_seed_badges(self):
        user, _ = self._seed_user()
        resp = self.client.post(
            "/api/gamification/admin/badges/seed",
            headers=self._auth_headers(user),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("created", data)

    def test_admin_adjust_points(self):
        user, profile = self._seed_user()
        resp = self.client.post(
            f"/api/gamification/admin/profiles/{profile.id}/adjust",
            json={"amount": 75, "description": "Teste admin"},
            headers=self._auth_headers(user),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["amount"], 75)

        # Verificar que o saldo atualizou
        resp2 = self.client.get("/api/gamification/me", headers=self._auth_headers(user))
        self.assertEqual(resp2.json()["total_points"], 75)

    def test_my_point_history(self):
        user, profile = self._seed_user()
        # Criar pontos primeiro
        self.client.post(
            f"/api/gamification/admin/profiles/{profile.id}/adjust",
            json={"amount": 30, "description": "Hist test"},
            headers=self._auth_headers(user),
        )
        resp = self.client.get("/api/gamification/me/points", headers=self._auth_headers(user))
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()), 1)

    def test_my_badges(self):
        user, _ = self._seed_user()
        resp = self.client.get("/api/gamification/me/badges", headers=self._auth_headers(user))
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)


if __name__ == "__main__":
    unittest.main()
