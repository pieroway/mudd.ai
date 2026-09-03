"""Add persistent light-source state to items.

Revision ID: 0004
Revises: 0003
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "items",
        sa.Column("is_light_source", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "items", sa.Column("is_lit", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.create_check_constraint(
        "ck_items_lit_requires_light_source", "items", "NOT is_lit OR is_light_source"
    )
    op.alter_column("items", "is_light_source", server_default=None)
    op.alter_column("items", "is_lit", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_items_lit_requires_light_source", "items", type_="check")
    op.drop_column("items", "is_lit")
    op.drop_column("items", "is_light_source")
