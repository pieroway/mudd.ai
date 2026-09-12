from alembic import op
import sqlalchemy as sa
revision='0017'
down_revision='0016'
branch_labels=None
depends_on=None
def upgrade():
 op.add_column('items',sa.Column('interaction_verb',sa.String(12)));op.add_column('items',sa.Column('interaction_state',sa.String(12)))
def downgrade():
 op.drop_column('items','interaction_state');op.drop_column('items','interaction_verb')
