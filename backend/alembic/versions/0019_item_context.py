"""Persist player condition and room environment without changing item locations."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    for table, column in [("players", "state_data"), ("rooms", "conditions")]:
        op.add_column(
            table, sa.Column(column, JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb"))
        )


def downgrade():
    op.drop_column("rooms", "conditions")
    op.drop_column("players", "state_data")
