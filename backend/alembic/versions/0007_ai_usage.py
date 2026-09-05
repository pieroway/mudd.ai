"""Persist daily AI request allowances per account."""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_daily_usage",
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.CheckConstraint("attempts >= 0", name="ck_ai_usage_nonnegative"),
    )


def downgrade() -> None:
    op.drop_table("ai_daily_usage")
