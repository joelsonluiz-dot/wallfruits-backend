"""add platform/account role columns to users

Revision ID: 20260417_01
Revises: 20260402_01
Create Date: 2026-04-17 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260417_01"
down_revision = "20260402_01"
branch_labels = None
depends_on = None


def _columns_for(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {str(col.get("name")) for col in inspector.get_columns(table_name)}


def _indexes_for(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {str(idx.get("name")) for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    columns = _columns_for("users")

    if "platform_role" not in columns:
        op.add_column(
            "users",
            sa.Column("platform_role", sa.String(length=30), nullable=False, server_default="none"),
        )

    if "account_role" not in columns:
        op.add_column(
            "users",
            sa.Column("account_role", sa.String(length=30), nullable=False, server_default="account_owner"),
        )

    if "account_scope_id" not in columns:
        op.add_column("users", sa.Column("account_scope_id", sa.String(length=64), nullable=True))

    indexes = _indexes_for("users")
    if "ix_users_platform_role" not in indexes:
        op.create_index("ix_users_platform_role", "users", ["platform_role"], unique=False)

    if "ix_users_account_role" not in indexes:
        op.create_index("ix_users_account_role", "users", ["account_role"], unique=False)

    if "ix_users_account_scope_id" not in indexes:
        op.create_index("ix_users_account_scope_id", "users", ["account_scope_id"], unique=False)

    # Legacy compatibility: promote historical role=admin users to platform staff admin.
    op.execute(
        """
        UPDATE users
        SET platform_role = 'staff_admin'
        WHERE lower(coalesce(role, '')) = 'admin'
        """
    )


def downgrade() -> None:
    indexes = _indexes_for("users")
    if "ix_users_account_scope_id" in indexes:
        op.drop_index("ix_users_account_scope_id", table_name="users")
    if "ix_users_account_role" in indexes:
        op.drop_index("ix_users_account_role", table_name="users")
    if "ix_users_platform_role" in indexes:
        op.drop_index("ix_users_platform_role", table_name="users")

    columns = _columns_for("users")
    if "account_scope_id" in columns:
        op.drop_column("users", "account_scope_id")
    if "account_role" in columns:
        op.drop_column("users", "account_role")
    if "platform_role" in columns:
        op.drop_column("users", "platform_role")
