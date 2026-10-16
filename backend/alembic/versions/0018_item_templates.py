"""Persist item templates and structured instance metadata.

Revision ID: 0018
Revises: 0017
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


EMPTY_OBJECT = sa.text("'{}'::jsonb")
EMPTY_ARRAY = sa.text("'[]'::jsonb")


def upgrade() -> None:
    op.create_table(
        "item_templates",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("aliases", JSONB(), nullable=False, server_default=EMPTY_ARRAY),
        sa.Column("categories", JSONB(), nullable=False, server_default=EMPTY_ARRAY),
        sa.Column("short_description", sa.String(length=500), nullable=False),
        sa.Column("examine_description", sa.Text(), nullable=False),
        sa.Column("material", sa.String(length=100), nullable=False),
        sa.Column("physical", JSONB(), nullable=False),
        sa.Column("capabilities", JSONB(), nullable=False, server_default=EMPTY_OBJECT),
        sa.Column("default_state", JSONB(), nullable=False, server_default=EMPTY_OBJECT),
        sa.Column(
            "value",
            JSONB(),
            nullable=False,
            server_default=sa.text('\'{"amount": 0, "currency": "copper"}\'::jsonb'),
        ),
        sa.Column("rarity", sa.String(length=20), nullable=False, server_default="common"),
        sa.Column("equipment_slots", JSONB(), nullable=False, server_default=EMPTY_ARRAY),
        sa.Column("stackable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("attributes", JSONB(), nullable=False, server_default=EMPTY_OBJECT),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "rarity IN ('common','uncommon','rare','legendary')",
            name="ck_item_templates_rarity",
        ),
    )

    op.add_column(
        "items",
        sa.Column(
            "template_id",
            sa.String(length=80),
            sa.ForeignKey("item_templates.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index("ix_items_template_id", "items", ["template_id"])
    op.add_column("items", sa.Column("state", JSONB(), nullable=False, server_default=EMPTY_OBJECT))
    op.add_column(
        "items", sa.Column("condition", JSONB(), nullable=False, server_default=EMPTY_OBJECT)
    )
    op.add_column(
        "items",
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint("ck_items_quantity_positive", "items", "quantity > 0")
    op.add_column(
        "items", sa.Column("relationships", JSONB(), nullable=False, server_default=EMPTY_OBJECT)
    )
    op.add_column(
        "items",
        sa.Column(
            "discovery",
            JSONB(),
            nullable=False,
            server_default=sa.text('\'{"hidden": false, "discovered_by": []}\'::jsonb'),
        ),
    )
    op.add_column(
        "items",
        sa.Column(
            "provenance",
            JSONB(),
            nullable=False,
            server_default=sa.text('\'{"source": "authored"}\'::jsonb'),
        ),
    )
    op.add_column(
        "items",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "items",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_column("items", "updated_at")
    op.drop_column("items", "created_at")
    op.drop_column("items", "provenance")
    op.drop_column("items", "discovery")
    op.drop_column("items", "relationships")
    op.drop_constraint("ck_items_quantity_positive", "items", type_="check")
    op.drop_column("items", "quantity")
    op.drop_column("items", "condition")
    op.drop_column("items", "state")
    op.drop_index("ix_items_template_id", table_name="items")
    op.drop_column("items", "template_id")
    op.drop_table("item_templates")
