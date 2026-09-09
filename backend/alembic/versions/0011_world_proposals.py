"""Private room proposals and atomic approval history."""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "world_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("creator_account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("source_room_id", sa.String(50), sa.ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("direction", sa.String(5), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(8), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("result_room_id", sa.String(50), sa.ForeignKey("rooms.id", ondelete="RESTRICT")),
        sa.CheckConstraint("status IN ('pending','approved','rejected','stale')", name="ck_world_status"),
        sa.CheckConstraint("direction IN ('north','south','east','west','up','down')", name="ck_world_direction"),
        sa.CheckConstraint("(status = 'approved') = (result_room_id IS NOT NULL)", name="ck_world_result"),
        sa.CheckConstraint("(status = 'pending') = (decided_at IS NULL)", name="ck_world_decision"),
        sa.CheckConstraint("schema_version = 1", name="ck_world_schema"),
    )
    op.create_index("ix_world_proposals_creator_account_id", "world_proposals", ["creator_account_id"])


def downgrade() -> None:
    op.drop_table("world_proposals")
