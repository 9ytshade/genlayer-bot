"""chat history

Revision ID: 202605270001
Revises: 202605260001
Create Date: 2026-05-27 00:01:00
"""

from alembic import op
import sqlalchemy as sa

revision = "202605270001"
down_revision = "202605260001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chat_histories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_histories_id"), "chat_histories", ["id"], unique=False)
    op.create_index(op.f("ix_chat_histories_user_id"), "chat_histories", ["user_id"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_chat_histories_user_id"), table_name="chat_histories")
    op.drop_index(op.f("ix_chat_histories_id"), table_name="chat_histories")
    op.drop_table("chat_histories")
