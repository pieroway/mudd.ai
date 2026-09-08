"""Add one NPC and bounded per-character conversation memory."""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "npcs",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("room_id", sa.String(50), sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("secret", sa.Text(), nullable=False),
    )
    op.create_table(
        "npc_memories",
        sa.Column("npc_id", sa.String(50), sa.ForeignKey("npcs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("player_id", sa.String(36), sa.ForeignKey("players.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("interactions", sa.Integer(), nullable=False),
        sa.Column("player_text", sa.String(400), nullable=False),
        sa.Column("npc_text", sa.String(600), nullable=False),
        sa.CheckConstraint("interactions >= 0", name="ck_npc_memory_interactions"),
        sa.CheckConstraint("char_length(player_text) <= 400", name="ck_npc_memory_player_text"),
        sa.CheckConstraint("char_length(npc_text) <= 600", name="ck_npc_memory_npc_text"),
    )


def downgrade() -> None:
    op.drop_table("npc_memories")
    op.drop_table("npcs")
