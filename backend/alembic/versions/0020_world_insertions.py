"""Allow reviewed route insertion proposals without changing existing drafts."""

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_world_schema", "world_proposals", type_="check")
    op.create_check_constraint("ck_world_schema", "world_proposals", "schema_version IN (1,2,3)")


def downgrade():
    # PostgreSQL refuses this downgrade while insertion drafts exist, preserving them.
    op.drop_constraint("ck_world_schema", "world_proposals", type_="check")
    op.create_check_constraint("ck_world_schema", "world_proposals", "schema_version IN (1,2)")
