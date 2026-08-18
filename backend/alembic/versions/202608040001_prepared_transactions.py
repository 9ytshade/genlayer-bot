"""prepared transaction intent envelopes

Revision ID: 202608040001
Revises: 202607280001
Create Date: 2026-08-04 00:01:00
"""

from alembic import op
import sqlalchemy as sa


revision = "202608040001"
down_revision = "202607280001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "prepared_transactions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("network", sa.String(), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("sender_address", sa.String(), nullable=False),
        sa.Column("to_address", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("value_wei", sa.String(), nullable=False),
        sa.Column("gas_limit", sa.Integer(), nullable=False),
        sa.Column("nonce", sa.Integer(), nullable=False),
        sa.Column("gas_price", sa.String(), nullable=True),
        sa.Column("max_fee_per_gas", sa.String(), nullable=True),
        sa.Column("max_priority_fee_per_gas", sa.String(), nullable=True),
        sa.Column("consensus_max_rotations", sa.Integer(), nullable=True),
        sa.Column("leader_only", sa.Boolean(), nullable=False),
        sa.Column("intent_json", sa.Text(), nullable=False),
        sa.Column("intent_hash", sa.String(), nullable=False),
        sa.Column("consensus_tx_id", sa.String(), nullable=True),
        sa.Column("tx_hash", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prepared_transactions_action"), "prepared_transactions", ["action"], unique=False)
    op.create_index(op.f("ix_prepared_transactions_consensus_tx_id"), "prepared_transactions", ["consensus_tx_id"], unique=False)
    op.create_index(op.f("ix_prepared_transactions_intent_hash"), "prepared_transactions", ["intent_hash"], unique=False)
    op.create_index(op.f("ix_prepared_transactions_network"), "prepared_transactions", ["network"], unique=False)
    op.create_index(op.f("ix_prepared_transactions_sender_address"), "prepared_transactions", ["sender_address"], unique=False)
    op.create_index(op.f("ix_prepared_transactions_status"), "prepared_transactions", ["status"], unique=False)
    op.create_index(op.f("ix_prepared_transactions_tx_hash"), "prepared_transactions", ["tx_hash"], unique=True)
    op.create_index(op.f("ix_prepared_transactions_user_id"), "prepared_transactions", ["user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_prepared_transactions_user_id"), table_name="prepared_transactions")
    op.drop_index(op.f("ix_prepared_transactions_tx_hash"), table_name="prepared_transactions")
    op.drop_index(op.f("ix_prepared_transactions_status"), table_name="prepared_transactions")
    op.drop_index(op.f("ix_prepared_transactions_sender_address"), table_name="prepared_transactions")
    op.drop_index(op.f("ix_prepared_transactions_network"), table_name="prepared_transactions")
    op.drop_index(op.f("ix_prepared_transactions_intent_hash"), table_name="prepared_transactions")
    op.drop_index(op.f("ix_prepared_transactions_consensus_tx_id"), table_name="prepared_transactions")
    op.drop_index(op.f("ix_prepared_transactions_action"), table_name="prepared_transactions")
    op.drop_table("prepared_transactions")
