"""Check 0014 on a fresh, explicitly isolated PostgreSQL database.

Run inside the backend container with DATABASE_URL pointing to a new database
named muddb_migration_test. Never run against the game or the pytest database.
"""

import asyncio
import os
import subprocess

import asyncpg
from sqlalchemy.engine import make_url


url = make_url(os.environ['DATABASE_URL'])
if url.database != 'muddb_migration_test' or url.host != 'postgres_test':
    raise RuntimeError('This check requires postgres_test/muddb_migration_test.')


async def sql(statement, *args):
    connection = await asyncpg.connect(url.set(drivername='postgresql').render_as_string(hide_password=False))
    try:
        return await connection.fetch(statement, *args)
    finally:
        await connection.close()


def query(statement, *args):
    return asyncio.run(sql(statement, *args))


def migrate(verb, revision):
    subprocess.run(['alembic', verb, revision], check=True)


migrate('upgrade', '0013')
query("INSERT INTO rooms (id,name,description) VALUES ('inn','Inn','Warm.'), ('forest','Forest','Trees.')")
query("INSERT INTO players (id,username,normalized_username,current_room_id) VALUES ('walker','Walker','walker','forest')")
query("INSERT INTO player_discoveries (player_id,room_id) VALUES ('walker','forest')")
query("""INSERT INTO world_proposals
    (id,source_room_id,source_fingerprint,direction,name,description)
    VALUES ('legacy','forest',repeat('a',64),'north','Glade','Still air.')""")
query("""INSERT INTO items (id,name,description,room_id,can_open,is_open,can_use,is_light_source,is_lit)
    VALUES ('cup','cup','A cup.','inn',false,false,false,false,false)""")
migrate('upgrade', '0014')
assert query("SELECT building_id FROM rooms WHERE id='inn'")[0]['building_id'] == 'inn'
assert query("SELECT portable FROM items WHERE id='cup'")[0]['portable'] is True
assert query("SELECT count(*) AS n FROM player_discoveries")[0]['n'] == 1
assert query("SELECT schema_version FROM world_proposals WHERE id='legacy'")[0]['schema_version'] == 1
migrate('downgrade', '0013')
assert query("SELECT count(*) AS n FROM rooms")[0]['n'] == 2
assert query("SELECT count(*) AS n FROM items")[0]['n'] == 1
migrate('upgrade', '0014')
query("""INSERT INTO world_proposals
    (id,source_room_id,source_fingerprint,direction,name,description,schema_version,payload)
    VALUES ('version2','forest',repeat('b',64),'east','Draft','Draft.',2,'{}')""")
refused = subprocess.run(['alembic', 'downgrade', '0013'], capture_output=True, text=True)
assert refused.returncode != 0 and 'ck_world_schema_legacy' in refused.stderr
assert query('SELECT version_num FROM alembic_version')[0]['version_num'] == '0014'
assert query("SELECT count(*) AS n FROM world_proposals")[0]['n'] == 2
assert query("SELECT portable FROM items WHERE id='cup'")[0]['portable'] is True
print('Migration upgrade, legacy data preservation, downgrade/upgrade, and protected rollback passed.')
