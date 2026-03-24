from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.llm_client import LLMClient
from app.models.ai_models import AISuggestion


class ServiceRecommendationAI:
    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMClient()

    def recommend(self, *, user_id: int, crop_type: str, region: str, season: str) -> list[dict]:
        crop = crop_type.strip().lower()
        season_norm = season.strip().lower()

        catalog = [
            {
                "service": "Análise de solo e correção nutricional",
                "timing": "7-15 dias antes do plantio",
                "applies": ["cafe", "soja", "milho", "uva", "citros"],
            },
            {
                "service": "Pulverização preventiva inteligente",
                "timing": "início do ciclo vegetativo",
                "applies": ["soja", "milho", "tomate", "citros"],
            },
            {
                "service": "Irrigação de precisão e telemetria",
                "timing": "monitoramento contínuo",
                "applies": ["frutas", "hortalicas", "uva", "citros"],
            },
            {
                "service": "Planejamento de colheita e logística",
                "timing": "30 dias antes da colheita",
                "applies": ["frutas", "cafe", "soja", "milho", "uva"],
            },
        ]

        picks = [item for item in catalog if any(term in crop for term in item["applies"])]
        if not picks:
            picks = catalog[:2]

        enriched = []
        for item in picks:
            recommendation = {
                "service": item["service"],
                "timing": item["timing"],
                "context": f"{region} | estação: {season_norm}",
            }
            enriched.append(recommendation)

            self.db.add(
                AISuggestion(
                    user_id=user_id,
                    module="service_recommendation",
                    suggestion_type="service_timing",
                    title="Serviço recomendado para sua lavoura",
                    content=f"{item['service']} ({item['timing']}).",
                    priority="high" if season_norm in {"primavera", "verao"} else "medium",
                    confidence=0.78,
                    meta_json={"crop_type": crop_type, "region": region, "season": season},
                )
            )

        llm_output = self.llm.complete_json(
            system_prompt=(
                "Você é um agrônomo digital. Retorne JSON com chave recommendations "
                "como lista de objetos com service, timing, context."
            ),
            user_prompt=(
                f"cultura={crop_type}; região={region}; estação={season}. "
                f"Sugestões base: {enriched}"
            ),
            fallback={"recommendations": enriched},
        )

        self.db.commit()

        llm_recommendations = llm_output.get("recommendations")
        if isinstance(llm_recommendations, list) and llm_recommendations:
            return llm_recommendations

        return enriched
