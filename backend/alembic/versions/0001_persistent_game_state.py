"""Create persistent game state.

Revision ID: 0001
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rooms",
        sa.Column("id", sa.String(length=50), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_table(
        "room_exits",
        sa.Column("room_id", sa.String(length=50), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("destination_room_id", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["destination_room_id"], ["rooms.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("room_id", "direction"),
    )
    op.create_table(
        "players",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("normalized_username", sa.String(length=50), nullable=False, unique=True),
        sa.Column("current_room_id", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["current_room_id"], ["rooms.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "items",
        sa.Column("id", sa.String(length=50), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("room_id", sa.String(length=50), nullable=True),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "(room_id IS NOT NULL AND owner_id IS NULL) OR "
            "(room_id IS NULL AND owner_id IS NOT NULL)",
            name="ck_items_exactly_one_location",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["players.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_items_owner_id", "items", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_items_owner_id", table_name="items")
    op.drop_table("items")
    op.drop_table("players")
    op.drop_table("room_exits")
    op.drop_table("rooms")
