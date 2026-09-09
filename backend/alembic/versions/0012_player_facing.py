"""Persist last successful horizontal movement for relative directions."""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("facing_direction", sa.String(5), nullable=False, server_default="north"))
    op.create_check_constraint("ck_player_facing", "players", "facing_direction IN ('north','east','south','west')")


def downgrade() -> None:
    op.drop_constraint("ck_player_facing", "players", type_="check")
    op.drop_column("players", "facing_direction")
