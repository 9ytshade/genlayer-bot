"""workflow deployments

Revision ID: 202607280001
Revises: 202605270001
Create Date: 2026-07-28 00:01:00
"""

from alembic import op
import sqlalchemy as sa

revision = "202607280001"
down_revision = "202605270001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workflow_deployments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("workflow_type", sa.String(), nullable=False),
        sa.Column("network", sa.String(), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("contract_address", sa.String(), nullable=True),
        sa.Column("deploy_tx_hash", sa.String(), nullable=True),
        sa.Column("consensus_tx_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("last_action", sa.String(), nullable=True),
        sa.Column("last_action_tx_hash", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_deployments_contract_address"), "workflow_deployments", ["contract_address"], unique=False)
    op.create_index(op.f("ix_workflow_deployments_deploy_tx_hash"), "workflow_deployments", ["deploy_tx_hash"], unique=False)
    op.create_index(op.f("ix_workflow_deployments_id"), "workflow_deployments", ["id"], unique=False)
    op.create_index(op.f("ix_workflow_deployments_user_id"), "workflow_deployments", ["user_id"], unique=False)
    op.create_index(op.f("ix_workflow_deployments_workflow_type"), "workflow_deployments", ["workflow_type"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_workflow_deployments_workflow_type"), table_name="workflow_deployments")
    op.drop_index(op.f("ix_workflow_deployments_user_id"), table_name="workflow_deployments")
    op.drop_index(op.f("ix_workflow_deployments_id"), table_name="workflow_deployments")
    op.drop_index(op.f("ix_workflow_deployments_deploy_tx_hash"), table_name="workflow_deployments")
    op.drop_index(op.f("ix_workflow_deployments_contract_address"), table_name="workflow_deployments")
    op.drop_table("workflow_deployments")
