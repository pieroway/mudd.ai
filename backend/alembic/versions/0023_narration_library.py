"""Persist shared narration flourishes."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "narration_library",
        sa.Column("outcome_key", sa.String(64), primary_key=True),
        sa.Column("flourishes", JSONB, nullable=False),
        sa.CheckConstraint("jsonb_array_length(flourishes) BETWEEN 1 AND 5",
                           name="ck_narration_library_size"),
    )


def downgrade():
    op.drop_table("narration_library")
