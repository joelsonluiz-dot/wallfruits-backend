"""
Serviço de retenção e expurgo de arquivos de contrato.
- Limita número máximo de versões mantidas por contrato
- Remove arquivos de disco para versões expiradas
- Endpoint de limpeza de arquivos órfãos
"""
import logging
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.intermediation_contract import IntermediationContract
from app.models.intermediation_contract_version import IntermediationContractVersion

logger = logging.getLogger("contract_retention")

CONTRACTS_DIR = Path("uploads") / "contracts"


def _extract_filename_from_url(file_url: str) -> str | None:
    """Extrai apenas o nome do arquivo (último segmento) da URL interna."""
    if not file_url:
        return None
    parts = file_url.rstrip("/").split("/")
    return parts[-1] if parts else None


def purge_old_versions(
    db: Session,
    *,
    contract_id,
    max_versions: int | None = None,
) -> int:
    """
    Remove versões antigas de um contrato que excedem o limite de retenção.
    Deleta os arquivos correspondentes do disco.

    Retorna o número de versões removidas.
    """
    limit = max_versions if max_versions is not None else settings.CONTRACT_MAX_RETAINED_VERSIONS

    if limit <= 0:
        return 0

    total_versions = (
        db.query(func.count(IntermediationContractVersion.id))
        .filter(IntermediationContractVersion.contract_id == contract_id)
        .scalar()
        or 0
    )

    if total_versions <= limit:
        return 0

    # Manter as N versões mais recentes (maior version_number)
    versions_to_keep = (
        db.query(IntermediationContractVersion.id)
        .filter(IntermediationContractVersion.contract_id == contract_id)
        .order_by(IntermediationContractVersion.version_number.desc())
        .limit(limit)
        .subquery()
    )

    # Buscar versões a deletar (que NÃO estão no top N)
    old_versions = (
        db.query(IntermediationContractVersion)
        .filter(
            IntermediationContractVersion.contract_id == contract_id,
            ~IntermediationContractVersion.id.in_(
                db.query(versions_to_keep.c.id)
            ),
        )
        .all()
    )

    # Coletar URLs atuais dos contratos ativos para não deletar arquivo em uso
    current_contract = (
        db.query(IntermediationContract.file_url)
        .filter(IntermediationContract.id == contract_id)
        .scalar()
    )
    active_urls = {current_contract} if current_contract else set()

    # Coletar URLs das versões mantidas
    kept_urls = {
        row[0]
        for row in db.query(IntermediationContractVersion.file_url)
        .filter(
            IntermediationContractVersion.contract_id == contract_id,
            IntermediationContractVersion.id.in_(
                db.query(versions_to_keep.c.id)
            ),
        )
        .all()
    }
    active_urls.update(kept_urls)

    removed = 0
    for version in old_versions:
        # Só remove arquivo do disco se nenhuma versão ativa usa a mesma URL
        if version.file_url and version.file_url not in active_urls:
            filename = _extract_filename_from_url(version.file_url)
            if filename:
                file_path = CONTRACTS_DIR / filename
                if file_path.exists():
                    try:
                        file_path.unlink()
                        logger.info("Arquivo expirado removido: %s", filename)
                    except OSError as exc:
                        logger.warning("Falha ao remover arquivo %s: %s", filename, exc)

        db.delete(version)
        removed += 1

    if removed:
        db.flush()
        logger.info(
            "Expurgo de contrato %s: %d versões removidas (limite: %d)",
            contract_id,
            removed,
            limit,
        )

    return removed


def cleanup_orphan_files(db: Session) -> dict[str, int]:
    """
    Remove arquivos de disco em uploads/contracts/ que não são referenciados
    por nenhum contrato ou versão no banco de dados.

    Retorna estatísticas: {"checked": N, "removed": N, "kept": N}.
    """
    if not CONTRACTS_DIR.exists():
        return {"checked": 0, "removed": 0, "kept": 0}

    # Coletar todas as URLs ativas (contratos + versões)
    contract_urls = {
        row[0]
        for row in db.query(IntermediationContract.file_url).all()
        if row[0]
    }
    version_urls = {
        row[0]
        for row in db.query(IntermediationContractVersion.file_url).all()
        if row[0]
    }

    # Extrair nomes de arquivo das URLs
    active_filenames: set[str] = set()
    for url in contract_urls | version_urls:
        fname = _extract_filename_from_url(url)
        if fname:
            active_filenames.add(fname)

    checked = 0
    removed = 0
    for file_path in CONTRACTS_DIR.iterdir():
        if not file_path.is_file():
            continue
        checked += 1
        if file_path.name not in active_filenames:
            try:
                file_path.unlink()
                removed += 1
                logger.info("Arquivo órfão removido: %s", file_path.name)
            except OSError as exc:
                logger.warning("Falha ao remover órfão %s: %s", file_path.name, exc)

    kept = checked - removed
    logger.info(
        "Limpeza de órfãos: %d verificados, %d removidos, %d mantidos",
        checked,
        removed,
        kept,
    )
    return {"checked": checked, "removed": removed, "kept": kept}
