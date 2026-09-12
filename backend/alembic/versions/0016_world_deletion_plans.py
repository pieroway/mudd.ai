from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='0016'
down_revision='0015'
branch_labels=None
depends_on=None
def upgrade():
 op.create_table('world_deletion_plans',sa.Column('id',sa.String(36),primary_key=True),sa.Column('creator_account_id',sa.String(50),sa.ForeignKey('accounts.id',ondelete='CASCADE'),nullable=False),sa.Column('source_room_id',sa.String(50),sa.ForeignKey('rooms.id',ondelete='CASCADE'),nullable=False),sa.Column('direction',sa.String(5),nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False),sa.Column('room_ids',JSONB,nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('now()')))
def downgrade(): op.drop_table('world_deletion_plans')
