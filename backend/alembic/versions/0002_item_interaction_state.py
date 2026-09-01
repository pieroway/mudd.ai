"""Add deterministic item interaction state.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "items", sa.Column("can_open", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "items", sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "items", sa.Column("can_use", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("items", sa.Column("use_message", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_items_open_requires_capability", "items", "NOT is_open OR can_open"
    )
    op.alter_column("items", "can_open", server_default=None)
    op.alter_column("items", "is_open", server_default=None)
    op.alter_column("items", "can_use", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_items_open_requires_capability", "items", type_="check")
    op.drop_column("items", "use_message")
    op.drop_column("items", "can_use")
    op.drop_column("items", "is_open")
    op.drop_column("items", "can_open")
