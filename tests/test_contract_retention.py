"""
Testes para validação de arquivo e retenção de contratos.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from app.services.file_validator import validate_file_content


class TestFileValidator(unittest.TestCase):
    """Testes de magic bytes."""

    def test_valid_pdf(self):
        content = b"%PDF-1.4 rest of file..."
        self.assertTrue(validate_file_content(content, ".pdf"))

    def test_invalid_pdf_actually_exe(self):
        content = b"MZ\x90\x00\x03\x00\x00\x00"  # EXE header
        self.assertFalse(validate_file_content(content, ".pdf"))

    def test_valid_png(self):
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        self.assertTrue(validate_file_content(content, ".png"))

    def test_valid_jpg(self):
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 20
        self.assertTrue(validate_file_content(content, ".jpg"))

    def test_valid_jpeg_alias(self):
        content = b"\xff\xd8\xff\xe1" + b"\x00" * 20
        self.assertTrue(validate_file_content(content, ".jpeg"))

    def test_valid_docx(self):
        content = b"PK\x03\x04" + b"\x00" * 20
        self.assertTrue(validate_file_content(content, ".docx"))

    def test_valid_doc(self):
        content = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 20
        self.assertTrue(validate_file_content(content, ".doc"))

    def test_empty_file_rejected_for_known_type(self):
        self.assertFalse(validate_file_content(b"", ".pdf"))

    def test_unknown_extension_always_passes(self):
        content = b"anything goes"
        self.assertTrue(validate_file_content(content, ".xyz"))

    def test_case_insensitive_extension(self):
        content = b"%PDF-1.7"
        self.assertTrue(validate_file_content(content, ".PDF"))

    def test_jpg_content_named_as_png_rejected(self):
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 20
        self.assertFalse(validate_file_content(content, ".png"))


class TestContractRetention(unittest.TestCase):
    """Testes de retenção e expurgo de contratos (com DB real de teste)."""

    @classmethod
    def setUpClass(cls):
        """Preparar ambiente de teste com banco SQLite in-memory."""
        os.environ.setdefault("REDIS_ENABLED", "false")
        os.environ.setdefault("APP_ENV", "test")

        from app.database.connection import SessionLocal
        cls.SessionLocal = SessionLocal

        # Criar diretório temporário para arquivos de contrato
        cls._tmp_dir = tempfile.mkdtemp(prefix="wallfruits_test_contracts_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp_dir, ignore_errors=True)

    def _create_dummy_file(self, filename: str) -> Path:
        """Cria arquivo dummy no diretório temporário."""
        p = Path(self._tmp_dir) / filename
        p.write_bytes(b"%PDF-1.4 test content")
        return p

    def test_purge_old_versions_respects_limit(self):
        """Verifica que purge_old_versions mantém apenas N versões."""
        from app.services.contract_retention import purge_old_versions
        from app.models.intermediation_contract_version import IntermediationContractVersion

        db = self.SessionLocal()
        try:
            # Criar um contrato com muitas versões via seed
            from app.models.user import User
            from app.models.intermediation_request import IntermediationRequest
            from app.models.intermediation_contract import IntermediationContract
            from app.models.negotiation import Negotiation
            from app.models.offer import Offer
            from app.models.profile import Profile

            suffix = uuid4().hex[:8]

            user = User(
                name="Retention Test",
                email=f"retention_{suffix}@test.local",
                password="x",
                role="producer",
                is_active=True,
            )
            db.add(user)
            db.flush()

            profile = Profile(
                user_id=user.id,
                profile_type="producer",
                validation_status="approved",
            )
            db.add(profile)
            db.flush()

            offer = Offer(
                product_name="Test Offer Retention",
                description="test",
                price=100,
                user_id=user.id,
                owner_profile_id=profile.id,
                quantity=10,
                unit="kg",
                category="frutas",
                status="active",
            )
            db.add(offer)
            db.flush()

            negotiation = Negotiation(
                offer_id=offer.id,
                buyer_profile_id=profile.id,
                seller_profile_id=profile.id,
                proposed_price=90,
                quantity=5,
                status="accepted",
            )
            db.add(negotiation)
            db.flush()

            int_request = IntermediationRequest(
                negotiation_id=negotiation.id,
                requester_profile_id=profile.id,
                status="validada",
            )
            db.add(int_request)
            db.flush()

            contract = IntermediationContract(
                intermediation_request_id=int_request.id,
                file_url="/api/test/current.pdf",
                file_name="current.pdf",
                uploaded_by_user_id=user.id,
            )
            db.add(contract)
            db.flush()

            # Criar 8 versões
            for i in range(1, 9):
                fname = f"v{i}_{uuid4().hex[:8]}.pdf"
                self._create_dummy_file(fname)
                version = IntermediationContractVersion(
                    contract_id=contract.id,
                    version_number=i,
                    file_url=f"/api/test/file/{fname}",
                    file_name=f"versao_{i}.pdf",
                    uploaded_by_user_id=user.id,
                )
                db.add(version)
            db.flush()

            # Executar purge com limite de 3 (usando diretório temporário)
            with patch("app.services.contract_retention.CONTRACTS_DIR", Path(self._tmp_dir)):
                removed = purge_old_versions(db, contract_id=contract.id, max_versions=3)

            self.assertEqual(removed, 5)  # 8 - 3 = 5 removidas

            remaining = (
                db.query(IntermediationContractVersion)
                .filter(IntermediationContractVersion.contract_id == contract.id)
                .count()
            )
            self.assertEqual(remaining, 3)

            # Verificar que as 3 mantidas são as mais recentes (v6, v7, v8)
            kept_versions = (
                db.query(IntermediationContractVersion.version_number)
                .filter(IntermediationContractVersion.contract_id == contract.id)
                .order_by(IntermediationContractVersion.version_number)
                .all()
            )
            self.assertEqual([v[0] for v in kept_versions], [6, 7, 8])

        finally:
            db.rollback()
            db.close()

    def test_cleanup_orphan_files(self):
        """Verifica que cleanup remove arquivos não referenciados."""
        from app.services.contract_retention import cleanup_orphan_files

        tmp = Path(self._tmp_dir) / "orphan_test"
        tmp.mkdir(exist_ok=True)

        # Criar arquivo órfão
        orphan = tmp / "orphan_file.pdf"
        orphan.write_bytes(b"orphan data")

        # Criar arquivo "ativo" (que existiria no banco)
        active = tmp / "active_file.pdf"
        active.write_bytes(b"active data")

        db = self.SessionLocal()
        try:
            with patch("app.services.contract_retention.CONTRACTS_DIR", tmp):
                # Sem nenhum registro no banco, ambos são órfãos
                stats = cleanup_orphan_files(db)
                self.assertEqual(stats["checked"], 2)
                self.assertEqual(stats["removed"], 2)
                self.assertFalse(orphan.exists())
                self.assertFalse(active.exists())
        finally:
            db.close()

    def test_purge_no_op_when_within_limit(self):
        """Purge não faz nada se versões estão dentro do limite."""
        from app.services.contract_retention import purge_old_versions

        db = self.SessionLocal()
        try:
            # Com UUID fake que não existe — 0 versões, dentro de qualquer limite
            removed = purge_old_versions(db, contract_id=uuid4(), max_versions=5)
            self.assertEqual(removed, 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
