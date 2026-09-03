"""Add persistent fuel to usable items.

Revision ID: 0005
Revises: 0004
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("fuel_remaining", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_items_fuel_nonnegative",
        "items",
        "fuel_remaining IS NULL OR fuel_remaining >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_items_fuel_nonnegative", "items", type_="check")
    op.drop_column("items", "fuel_remaining")
