from alembic import op
import sqlalchemy as sa
revision='0015'
down_revision='0014'
branch_labels=None
depends_on=None
def upgrade():
 op.add_column('items',sa.Column('interaction_target_id',sa.String(50),sa.ForeignKey('items.id',ondelete='SET NULL')));op.add_column('items',sa.Column('is_clean',sa.Boolean(),nullable=False,server_default='false'))
def downgrade():
 op.drop_column('items','is_clean');op.drop_column('items','interaction_target_id')
