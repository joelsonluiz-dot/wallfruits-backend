from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SuggestionItem(BaseModel):
    module: str
    suggestion_type: str
    title: str
    content: str
    priority: str = "medium"
    confidence: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AISuggestionsResponse(BaseModel):
    generated_at: datetime
    items: list[SuggestionItem]


class PredictRequest(BaseModel):
    module: str = Field(..., pattern="^(negotiation|service_duration|engagement)$")
    payload: dict[str, Any] = Field(default_factory=dict)


class PredictResponse(BaseModel):
    module: str
    prediction: dict[str, Any]
    confidence: float


class RecommendationRequest(BaseModel):
    crop_type: str = Field(..., min_length=2, max_length=80)
    region: str = Field(..., min_length=2, max_length=100)
    season: str = Field(..., min_length=2, max_length=60)


class RecommendationResponse(BaseModel):
    recommendations: list[dict[str, Any]]


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default="default", max_length=80)


class ChatResponse(BaseModel):
    response: str
    intent: str
    actions: list[dict[str, Any]]
    automation_triggered: bool


class TrainModelsResponse(BaseModel):
    success: bool
    details: dict[str, Any]
