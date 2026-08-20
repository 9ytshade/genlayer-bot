"""Bind prepared transaction identity and calldata integrity.

Revision ID: 202608130001
Revises: 202608050001
Create Date: 2026-08-13 00:01:00
"""

import hashlib

from alembic import op
import sqlalchemy as sa


revision = "202608130001"
down_revision = "202608050001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("prepared_transactions", sa.Column("calldata_hash", sa.String(), nullable=True))
    op.add_column(
        "prepared_transactions",
        sa.Column("intent_version", sa.Integer(), nullable=False, server_default="1"),
    )
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, data FROM prepared_transactions")).fetchall()
    for row in rows:
        digest = "0x" + hashlib.sha256(str(row.data or "0x").lower().encode("ascii")).hexdigest()
        bind.execute(
            sa.text("UPDATE prepared_transactions SET calldata_hash = :digest WHERE id = :id"),
            {"digest": digest, "id": row.id},
        )
    with op.batch_alter_table("prepared_transactions") as batch:
        batch.alter_column("calldata_hash", existing_type=sa.String(), nullable=False)
        batch.alter_column("intent_version", existing_type=sa.Integer(), server_default=None)
        batch.create_index("ix_prepared_transactions_calldata_hash", ["calldata_hash"], unique=False)


def downgrade():
    with op.batch_alter_table("prepared_transactions") as batch:
        batch.drop_index("ix_prepared_transactions_calldata_hash")
        batch.drop_column("intent_version")
        batch.drop_column("calldata_hash")
