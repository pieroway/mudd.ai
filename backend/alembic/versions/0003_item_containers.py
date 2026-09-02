"""Allow items to be stored inside container items.

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_items_exactly_one_location", "items", type_="check")
    op.add_column("items", sa.Column("container_id", sa.String(length=50), nullable=True))
    op.create_foreign_key(
        "fk_items_container_id_items",
        "items",
        "items",
        ["container_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_items_container_id", "items", ["container_id"])
    op.create_check_constraint(
        "ck_items_exactly_one_location",
        "items",
        "(room_id IS NOT NULL AND owner_id IS NULL AND container_id IS NULL) OR "
        "(room_id IS NULL AND owner_id IS NOT NULL AND container_id IS NULL) OR "
        "(room_id IS NULL AND owner_id IS NULL AND container_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE items AS contents SET room_id = containers.room_id, "
        "owner_id = containers.owner_id, container_id = NULL "
        "FROM items AS containers WHERE contents.container_id = containers.id"
    )
    op.drop_constraint("ck_items_exactly_one_location", "items", type_="check")
    op.drop_index("ix_items_container_id", table_name="items")
    op.drop_constraint("fk_items_container_id_items", "items", type_="foreignkey")
    op.drop_column("items", "container_id")
    op.create_check_constraint(
        "ck_items_exactly_one_location",
        "items",
        "(room_id IS NOT NULL AND owner_id IS NULL) OR "
        "(room_id IS NULL AND owner_id IS NOT NULL)",
    )
