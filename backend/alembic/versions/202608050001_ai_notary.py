"""AI Notary registry and claim references

Revision ID: 202608050001
Revises: 202608040001
Create Date: 2026-08-05 21:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "202608050001"
down_revision = "202608040001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notary_registries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("network", sa.String(), nullable=False),
        sa.Column("contract_address", sa.String(), nullable=True),
        sa.Column("deploy_tx_hash", sa.String(), nullable=True),
        sa.Column("consensus_tx_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("source_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "user_id",
        "network",
        "contract_address",
        "deploy_tx_hash",
        "consensus_tx_id",
        "status",
    ):
        op.create_index(
            op.f(f"ix_notary_registries_{column}"),
            "notary_registries",
            [column],
            unique=False,
        )

    op.create_table(
        "notary_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("registry_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.String(), nullable=False),
        sa.Column("spec_json", sa.Text(), nullable=False),
        sa.Column("submit_tx_hash", sa.String(), nullable=True),
        sa.Column("submit_consensus_tx_id", sa.String(), nullable=True),
        sa.Column("evaluate_tx_hash", sa.String(), nullable=True),
        sa.Column("evaluate_consensus_tx_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("verdict", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["registry_id"], ["notary_registries.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("registry_id", "claim_id", name="uq_notary_claim_registry_id"),
    )
    for column in (
        "registry_id",
        "user_id",
        "claim_id",
        "submit_tx_hash",
        "submit_consensus_tx_id",
        "evaluate_tx_hash",
        "evaluate_consensus_tx_id",
        "status",
        "verdict",
    ):
        op.create_index(
            op.f(f"ix_notary_claims_{column}"),
            "notary_claims",
            [column],
            unique=False,
        )


def downgrade():
    for column in (
        "verdict",
        "status",
        "evaluate_consensus_tx_id",
        "evaluate_tx_hash",
        "submit_consensus_tx_id",
        "submit_tx_hash",
        "claim_id",
        "user_id",
        "registry_id",
    ):
        op.drop_index(op.f(f"ix_notary_claims_{column}"), table_name="notary_claims")
    op.drop_table("notary_claims")

    for column in (
        "status",
        "consensus_tx_id",
        "deploy_tx_hash",
        "contract_address",
        "network",
        "user_id",
    ):
        op.drop_index(op.f(f"ix_notary_registries_{column}"), table_name="notary_registries")
    op.drop_table("notary_registries")
