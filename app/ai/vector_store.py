from __future__ import annotations

from math import sqrt
from typing import Any

from sqlalchemy.orm import Session

from app.models.ai_models import EmbeddingRecord


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    size = min(len(a), len(b))
    if size == 0:
        return 0.0

    dot = sum(float(a[i]) * float(b[i]) for i in range(size))
    norm_a = sqrt(sum(float(a[i]) ** 2 for i in range(size)))
    norm_b = sqrt(sum(float(b[i]) ** 2 for i in range(size)))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingStore:
    """Store vetorial simples (JSON) pronto para migração posterior para PGVector/FAISS."""

    def __init__(self, db: Session):
        self.db = db

    def upsert(
        self,
        *,
        source_type: str,
        source_id: str,
        vector: list[float],
        content: str,
        model: str = "local-tfidf",
        metadata: dict[str, Any] | None = None,
    ) -> EmbeddingRecord:
        row = (
            self.db.query(EmbeddingRecord)
            .filter(
                EmbeddingRecord.source_type == source_type,
                EmbeddingRecord.source_id == source_id,
            )
            .first()
        )
        if row is None:
            row = EmbeddingRecord(
                source_type=source_type,
                source_id=source_id,
                model=model,
                vector=[float(x) for x in vector],
                content=content,
                meta_json=metadata or {},
            )
            self.db.add(row)
        else:
            row.model = model
            row.vector = [float(x) for x in vector]
            row.content = content
            row.meta_json = metadata or {}

        return row

    def query_similar(self, *, vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        rows = self.db.query(EmbeddingRecord).all()
        scored = []
        for row in rows:
            sim = _cosine_similarity(vector, row.vector or [])
            scored.append(
                {
                    "id": row.id,
                    "source_type": row.source_type,
                    "source_id": row.source_id,
                    "content": row.content,
                    "score": float(sim),
                    "metadata": row.meta_json or {},
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[: max(1, top_k)]
