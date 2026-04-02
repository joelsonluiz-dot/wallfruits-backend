"""create reports table if not exists

Revision ID: 20260401_01
Revises: 20260324_01
Create Date: 2026-04-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260401_01"
down_revision = "20260324_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the reports table if it doesn't exist
    # This table may have been auto-created in earlier versions via create_all()
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporter_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reported_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reported_offer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["reporter_profile_id"], ["profiles.id"], ),
        sa.ForeignKeyConstraint(["reported_profile_id"], ["profiles.id"], ),
        sa.ForeignKeyConstraint(["reported_offer_id"], ["offers.id"], ),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reports_id", "reports", ["id"], unique=False)
    op.create_index("ix_reports_reporter_profile_id", "reports", ["reporter_profile_id"], unique=False)
    op.create_index("ix_reports_reported_profile_id", "reports", ["reported_profile_id"], unique=False)
    op.create_index("ix_reports_reported_offer_id", "reports", ["reported_offer_id"], unique=False)
    op.create_index("ix_reports_status", "reports", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_index("ix_reports_reported_offer_id", table_name="reports")
    op.drop_index("ix_reports_reported_profile_id", table_name="reports")
    op.drop_index("ix_reports_reporter_profile_id", table_name="reports")
    op.drop_index("ix_reports_id", table_name="reports")
    op.drop_table("reports")
