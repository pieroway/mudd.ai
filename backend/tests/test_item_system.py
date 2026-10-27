from copy import deepcopy

import pytest
from sqlalchemy import select

from app.commands.parser import parse_command
from app.domain.catalogue import CATALOGUE, PRIORITY
from app.domain.item import Item
from app.domain.item_context import describe, visible
from app.domain.item_dependencies import provision_lock, validate_dependencies
from app.domain.player import Player
from app.domain.room import Room
from app.engine.executor import execute_command
from app.models import ItemRecord
from app.repositories.game import GameRepository
from tests.test_services.test_world_generation import connect, command


def scene():
    player = Player("builder", "Builder", "one")
    rooms = {
        key: Room(key, key, "A quiet room.") for key in ("one", "two", "three", "four", "five")
    }
    for left, right in zip(rooms, list(rooms)[1:]):
        rooms[left].exits["east"] = right
        rooms[right].exits["west"] = left
    return player, {"rooms": rooms, "items": {}, "players": {player.id: player}}


def add(world, template_id, key=None, owner=None, room="one"):
    item = Item.from_template(
        key or template_id, CATALOGUE[template_id], room_id=None if owner else room, owned_by=owner
    )
    world["items"][item.id] = item
    if owner:
        world["players"][owner].inventory.append(item.id)
    return item


def run(text, player, world, success=True):
    reply = execute_command(parse_command(text), player, world)
    assert reply["success"] is success, (text, reply)
    return reply["output"]


def test_catalogue_covers_specification_and_priority_templates():
    # The catalogue source is checked separately against the spec in repository validation.
    assert len(CATALOGUE) >= 140
    assert len(PRIORITY) == 20
    assert set(PRIORITY) <= set(CATALOGUE)
    assert not CATALOGUE["vehicle_fishing_skiff"].physical.portable
    assert CATALOGUE["clothing_backpack"].capabilities["container"]["capacity_litres"] == 30


def test_hands_equipment_placement_and_context():
    player, world = scene()
    sword = add(world, "weapon_sword_short")
    add(world, "weapon_dagger_iron")
    add(world, "clothing_cloak_wool")
    add(world, "clothing_backpack")
    table = add(world, "furniture_table_wooden")
    run("take blade", player, world)
    assert "right hand" in run("wield sword", player, world)
    run("take dagger", player, world)
    run("hold dagger in left hand", player, world)
    run("take cloak", player, world)
    assert "full" in run("hold cloak", player, world, False)
    run("wear cloak", player, world)
    run("release dagger", player, world)
    run("remove cloak", player, world)
    run("put sword on table", player, world)
    assert sword.container_id == table.id
    assert "rests on the wooden table" in run("look on table", player, world)
    run("take sword from table", player, world)
    run("take backpack", player, world)
    run("open backpack", player, world)
    run("put dagger in backpack", player, world)
    run("close backpack", player, world)
    assert not visible(world["items"]["weapon_dagger_iron"], player, world)
    assert "closed" in run("look in backpack", player, world, False)
    assert "carry" in describe(sword, player, world, "inventory")
    run("open backpack", player, world)
    run("take dagger from backpack", player, world)
    assert not sword.relationships.get("slot")


def test_capacity_opening_and_large_objects():
    player, world = scene()
    add(world, "weapon_sword_short", owner=player.id)
    add(world, "container_bottle_glass", owner=player.id)
    add(world, "vehicle_fishing_skiff")
    run("open bottle", player, world)
    assert "weight" in run("put sword in bottle", player, world, False)
    world["items"]["weapon_sword_short"].weight_kg = 0.1
    assert "fit" in run("put sword in bottle", player, world, False)
    assert "large" in run("take skiff", player, world, False)
    assert "heavy" in run("push skiff", player, world, False)
    run("board skiff", player, world)
    assert "Leave" in run("east", player, world, False)
    run("leave", player, world)
    run("east", player, world)


def test_adding_to_nested_container_cannot_bypass_ancestor_capacity():
    player, world = scene()
    pack = add(world, "clothing_backpack", owner=player.id)
    inner = add(world, "container_sack_burlap", owner=player.id)
    inner.name = "inner sack"
    inner.capabilities["container"]["maximum_weight_kg"] = 100
    pack.is_open = inner.is_open = True
    stone = add(world, "material_stone", owner=player.id)
    stone.weight_kg = 25
    run("put inner sack in backpack", player, world)
    reply = execute_command(parse_command("put stone in inner sack"), player, world)
    assert not reply["success"]
    assert stone.owned_by == player.id and stone.container_id is None


def test_ambiguous_template_name_does_not_pick_an_arbitrary_instance():
    player, world = scene()
    first = add(world, "weapon_sword_short", "first_sword")
    second = add(world, "weapon_sword_short", "second_sword")
    reply = execute_command(parse_command("take short sword"), player, world)
    assert not reply["success"]
    assert not player.inventory
    assert first.room_id == second.room_id == "one"


def test_wield_respects_declared_slots():
    player, world = scene()
    sword = add(world, "weapon_sword_short", owner=player.id)
    sword.capabilities["wieldable"]["slots"] = ["left_hand"]
    reply = execute_command(parse_command("wield sword in right hand"), player, world)
    assert not reply["success"] and "slot" not in sword.relationships


def test_legacy_objects_do_not_gain_undeclared_wield_capability():
    player, world = scene()
    legacy = Item(
        id="plain_rock", name="plain rock", description="An ordinary rock.", owned_by=player.id
    )
    world["items"][legacy.id] = legacy
    player.inventory.append(legacy.id)
    reply = execute_command(parse_command("wield plain rock"), player, world)
    assert not reply["success"]


def test_filling_a_carried_vessel_checks_liquid_weight_before_mutating():
    player, world = scene()
    player.state["carrying_capacity_kg"] = 1
    source = add(world, "container_bottle_glass", "source")
    source.name = "source bottle"
    source.is_open = True
    source.state.update(liquid="water", liquid_litres=1)
    vessel = add(world, "container_bottle_glass", "vessel", owner=player.id)
    vessel.name = "empty bottle"
    vessel.is_open = True
    reply = execute_command(parse_command("fill empty bottle from source bottle"), player, world)
    assert not reply["success"]
    assert source.state["liquid_litres"] == 1
    assert not vessel.state.get("liquid_litres")


def lit_legacy_scene():
    player, world = scene()
    add(world, "weapon_sword_short", owner=player.id)
    torch = Item(
        id="legacy_torch",
        name="torch",
        description="An old torch.",
        owned_by=player.id,
        is_light_source=True,
        is_lit=True,
        fuel_remaining=20,
    )
    world["items"][torch.id] = torch
    player.inventory.append(torch.id)
    return player, world


def test_contextual_look_preserves_authoritative_room_id():
    player, world = lit_legacy_scene()
    reply = execute_command(parse_command("look"), player, world)
    assert reply.get("room_id") == "one"


def test_contextual_look_preserves_legacy_torchlight_information():
    player, world = lit_legacy_scene()
    reply = execute_command(parse_command("look"), player, world)
    assert "Torchlight reaches farther." in reply["output"]
    assert "east: two" in reply["output"]


def test_legacy_tool_fallback_cannot_select_a_hidden_item():
    player, world = scene()
    surface = Item(
        id="dusty_shelf", name="dusty shelf", description="Dust coats a shelf.", room_id="one"
    )
    visible_rag = Item(
        id="plain_rag",
        name="rag",
        description="A cloth rag.",
        owned_by=player.id,
        interaction_target_id="another_surface",
    )
    hidden_rag = Item(
        id="hidden_rag",
        name="rag",
        description="A hidden rag.",
        owned_by=player.id,
        interaction_target_id=surface.id,
        discovery={"hidden": True, "discovered_by": []},
    )
    world["items"].update({item.id: item for item in (surface, visible_rag, hidden_rag)})
    player.inventory.extend([visible_rag.id, hidden_rag.id])
    reply = execute_command(parse_command("wipe dusty shelf with rag"), player, world)
    assert not reply["success"]
    assert not surface.is_clean and surface.interaction_state is None


def test_hidden_matching_key_search_unlock_and_cycles():
    player, world = scene()
    chest = add(world, "container_chest_wooden")
    rug = add(world, "furniture_rug")
    key = provision_lock(chest, world["items"], world["rooms"], "one", hiding_place=rug.id)
    assert not visible(key, player, world)
    assert key.name not in run("look", player, world)
    assert "Scuff marks" in run("search room", player, world)
    assert key.name in run("look under rug", player, world)
    assert visible(key, player, world)
    run(f"take {key.name}", player, world)
    run(f"unlock chest with {key.name}", player, world)
    run("open chest", player, world)
    run("close chest", player, world)
    run(f"lock chest with {key.name}", player, world)
    key.put_in(chest.id)
    with pytest.raises(ValueError, match="cyclic"):
        validate_dependencies(world["items"], world["rooms"], "one", player.id)
    key.drop_in("one")
    other = add(world, "container_chest_wooden", "other")
    other.name = "second chest"
    other_key = provision_lock(other, world["items"], world["rooms"], "one")
    if other_key is key:
        other_key = deepcopy(key)
        other_key.id = "second_chest_key"
        other_key.relationships["opens"] = [other.relationships["lock_id"]]
        key.relationships["opens"] = [chest.relationships["lock_id"]]
        world["items"][other_key.id] = other_key
    key.put_in(other.id)
    other_key.put_in(chest.id)
    with pytest.raises(ValueError, match="cyclic"):
        validate_dependencies(world["items"], world["rooms"], "one", player.id)


def test_nearby_keys_duplicate_keys_alternatives_and_unreachable_placement():
    player, world = scene()
    chest = add(world, "container_chest_wooden")
    key = provision_lock(chest, world["items"], world["rooms"], "one", key_room="four")
    assert key.room_id == "four"
    assert validate_dependencies(world["items"], world["rooms"], "one")["solvable"]
    with pytest.raises(ValueError, match="three reachable"):
        provision_lock(chest, world["items"], world["rooms"], "one", key_room="five")
    duplicate = deepcopy(key)
    duplicate.id = "duplicate_key"
    duplicate.room_id = "one"
    world["items"][duplicate.id] = duplicate
    key.state["broken"] = True
    validate_dependencies(world["items"], world["rooms"], "one")
    del world["items"][duplicate.id]
    with pytest.raises(ValueError):
        validate_dependencies(world["items"], world["rooms"], "one")
    pick = add(world, "tool_lockpick", owner=player.id)
    chest.relationships["alternative_access"] = ["pick_lock"]
    validate_dependencies(world["items"], world["rooms"], "one", player.id)
    run("pick wooden chest lock", player, world)
    assert not chest.state["locked"]
    assert pick.id in player.inventory


def test_reading_lighting_darkness_consumption_and_durability():
    player, world = scene()
    letter = add(world, "readable_letter", owner=player.id)
    letter.state["readable"] = {"text": "Meet at the docks.", "back": "Bring the brass key."}
    run("read letter", player, world, False)
    run("open letter", player, world)
    assert "docks" in run("read letter", player, world)
    assert "brass key" in run("read back of letter", player, world)
    torch = add(world, "light_torch", owner=player.id)
    run("light torch", player, world, False)
    ignition = add(world, "tool_flint_steel", owner=player.id)
    run("light torch", player, world)
    world["rooms"]["one"].conditions["dark"] = True
    assert "too dark" not in run("look", player, world)
    run("extinguish torch", player, world)
    assert "too dark" in run("look", player, world)
    world["rooms"]["one"].conditions["dark"] = False
    potion = add(world, "potion_healing_minor", owner=player.id)
    player.state["health"] = 50
    run("drink healing potion", player, world)
    assert player.state["health"] == 70 and potion.id not in world["items"]
    crate = add(world, "container_crate_wooden")
    crowbar = add(world, "tool_crowbar", owner=player.id)
    run("break crate with crowbar", player, world)
    assert crate.state["broken"] and crate.is_open
    assert not torch.is_lit and ignition.id in player.inventory and crowbar.id in player.inventory


def test_attachment_climbing_and_vessels():
    player, world = scene()
    rope = add(world, "tool_rope_hemp", owner=player.id)
    add(world, "fixture_iron_ring")
    assert "Secure" in run("climb rope", player, world, False)
    run("tie rope to iron ring", player, world)
    rope.relationships["climb_destination"] = "two"
    run("climb rope", player, world)
    assert player.current_room_id == "two"
    player.current_room_id = "one"
    run("untie rope", player, world)
    first = add(world, "container_bottle_glass", "first", owner=player.id)
    first.name = "blue bottle"
    second = add(world, "container_bottle_glass", "second", owner=player.id)
    second.name = "red bottle"
    first.is_open = second.is_open = True
    first.state.update(liquid="water", liquid_litres=1)
    run("pour blue bottle into red bottle", player, world)
    assert second.state["liquid_litres"] == 1 and first.state["liquid_litres"] == 0


def test_stacks_split_combine_transfer_and_explicit_spending():
    player, world = scene()
    recipient = Player("mara", "Mara", "one")
    world["players"][recipient.id] = recipient
    coins = add(world, "currency_coin_copper", owner=player.id)
    coins.quantity = 20
    run("split 5 coins", player, world)
    split = next(item for item in world["items"].values() if item.id != coins.id)
    run(f"combine {coins.id} with {split.id}", player, world)
    assert coins.quantity == 20 and split.id not in world["items"]
    run("spend 3 coins to Mara", player, world)
    assert coins.quantity == 17
    assert (
        sum(item.quantity for item in world["items"].values() if item.owned_by == recipient.id) == 3
    )


def test_skiff_mooring_and_existing_water_routes():
    player, world = scene()
    skiff = add(world, "vehicle_fishing_skiff")
    add(world, "tool_rope_hemp", owner=player.id)
    add(world, "fixture_iron_ring")
    run("launch skiff", player, world, False)
    world["rooms"]["one"].conditions["terrain"] = "river"
    world["rooms"]["two"].conditions["terrain"] = "river"
    run("tie skiff to iron ring with rope", player, world)
    run("launch skiff", player, world, False)
    run("untie skiff", player, world)
    run("launch skiff", player, world)
    run("board skiff", player, world)
    run("pilot skiff east", player, world, False)
    add(world, "weapon_staff_oak", owner=player.id)
    run("pilot skiff east", player, world)
    assert player.current_room_id == skiff.room_id == "two"
    run("beach skiff", player, world, False)
    world["rooms"]["two"].conditions["shore"] = True
    run("beach skiff", player, world)
    assert not skiff.state["afloat"]


async def test_admin_authoring_snapshot_privacy_and_restart(session_factory):
    game, _, identity = await connect(session_factory)
    before = await command(game, identity, "/item spawn clothing_backpack")
    assert before["success"], before
    await command(game, identity, "take backpack")
    await command(game, identity, "wear backpack")
    await command(game, identity, "/item spawn readable_letter")
    await command(game, identity, "take letter")
    await command(game, identity, "open backpack")
    await command(game, identity, "put letter in backpack")
    await command(game, identity, "close backpack")
    async with session_factory() as session:
        snapshot = await GameRepository(session).client_state(identity.player_id)
        pack = snapshot.inventory[0]
        assert pack.location == "back" and pack.contents == []
        record = (
            await session.scalars(
                select(ItemRecord).where(ItemRecord.template_id == "clothing_backpack")
            )
        ).one()
        assert record.relationships["slot"] == "back"
    await command(game, identity, "open backpack")
    async with session_factory() as session:
        state = await GameRepository(session).client_state(identity.player_id)
        assert state.inventory[0].contents[0].name == "folded letter"
        assert "readable" not in state.model_dump_json()


async def test_unreferenced_template_cannot_break_legacy_world_reads(session_factory):
    from app.models import ItemTemplateRecord
    from app.services.game import GameService

    async with session_factory() as session, session.begin():
        unused = await session.get(ItemTemplateRecord, "weapon_sword_long")
        unused.capabilities = {"unregistered_effect": {}}
    game = GameService(session_factory)
    player = await game.connect_player("reader", "Reader")
    assert player.current_room_id == "town_square"
    snapshot = await game.client_state("reader")
    assert snapshot.room_name == "Town Square"
    assert {item.name for item in snapshot.visible_objects} == {"chest", "torch"}


async def test_stack_creation_and_consumption_are_persistent(session_factory):
    game, _, identity = await connect(session_factory)
    assert (await command(game, identity, "/item spawn currency_coin_copper 20"))["success"]
    assert (await command(game, identity, "take coins"))["success"]
    assert (await command(game, identity, "split 5 coins"))["success"]
    async with session_factory() as session:
        stacks = (
            await session.scalars(
                select(ItemRecord).where(ItemRecord.owner_id == identity.player_id)
            )
        ).all()
        assert sorted(record.quantity for record in stacks) == [5, 15]
    assert (await command(game, identity, "/item spawn potion_healing_minor"))["success"]
    assert (await command(game, identity, "take potion"))["success"]
    assert (await command(game, identity, "use potion"))["success"]
    async with session_factory() as session:
        assert not (
            await session.scalars(
                select(ItemRecord).where(ItemRecord.template_id == "potion_healing_minor")
            )
        ).all()


async def test_hidden_key_snapshot_and_admin_permissions(session_factory):
    from app.services.ai_preferences import set_admin

    game, _, identity = await connect(session_factory)
    assert (await command(game, identity, "/item spawn container_chest_wooden"))["success"]
    assert (await command(game, identity, "/item spawn furniture_rug"))["success"]
    async with session_factory() as session:
        records = list(
            (
                await session.scalars(select(ItemRecord).where(ItemRecord.template_id.is_not(None)))
            ).all()
        )
        chest = next(record for record in records if record.template_id == "container_chest_wooden")
        rug = next(record for record in records if record.template_id == "furniture_rug")
    reply = await command(game, identity, f"/item lock {chest.id} forest {rug.id}")
    assert reply["success"], reply
    async with session_factory() as session:
        snapshot = await GameRepository(session).client_state(identity.player_id)
        assert "key" not in snapshot.model_dump_json()
        key = (
            await session.scalars(
                select(ItemRecord).where(ItemRecord.template_id == "key_brass_ornate")
            )
        ).one()
        key_id = key.id
    # Even the exact internal ID cannot bypass discovery.
    assert not (await command(game, identity, f"take {key_id}"))["success"]
    assert (await command(game, identity, "search rug"))["success"]
    async with session_factory() as session:
        snapshot = await GameRepository(session).client_state(identity.player_id)
        assert key_id in snapshot.model_dump_json()
        assert (
            "lock_id" not in snapshot.model_dump_json()
            and "opens" not in snapshot.model_dump_json()
        )
    assert (await command(game, identity, f"take {key_id}"))["success"]
    assert (await command(game, identity, f"unlock {chest.id} with {key_id}"))["success"]
    assert (await command(game, identity, f"/item inspect {chest.id}"))["success"]
    await set_admin(session_factory, "Builder", False)
    denied = await command(game, identity, f"/item inspect {key_id}")
    assert not denied["success"] and key_id not in denied["output"]


async def test_critical_key_break_is_rolled_back_and_metadata_survives_restart(session_factory):
    from app.services.game import GameService

    game, provider, identity = await connect(session_factory)
    assert (await command(game, identity, "/item spawn container_chest_wooden"))["success"]
    async with session_factory() as session:
        chest = (
            await session.scalars(
                select(ItemRecord).where(ItemRecord.template_id == "container_chest_wooden")
            )
        ).one()
        chest_id = chest.id
    assert (await command(game, identity, f"/item lock {chest_id}"))["success"]
    assert (await command(game, identity, "take wooden chest key"))["success"]
    assert (await command(game, identity, "/item spawn tool_crowbar"))["success"]
    assert (await command(game, identity, "take crowbar"))["success"]
    denied = await command(game, identity, "break wooden chest key with crowbar")
    assert not denied["success"] and "No changes were made" in denied["output"]
    async with session_factory() as session:
        key = (
            await session.scalars(
                select(ItemRecord).where(ItemRecord.template_id == "key_brass_ornate")
            )
        ).one()
        assert not key.state_data.get("broken") and key.relationships["opens"]
    restarted = GameService(session_factory, world_provider=provider)
    await restarted.connect_player("admin", "Builder", player_id=identity.player_id)
    assert (await command(restarted, identity, "unlock wooden chest with wooden chest key"))[
        "success"
    ]


@pytest.mark.parametrize("isolated", [False, True])
async def test_other_players_locks_do_not_block_unrelated_movement(session_factory, isolated):
    from app.models import PlayerRecord, RoomRecord

    game, _, identity = await connect(session_factory)
    if isolated:
        async with session_factory() as session, session.begin():
            session.add(
                RoomRecord(id="isolated_workshop", name="Workshop", description="A quiet workshop.")
            )
            await session.flush()
            record = await session.get(PlayerRecord, identity.player_id)
            record.current_room_id = "isolated_workshop"
    assert (await command(game, identity, "/item spawn container_chest_wooden"))["success"]
    async with session_factory() as session:
        chest = (
            await session.scalars(
                select(ItemRecord).where(ItemRecord.template_id == "container_chest_wooden")
            )
        ).one()
        chest_id = chest.id
    assert (await command(game, identity, f"/item lock {chest_id}"))["success"]
    assert (await command(game, identity, "take wooden chest key"))["success"]
    await game.connect_player("visitor", "Visitor")
    reply = await game.execute("visitor", "north")
    assert reply["success"], reply
    denied = await game.execute("visitor", "unlock wooden chest with wooden chest key")
    assert not denied["success"]


def template_draft():
    from app.ai.neighborhood import NeighborhoodDraft

    return NeighborhoodDraft.model_validate(
        {
            "buildings": [],
            "rooms": [
                {
                    "key": "hall",
                    "name": "Hall",
                    "description": "Cedar beams frame a quiet hall.",
                    "building": None,
                }
            ],
            "connections": [
                {"source": "anchor", "direction": "north", "destination": "hall", "door": None}
            ],
            "objects": [
                {
                    "key": "chest",
                    "name": "cedar chest",
                    "description": "Iron bands protect a cedar chest.",
                    "kind": "container",
                    "room": "hall",
                    "container": None,
                    "interaction_target": None,
                    "template_id": "container_chest_wooden",
                    "locked": True,
                    "key_room": "hall",
                    "hiding_place": "rug",
                },
                {
                    "key": "rug",
                    "name": "faded rug",
                    "description": "A faded rug covers the boards.",
                    "kind": "fixture",
                    "room": "hall",
                    "container": None,
                    "interaction_target": None,
                    "template_id": "furniture_rug",
                },
            ],
        }
    )


async def test_generated_template_locks_publish_atomically(session_factory):
    from app.ai.fake import FakeAIProvider

    class Provider(FakeAIProvider):
        async def generate_neighborhood(self, request, *, before_dispatch):
            await before_dispatch()
            return template_draft()

    game, _, identity = await connect(session_factory, Provider())
    reply = await command(
        game,
        identity,
        '/world generate north --rooms 1 --buildings 0 --theme "A hall with a locked chest and a rug."',
    )
    assert reply["success"], reply
    assert "3 objects" in reply["output"]
    assert "cedar chest key" in reply["output"]
    assert "hidden_under faded rug" in reply["output"]
    assert "container_chest_wooden" in reply["output"]
    assert "locked" in reply["output"]
    async with session_factory() as session:
        assert not (
            await session.scalars(select(ItemRecord).where(ItemRecord.template_id.is_not(None)))
        ).all()
    reply = await command(game, identity, f'/world approve {reply["proposal_id"]}')
    assert reply["success"], reply
    assert (await command(game, identity, "north"))["success"]
    locked = await command(game, identity, "open cedar chest")
    assert not locked["success"] and "locked" in locked["output"]
    assert (await command(game, identity, "look under faded rug"))["success"]
    assert (await command(game, identity, "take cedar chest key"))["success"]
    assert (await command(game, identity, "unlock cedar chest with cedar chest key"))["success"]
    assert (await command(game, identity, "open cedar chest"))["success"]


def test_legacy_generated_objects_preserve_generation_provenance():
    from app.ai.neighborhood import NeighborhoodDraft, materialize_objects

    content = template_draft().model_dump()
    for obj in content["objects"]:
        obj.update(template_id=None, locked=False, key_room=None, hiding_place=None)
    objects = materialize_objects(NeighborhoodDraft.model_validate(content))
    assert objects
    assert all(item.provenance.get("source") == "ai_generated" for item in objects.values())


def test_generated_templates_reject_unsupported_capabilities_and_inaccessible_keys():
    from app.ai.neighborhood import NeighborhoodDraft, normalize_topology, NeighborhoodRequest
    from pydantic import ValidationError

    content = template_draft().model_dump()
    content["objects"][0]["template_id"] = "magic_execute_code"
    with pytest.raises(ValidationError, match="registered templates"):
        NeighborhoodDraft.model_validate(content)
    content = template_draft().model_dump()
    content["objects"][0]["hiding_place"] = "missing"
    with pytest.raises(ValidationError, match="reference"):
        NeighborhoodDraft.model_validate(content)
    request = NeighborhoodRequest(
        brief="Hall",
        origin_name="Forest",
        anchor_name="Forest",
        anchor_description="Trees.",
        direction="north",
        max_rooms=1,
        max_buildings=0,
    )
    assert normalize_topology(content, request) is None
