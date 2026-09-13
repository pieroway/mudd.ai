"""Create a deterministic admin account only in the isolated browser-test stack."""

import asyncio

from app.config import Settings
from app.db import engine, get_session_factory
from app.services.auth import register_account
from app.services.ai_preferences import set_admin
from app.models.game import RoomRecord, ExitRecord, PlayerRecord, PlayerDiscoveryRecord


async def seed_map():
    identity = await register_account('MapExplorer', 'A long test-only passphrase1!')
    rooms = {
        'hall': 'Cedar Hall', 'library': 'Library', 'workshop': 'Workshop',
        'garden': 'Garden', 'courtyard': 'Courtyard',
        'landing': 'Landing', 'guest': 'Guest Room', 'loft': 'Loft', 'attic': 'Attic',
        'cellar': 'Cellar', 'wine': 'Wine Store', 'tunnel': 'Tunnel', 'passage': 'Old Passage',
        'roof': 'Roof', 'deep': 'Deep Cave', 'secret': 'Unvisited Vault',
    }
    connections = [('hall', 'east', 'library'), ('hall', 'west', 'workshop'),
                   ('hall', 'north', 'garden'), ('hall', 'south', 'courtyard'),
                   ('hall', 'up', 'landing'), ('landing', 'east', 'guest'),
                   ('landing', 'up', 'loft'), ('loft', 'east', 'attic'), ('loft', 'up', 'roof'),
                   ('hall', 'down', 'cellar'), ('cellar', 'east', 'wine'),
                   ('cellar', 'down', 'tunnel'), ('tunnel', 'east', 'passage'),
                   ('tunnel', 'down', 'deep'), ('library', 'down', 'secret')]
    opposite = {'east': 'west', 'west': 'east', 'north': 'south', 'south': 'north', 'up': 'down', 'down': 'up'}
    async with get_session_factory()() as session, session.begin():
        session.add_all([RoomRecord(id='map_' + key, name=name, description='A quiet place.') for key, name in rooms.items()])
        await session.flush()
        for source, direction, destination in connections:
            session.add(ExitRecord(room_id='map_' + source, direction=direction, destination_room_id='map_' + destination))
            session.add(ExitRecord(room_id='map_' + destination, direction=opposite[direction], destination_room_id='map_' + source))
        player = await session.get(PlayerRecord, identity.player_id)
        player.current_room_id = 'map_hall'
        session.add_all([PlayerDiscoveryRecord(player_id=identity.player_id, room_id='map_' + key)
                         for key in rooms if key != 'secret'])


async def main():
    settings = Settings()
    if settings.app_env != "test" or "@postgres_e2e:5432/muddb_e2e" not in settings.database_url:
        raise RuntimeError("This fixture requires the isolated E2E database.")
    try:
        for username in ("NarrationAdmin", "CreditAdmin", "WorldAdmin", "NeighborhoodAdmin"):
            await register_account(username, "A long test-only passphrase1!")
            await set_admin(get_session_factory(), username, True)
        await seed_map()
    finally:
        await engine.dispose()


asyncio.run(main())
