"""initial schema

Revision ID: 202605260001
Revises:
Create Date: 2026-05-26 00:01:00
"""

from alembic import op
import sqlalchemy as sa

revision = "202605260001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("connected_wallet_address", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_connected_wallet_address"), "users", ["connected_wallet_address"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_connected_wallet_address"), table_name="users")
    op.drop_table("users")
