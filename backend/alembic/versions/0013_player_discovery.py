"""Persist rooms discovered by each character."""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_discoveries",
        sa.Column("player_id", sa.String(36), sa.ForeignKey("players.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("room_id", sa.String(50), sa.ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True),
    )
    # No historical travel log exists. Only the current location is known.
    op.execute("INSERT INTO player_discoveries (player_id, room_id) SELECT id, current_room_id FROM players")


def downgrade() -> None:
    op.drop_table("player_discoveries")
