"""create ai tables

Revision ID: 20260324_01
Revises: 
Create Date: 2026-03-24 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260324_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_behavior_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=True),
        sa.Column("entity_id", sa.String(length=120), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_behavior_logs_id", "user_behavior_logs", ["id"], unique=False)
    op.create_index("ix_user_behavior_logs_user_id", "user_behavior_logs", ["user_id"], unique=False)
    op.create_index("ix_user_behavior_logs_event_type", "user_behavior_logs", ["event_type"], unique=False)

    op.create_table(
        "ai_suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("module", sa.String(length=60), nullable=False),
        sa.Column("suggestion_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_suggestions_id", "ai_suggestions", ["id"], unique=False)
    op.create_index("ix_ai_suggestions_user_id", "ai_suggestions", ["user_id"], unique=False)
    op.create_index("ix_ai_suggestions_module", "ai_suggestions", ["module"], unique=False)
    op.create_index("ix_ai_suggestions_suggestion_type", "ai_suggestions", ["suggestion_type"], unique=False)

    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("target", sa.String(length=120), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("prediction_payload", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_predictions_id", "predictions", ["id"], unique=False)
    op.create_index("ix_predictions_user_id", "predictions", ["user_id"], unique=False)
    op.create_index("ix_predictions_module", "predictions", ["module"], unique=False)
    op.create_index("ix_predictions_target", "predictions", ["target"], unique=False)

    op.create_table(
        "embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_embeddings_id", "embeddings", ["id"], unique=False)
    op.create_index("ix_embeddings_source_type", "embeddings", ["source_type"], unique=False)
    op.create_index("ix_embeddings_source_id", "embeddings", ["source_id"], unique=False)

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("parsed_intent", sa.String(length=80), nullable=True),
        sa.Column("automation_triggered", sa.Boolean(), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_id", "chat_messages", ["id"], unique=False)
    op.create_index("ix_chat_messages_user_id", "chat_messages", ["user_id"], unique=False)
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_user_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_embeddings_source_id", table_name="embeddings")
    op.drop_index("ix_embeddings_source_type", table_name="embeddings")
    op.drop_index("ix_embeddings_id", table_name="embeddings")
    op.drop_table("embeddings")

    op.drop_index("ix_predictions_target", table_name="predictions")
    op.drop_index("ix_predictions_module", table_name="predictions")
    op.drop_index("ix_predictions_user_id", table_name="predictions")
    op.drop_index("ix_predictions_id", table_name="predictions")
    op.drop_table("predictions")

    op.drop_index("ix_ai_suggestions_suggestion_type", table_name="ai_suggestions")
    op.drop_index("ix_ai_suggestions_module", table_name="ai_suggestions")
    op.drop_index("ix_ai_suggestions_user_id", table_name="ai_suggestions")
    op.drop_index("ix_ai_suggestions_id", table_name="ai_suggestions")
    op.drop_table("ai_suggestions")

    op.drop_index("ix_user_behavior_logs_event_type", table_name="user_behavior_logs")
    op.drop_index("ix_user_behavior_logs_user_id", table_name="user_behavior_logs")
    op.drop_index("ix_user_behavior_logs_id", table_name="user_behavior_logs")
    op.drop_table("user_behavior_logs")
