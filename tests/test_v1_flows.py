import unittest
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth.jwt_handler import create_access_token
from app.database.connection import SessionLocal
from app.main import app
from app.models.offer import Offer
from app.models.profile import Profile
from app.models.subscription import Subscription
from app.models.user import User


class V1FlowsTestCase(unittest.TestCase):
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

    def _seed_scenario(self, *, include_extra_reporters: bool = False):
        db = SessionLocal()
        suffix = uuid4().hex[:10]

        seller = User(
            name="Seller V1",
            email=f"seller_v1_{suffix}@test.local",
            password="x",
            role="producer",
            is_active=True,
        )
        buyer = User(
            name="Buyer V1",
            email=f"buyer_v1_{suffix}@test.local",
            password="x",
            role="buyer",
            is_active=True,
        )
        admin = User(
            name="Admin V1",
            email=f"admin_v1_{suffix}@test.local",
            password="x",
            role="admin",
            is_active=True,
            is_superuser=True,
        )

        users = [seller, buyer, admin]
        if include_extra_reporters:
            users.extend(
                [
                    User(
                        name="Reporter Two",
                        email=f"report2_v1_{suffix}@test.local",
                        password="x",
                        role="buyer",
                        is_active=True,
                    ),
                    User(
                        name="Reporter Three",
                        email=f"report3_v1_{suffix}@test.local",
                        password="x",
                        role="buyer",
                        is_active=True,
                    ),
                ]
            )

        db.add_all(users)
        db.commit()
        for user in users:
            db.refresh(user)

        seller_profile = Profile(
            user_id=seller.id,
            profile_type="producer",
            validation_status="approved",
        )
        db.add(seller_profile)
        db.commit()
        db.refresh(seller_profile)

        buyer_subscription = Subscription(
            user_id=buyer.id,
            plan_type="premium",
            status="active",
            auto_renew=True,
        )
        db.add(buyer_subscription)

        offer = Offer(
            user_id=seller.id,
            owner_profile_id=seller_profile.id,
            product_name="Oferta V1 Flows",
            quantity=Decimal("150"),
            price=Decimal("7.20"),
            unit="kg",
            status="active",
            visibility="public",
            min_order=Decimal("5"),
        )
        db.add(offer)
        db.commit()
        db.refresh(offer)

        extra_reporters = users[3:] if include_extra_reporters else []

        return {
            "db": db,
            "seller": seller,
            "seller_profile": seller_profile,
            "buyer": buyer,
            "admin": admin,
            "offer": offer,
            "extra_reporters": extra_reporters,
        }

    def test_negotiation_crud_update_and_delete(self):
        ctx = self._seed_scenario()
        db = ctx["db"]
        buyer_headers = self._auth_headers(ctx["buyer"])

        try:
            create_resp = self.client.post(
                "/api/negotiations/",
                json={
                    "offer_id": str(ctx["offer"].id),
                    "proposed_price": "6.80",
                    "quantity": "8",
                    "is_intermediated": False,
                    "initial_message": "abrindo negociação para teste CRUD",
                },
                headers=buyer_headers,
            )
            self.assertEqual(201, create_resp.status_code)
            negotiation_id = create_resp.json()["id"]

            update_resp = self.client.put(
                f"/api/negotiations/{negotiation_id}",
                json={
                    "proposed_price": "6.55",
                    "quantity": "10",
                },
                headers=buyer_headers,
            )
            self.assertEqual(200, update_resp.status_code)
            self.assertEqual("6.55", str(update_resp.json()["proposed_price"]))
            self.assertEqual("10.00", str(update_resp.json()["quantity"]))

            delete_resp = self.client.delete(
                f"/api/negotiations/{negotiation_id}",
                headers=buyer_headers,
            )
            self.assertEqual(204, delete_resp.status_code)

            not_found_resp = self.client.get(
                f"/api/negotiations/{negotiation_id}",
                headers=buyer_headers,
            )
            self.assertEqual(404, not_found_resp.status_code)
        finally:
            db.close()

    def test_intermediation_contract_flow(self):
        ctx = self._seed_scenario()
        db = ctx["db"]
        buyer_headers = self._auth_headers(ctx["buyer"])
        seller_headers = self._auth_headers(ctx["seller"])
        admin_headers = self._auth_headers(ctx["admin"])

        try:
            neg_resp = self.client.post(
                "/api/negotiations/",
                json={
                    "offer_id": str(ctx["offer"].id),
                    "proposed_price": "6.85",
                    "quantity": "12",
                    "is_intermediated": False,
                    "initial_message": "negociacao para fluxo de contrato",
                },
                headers=buyer_headers,
            )
            self.assertEqual(201, neg_resp.status_code)
            negotiation_id = neg_resp.json()["id"]

            accept_resp = self.client.patch(
                f"/api/negotiations/{negotiation_id}/status",
                json={"status": "accepted"},
                headers=seller_headers,
            )
            self.assertEqual(200, accept_resp.status_code)

            request_resp = self.client.post(
                f"/api/negotiations/{negotiation_id}/intermediation",
                json={"notes": "solicito mediacao no fechamento"},
                headers=buyer_headers,
            )
            self.assertEqual(201, request_resp.status_code)
            request_id = request_resp.json()["id"]

            review_resp = self.client.patch(
                f"/api/negotiations/intermediation/requests/{request_id}",
                json={"status": "validada", "review_notes": "validacao administrativa"},
                headers=admin_headers,
            )
            self.assertEqual(200, review_resp.status_code)
            self.assertEqual("validada", review_resp.json()["status"])

            upsert_resp = self.client.post(
                f"/api/negotiations/intermediation/requests/{request_id}/contract/upload",
                data={"notes": "contrato anexado para auditoria"},
                files={
                    "file": (
                        "v1-flow-contract.pdf",
                        b"%PDF-1.4 contrato de teste wallfruits",
                        "application/pdf",
                    )
                },
                headers=buyer_headers,
            )
            self.assertEqual(200, upsert_resp.status_code)
            self.assertEqual("v1-flow-contract.pdf", upsert_resp.json()["file_name"])
            self.assertIn("/contract/file/", upsert_resp.json()["file_url"])

            download_resp = self.client.get(
                upsert_resp.json()["file_url"],
                headers=admin_headers,
            )
            self.assertEqual(200, download_resp.status_code)
            self.assertGreater(len(download_resp.content), 0)

            versions_resp = self.client.get(
                f"/api/negotiations/intermediation/requests/{request_id}/contract/versions",
                headers=admin_headers,
            )
            self.assertEqual(200, versions_resp.status_code)
            versions_payload = versions_resp.json()
            self.assertEqual(1, len(versions_payload))
            self.assertEqual(1, versions_payload[0]["version_number"])

            second_upsert_resp = self.client.post(
                f"/api/negotiations/intermediation/requests/{request_id}/contract/upload",
                data={"notes": "contrato atualizado com aditivo"},
                files={
                    "file": (
                        "v1-flow-contract-v2.pdf",
                        b"%PDF-1.4 contrato de teste wallfruits v2",
                        "application/pdf",
                    )
                },
                headers=buyer_headers,
            )
            self.assertEqual(200, second_upsert_resp.status_code)
            self.assertEqual("v1-flow-contract-v2.pdf", second_upsert_resp.json()["file_name"])

            versions_resp = self.client.get(
                f"/api/negotiations/intermediation/requests/{request_id}/contract/versions",
                headers=admin_headers,
            )
            self.assertEqual(200, versions_resp.status_code)
            versions_payload = versions_resp.json()
            self.assertGreaterEqual(len(versions_payload), 2)
            self.assertEqual(2, versions_payload[0]["version_number"])
            self.assertEqual(1, versions_payload[1]["version_number"])
            self.assertEqual("v1-flow-contract-v2.pdf", versions_payload[0]["file_name"])
            self.assertEqual("v1-flow-contract.pdf", versions_payload[1]["file_name"])

            old_version_download = self.client.get(
                versions_payload[1]["file_url"],
                headers=admin_headers,
            )
            self.assertEqual(200, old_version_download.status_code)
            self.assertGreater(len(old_version_download.content), 0)

            get_resp = self.client.get(
                f"/api/negotiations/intermediation/requests/{request_id}/contract",
                headers=admin_headers,
            )
            self.assertEqual(200, get_resp.status_code)
            contract = get_resp.json()
            self.assertIn("/contract/file/", contract["file_url"])
            self.assertEqual(ctx["buyer"].id, contract["uploaded_by_user_id"])
        finally:
            db.close()

    def test_intermediated_negotiation_requires_contract_to_complete(self):
        ctx = self._seed_scenario()
        db = ctx["db"]
        buyer_headers = self._auth_headers(ctx["buyer"])
        seller_headers = self._auth_headers(ctx["seller"])
        admin_headers = self._auth_headers(ctx["admin"])

        try:
            neg_resp = self.client.post(
                "/api/negotiations/",
                json={
                    "offer_id": str(ctx["offer"].id),
                    "proposed_price": "6.70",
                    "quantity": "9",
                    "is_intermediated": False,
                    "initial_message": "teste de bloqueio sem contrato",
                },
                headers=buyer_headers,
            )
            self.assertEqual(201, neg_resp.status_code)
            negotiation_id = neg_resp.json()["id"]

            accept_resp = self.client.patch(
                f"/api/negotiations/{negotiation_id}/status",
                json={"status": "accepted"},
                headers=seller_headers,
            )
            self.assertEqual(200, accept_resp.status_code)

            request_resp = self.client.post(
                f"/api/negotiations/{negotiation_id}/intermediation",
                json={"notes": "solicito mediacao obrigatoria"},
                headers=buyer_headers,
            )
            self.assertEqual(201, request_resp.status_code)
            request_id = request_resp.json()["id"]

            review_resp = self.client.patch(
                f"/api/negotiations/intermediation/requests/{request_id}",
                json={"status": "validada", "review_notes": "ok"},
                headers=admin_headers,
            )
            self.assertEqual(200, review_resp.status_code)

            blocked_complete_resp = self.client.patch(
                f"/api/negotiations/{negotiation_id}/status",
                json={"status": "completed"},
                headers=seller_headers,
            )
            self.assertEqual(400, blocked_complete_resp.status_code)
            payload = blocked_complete_resp.json()
            error_message = payload.get("error", {}).get("message", payload.get("detail", ""))
            self.assertIn("exige contrato", str(error_message).lower())

            upsert_resp = self.client.post(
                f"/api/negotiations/intermediation/requests/{request_id}/contract",
                json={
                    "file_url": "https://cdn.wallfruits.test/contracts/intermediated-required.pdf",
                    "file_name": "intermediated-required.pdf",
                    "notes": "contrato para liberar conclusao",
                },
                headers=buyer_headers,
            )
            self.assertEqual(200, upsert_resp.status_code)

            complete_resp = self.client.patch(
                f"/api/negotiations/{negotiation_id}/status",
                json={"status": "completed"},
                headers=seller_headers,
            )
            self.assertEqual(200, complete_resp.status_code)
            self.assertEqual("completed", complete_resp.json()["status"])
        finally:
            db.close()

    def test_reputation_flow_after_completed_negotiation(self):
        ctx = self._seed_scenario()
        db = ctx["db"]
        buyer_headers = self._auth_headers(ctx["buyer"])
        seller_headers = self._auth_headers(ctx["seller"])

        try:
            neg_resp = self.client.post(
                "/api/negotiations/",
                json={
                    "offer_id": str(ctx["offer"].id),
                    "proposed_price": "6.90",
                    "quantity": "10",
                    "is_intermediated": False,
                    "initial_message": "fluxo reputacao",
                },
                headers=buyer_headers,
            )
            self.assertEqual(201, neg_resp.status_code)
            negotiation_id = neg_resp.json()["id"]

            accept_resp = self.client.patch(
                f"/api/negotiations/{negotiation_id}/status",
                json={"status": "accepted"},
                headers=seller_headers,
            )
            self.assertEqual(200, accept_resp.status_code)

            complete_resp = self.client.patch(
                f"/api/negotiations/{negotiation_id}/status",
                json={"status": "completed"},
                headers=seller_headers,
            )
            self.assertEqual(200, complete_resp.status_code)
            self.assertEqual("completed", complete_resp.json()["status"])

            review_resp = self.client.post(
                "/api/reputation/reviews",
                json={
                    "negotiation_id": negotiation_id,
                    "rating": 5,
                    "comment": "fechamento excelente",
                },
                headers=buyer_headers,
            )
            self.assertEqual(201, review_resp.status_code)
            self.assertEqual(5, review_resp.json()["rating"])

            seller_profile = db.query(Profile).filter(Profile.user_id == ctx["seller"].id).first()
            self.assertIsNotNone(seller_profile)

            summary_resp = self.client.get(f"/api/reputation/profiles/{seller_profile.id}/summary")
            self.assertEqual(200, summary_resp.status_code)
            summary = summary_resp.json()
            self.assertEqual(1, summary["total_reviews"])
            self.assertEqual(5.0, summary["average_rating"])
            distribution = summary["rating_distribution"]
            rating_5_count = distribution.get("5", distribution.get(5))
            self.assertEqual(1, rating_5_count)
        finally:
            db.close()

    def test_reports_flow_with_auto_suspension(self):
        ctx = self._seed_scenario(include_extra_reporters=True)
        db = ctx["db"]
        buyer_headers = self._auth_headers(ctx["buyer"])
        admin_headers = self._auth_headers(ctx["admin"])
        reporter2_headers = self._auth_headers(ctx["extra_reporters"][0])
        reporter3_headers = self._auth_headers(ctx["extra_reporters"][1])

        try:
            report_responses = [
                self.client.post(
                    "/api/reports/",
                    json={
                        "reported_offer_id": str(ctx["offer"].id),
                        "reason": "Suspeita grave de fraude documental no lote anunciado",
                    },
                    headers=buyer_headers,
                ),
                self.client.post(
                    "/api/reports/",
                    json={
                        "reported_offer_id": str(ctx["offer"].id),
                        "reason": "Possivel golpe com informacao falsa para pagamento",
                    },
                    headers=reporter2_headers,
                ),
                self.client.post(
                    "/api/reports/",
                    json={
                        "reported_offer_id": str(ctx["offer"].id),
                        "reason": "Tentativa de estelionato no fechamento da compra",
                    },
                    headers=reporter3_headers,
                ),
            ]

            for response in report_responses:
                self.assertEqual(201, response.status_code)

            report_ids = [response.json()["id"] for response in report_responses]

            seller_profile = db.query(Profile).filter(Profile.user_id == ctx["seller"].id).first()
            self.assertIsNotNone(seller_profile)
            db.refresh(seller_profile)
            self.assertEqual("suspended", seller_profile.validation_status)
            self.assertIn("AUTO_SUSPENSAO", seller_profile.validation_notes or "")

            pending_resp = self.client.get("/api/reports/?status=pending", headers=admin_headers)
            self.assertEqual(200, pending_resp.status_code)
            pending_reports = pending_resp.json()
            pending_ids = {item["id"] for item in pending_reports}
            for report_id in report_ids:
                self.assertIn(report_id, pending_ids)

            review_resp = self.client.patch(
                f"/api/reports/{report_ids[0]}",
                json={"status": "under_review", "resolution_notes": "analise iniciada"},
                headers=admin_headers,
            )
            self.assertEqual(200, review_resp.status_code)
            self.assertEqual("under_review", review_resp.json()["status"])
            self.assertEqual(ctx["admin"].id, review_resp.json()["reviewed_by_user_id"])
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)