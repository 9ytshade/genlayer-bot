"""Persist canonical EVM and GenLayer lifecycle state.

Revision ID: 202608180001
Revises: 202608130001
Create Date: 2026-08-18 00:01:00
"""

from alembic import op
import sqlalchemy as sa


revision = "202608180001"
down_revision = "202608130001"
branch_labels = None
depends_on = None


LIFECYCLE_COLUMNS = (
    ("lifecycle_status", sa.String(), "PREPARED", False),
    ("evm_status", sa.String(), "NOT_BROADCAST", False),
    ("consensus_status", sa.String(), "UNINITIALIZED", False),
    ("execution_status", sa.String(), "UNKNOWN", False),
    ("final", sa.Boolean(), False, False),
    ("terminal", sa.Boolean(), False, False),
    ("appealable", sa.Boolean(), False, False),
    ("protocol_result", sa.String(), None, True),
    ("num_rounds", sa.Integer(), None, True),
    ("validator_count", sa.Integer(), None, True),
    ("vote_count", sa.Integer(), None, True),
    ("zero_round_no_majority", sa.Boolean(), False, False),
    ("diagnostic_json", sa.Text(), "{}", False),
    ("last_polled_at", sa.DateTime(), None, True),
)


def _add_columns(table_name):
    for name, column_type, default, nullable in LIFECYCLE_COLUMNS:
        kwargs = {"nullable": nullable}
        if not nullable:
            kwargs["server_default"] = sa.text(
                "1" if default is True else "0" if default is False else repr(default)
            )
        op.add_column(table_name, sa.Column(name, column_type, **kwargs))
    if table_name == "prepared_transactions":
        op.create_index(
            "ix_prepared_transactions_lifecycle_status",
            table_name,
            ["lifecycle_status"],
            unique=False,
        )
    else:
        op.create_index(
            "ix_workflow_deployments_lifecycle_status",
            table_name,
            ["lifecycle_status"],
            unique=False,
        )


def upgrade():
    _add_columns("prepared_transactions")
    _add_columns("workflow_deployments")


def _drop_columns(table_name):
    index_name = (
        "ix_prepared_transactions_lifecycle_status"
        if table_name == "prepared_transactions"
        else "ix_workflow_deployments_lifecycle_status"
    )
    with op.batch_alter_table(table_name) as batch:
        batch.drop_index(index_name)
        for name, _column_type, _default, _nullable in reversed(LIFECYCLE_COLUMNS):
            batch.drop_column(name)


def downgrade():
    _drop_columns("workflow_deployments")
    _drop_columns("prepared_transactions")
