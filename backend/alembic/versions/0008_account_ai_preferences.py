"""Default all accounts to non-admin with narration off."""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("accounts", sa.Column(
        "ai_narration_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
    ))


def downgrade() -> None:
    op.drop_column("accounts", "ai_narration_enabled")
    op.drop_column("accounts", "is_admin")
