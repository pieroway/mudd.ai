from app.domain.door import Door
from app.domain.item import Item
from app.domain.player import Player
from app.engine.executor import execute_command


def test_door_blocks_movement_and_shares_state(seeded_world):
    door = Door('door', 'oak door', 'A plain oak door.', 'town_square', 'inn')
    seeded_world['rooms']['town_square'].doors['east'] = door
    seeded_world['rooms']['inn'].doors['west'] = door
    player = Player('p', 'Walker', 'town_square', [])
    assert not execute_command({'action': 'move', 'direction': 'east'}, player, seeded_world)['success']
    assert 'closed' in execute_command({'action': 'look'}, player, seeded_world)['output']
    assert execute_command({'action': 'open', 'target': 'east door'}, player, seeded_world)['success']
    assert execute_command({'action': 'move', 'direction': 'east'}, player, seeded_world)['success']
    assert execute_command({'action': 'close', 'target': 'door'}, player, seeded_world)['success']
    assert not execute_command({'action': 'move', 'direction': 'west'}, player, seeded_world)['success']


def test_local_names_and_immovable_fixtures(seeded_world):
    seeded_world['items']['remote_cup'] = Item('remote_cup', 'cup', 'A cup.', room_id='inn')
    seeded_world['items']['local_cup'] = Item('local_cup', 'cup', 'A cup.', room_id='town_square')
    seeded_world['items']['bench'] = Item('bench', 'bench', 'A workbench.', room_id='town_square', portable=False)
    player = Player('p', 'Walker', 'town_square', [])
    assert execute_command({'action': 'take', 'target': 'cup'}, player, seeded_world)['success']
    assert player.inventory == ['local_cup']
    assert not execute_command({'action': 'take', 'target': 'bench'}, player, seeded_world)['success']
