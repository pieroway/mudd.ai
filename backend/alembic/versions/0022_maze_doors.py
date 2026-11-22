"""Persist interactive maze door state."""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("doors", sa.Column("lock_id", sa.String(50)))
    for name in ("is_locked", "is_hidden", "is_jammed"):
        op.add_column("doors", sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    for name in ("is_jammed", "is_hidden", "is_locked", "lock_id"):
        op.drop_column("doors", name)
