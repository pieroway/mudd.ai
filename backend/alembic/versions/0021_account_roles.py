"""Add independent roles and protect the existing Alan account."""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("is_god", "is_moderator", "is_creator"):
        op.add_column("accounts", sa.Column(name, sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_check_constraint("ck_accounts_god", "accounts",
                               "NOT is_god OR (is_admin AND normalized_username = 'alan')")
    op.create_index("uq_accounts_single_god", "accounts", ["is_god"], unique=True,
                    postgresql_where=sa.text("is_god"))
    op.execute("UPDATE accounts SET is_god = true, is_admin = true WHERE normalized_username = 'alan'")
    op.execute("""
        CREATE FUNCTION protect_god_account() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.is_god THEN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'The God account is protected';
                END IF;
                IF ROW(NEW.id, NEW.normalized_username, NEW.player_id, NEW.is_god,
                       NEW.is_admin, NEW.is_creator, NEW.is_moderator)
                   IS DISTINCT FROM ROW(OLD.id, OLD.normalized_username, OLD.player_id, OLD.is_god,
                                        OLD.is_admin, OLD.is_creator, OLD.is_moderator) THEN
                    RAISE EXCEPTION 'The God account is protected';
                END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("CREATE TRIGGER protect_god_account BEFORE UPDATE OR DELETE ON accounts "
               "FOR EACH ROW EXECUTE FUNCTION protect_god_account()")
    op.create_table(
        "role_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.String(36)),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("role_changes")
    op.execute("DROP TRIGGER protect_god_account ON accounts")
    op.execute("DROP FUNCTION protect_god_account()")
    op.drop_index("uq_accounts_single_god", table_name="accounts")
    op.drop_constraint("ck_accounts_god", "accounts", type_="check")
    for name in ("is_creator", "is_moderator", "is_god"):
        op.drop_column("accounts", name)
