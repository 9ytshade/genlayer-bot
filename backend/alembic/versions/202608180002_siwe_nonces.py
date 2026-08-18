"""Persist single-use SIWE nonces.

Revision ID: 202608180002
Revises: 202608180001
Create Date: 2026-08-18 00:02:00
"""

from alembic import op
import sqlalchemy as sa


revision = "202608180002"
down_revision = "202608180001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "siwe_nonces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_address", sa.String(), nullable=False),
        sa.Column("nonce_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_siwe_nonces_wallet_address",
        "siwe_nonces",
        ["wallet_address"],
        unique=True,
    )
    op.create_index(
        "ix_siwe_nonces_expires_at",
        "siwe_nonces",
        ["expires_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_siwe_nonces_expires_at", table_name="siwe_nonces")
    op.drop_index("ix_siwe_nonces_wallet_address", table_name="siwe_nonces")
    op.drop_table("siwe_nonces")
