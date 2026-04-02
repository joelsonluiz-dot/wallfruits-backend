"""add reported_post_id to reports

Revision ID: 20260402_01
Revises: 20260324_01
Create Date: 2026-04-02 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260402_01"
down_revision = "20260401_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("reported_post_id", sa.Integer(), nullable=True))
    op.create_index("ix_reports_reported_post_id", "reports", ["reported_post_id"], unique=False)
    op.create_foreign_key(
        "fk_reports_reported_post_id_community_posts",
        "reports",
        "community_posts",
        ["reported_post_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_reports_reported_post_id_community_posts", "reports", type_="foreignkey")
    op.drop_index("ix_reports_reported_post_id", table_name="reports")
    op.drop_column("reports", "reported_post_id")
