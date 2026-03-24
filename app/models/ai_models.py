from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.database.connection import Base


class UserBehaviorLog(Base):
    __tablename__ = "user_behavior_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(80), nullable=True, index=True)
    entity_id = Column(String(120), nullable=True, index=True)
    meta_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AISuggestion(Base):
    __tablename__ = "ai_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    module = Column(String(60), nullable=False, index=True)
    suggestion_type = Column(String(80), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    content = Column(Text, nullable=False)
    priority = Column(String(20), nullable=False, default="medium")
    status = Column(String(30), nullable=False, default="open", index=True)
    confidence = Column(Float, nullable=False, default=0.0)
    meta_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    module = Column(String(80), nullable=False, index=True)
    model_name = Column(String(120), nullable=False)
    target = Column(String(120), nullable=False, index=True)
    input_payload = Column(JSON, default=dict)
    prediction_payload = Column(JSON, default=dict)
    confidence = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmbeddingRecord(Base):
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(80), nullable=False, index=True)
    source_id = Column(String(120), nullable=False, index=True)
    model = Column(String(120), nullable=False, default="local-tfidf")
    # Vetor em JSON para manter compatibilidade e facilitar migração futura para pgvector/faiss.
    vector = Column(JSON, nullable=False, default=list)
    content = Column(Text, nullable=False)
    meta_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AIChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String(80), nullable=False, index=True)
    role = Column(String(20), nullable=False, index=True)
    message = Column(Text, nullable=False)
    parsed_intent = Column(String(80), nullable=True, index=True)
    automation_triggered = Column(Boolean, nullable=False, default=False)
    meta_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
