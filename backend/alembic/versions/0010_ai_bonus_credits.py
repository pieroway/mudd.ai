"""Persistent admin-granted AI credits and grant history."""

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("ai_bonus_credits", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint("ck_accounts_ai_bonus_credits", "accounts", "ai_bonus_credits BETWEEN 0 AND 1000000")
    op.create_table(
        "ai_credit_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("admin_account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recipient_account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("units BETWEEN 1 AND 10000", name="ck_ai_credit_grant_units"),
    )
    op.create_index("ix_ai_credit_grants_recipient_account_id", "ai_credit_grants", ["recipient_account_id"])


def downgrade() -> None:
    op.drop_table("ai_credit_grants")
    op.drop_constraint("ck_accounts_ai_bonus_credits", "accounts", type_="check")
    op.drop_column("accounts", "ai_bonus_credits")
