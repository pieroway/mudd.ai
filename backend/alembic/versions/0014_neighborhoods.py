"""Buildings, shared doors, fixtures, and neighborhood drafts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('buildings', sa.Column('id', sa.String(50), primary_key=True),
                    sa.Column('name', sa.String(100), nullable=False))
    op.add_column('rooms', sa.Column('building_id', sa.String(50), sa.ForeignKey('buildings.id', ondelete='RESTRICT')))
    op.create_index('ix_rooms_building_id', 'rooms', ['building_id'])
    op.create_table('doors', sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False), sa.Column('description', sa.Text(), nullable=False),
        sa.Column('room_id', sa.String(50), sa.ForeignKey('rooms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('destination_room_id', sa.String(50), sa.ForeignKey('rooms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_open', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('room_exits', sa.Column('door_id', sa.String(50), sa.ForeignKey('doors.id', ondelete='RESTRICT')))
    op.add_column('items', sa.Column('portable', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('world_proposals', sa.Column('payload', JSONB()))
    op.drop_constraint('ck_world_schema', 'world_proposals', type_='check')
    op.create_check_constraint('ck_world_schema', 'world_proposals', 'schema_version IN (1,2)')
    op.execute("INSERT INTO buildings (id,name) VALUES ('inn','Inn'),('blacksmith','Blacksmith')")
    op.execute("UPDATE rooms SET building_id=id WHERE id IN ('inn','blacksmith')")


def downgrade():
    # Draft payloads cannot be represented by the old schema; fail rather than discard them.
    op.create_check_constraint('ck_world_schema_legacy', 'world_proposals', 'schema_version = 1')
    op.drop_constraint('ck_world_schema', 'world_proposals', type_='check')
    op.drop_constraint('ck_world_schema_legacy', 'world_proposals', type_='check')
    op.create_check_constraint('ck_world_schema', 'world_proposals', 'schema_version = 1')
    op.drop_column('world_proposals', 'payload')
    op.drop_column('items', 'portable')
    op.drop_column('room_exits', 'door_id')
    op.drop_table('doors')
    op.drop_column('rooms', 'building_id')
    op.drop_table('buildings')
