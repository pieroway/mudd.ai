"""Building topology belongs to the engine, never the language model."""

import json

import httpx
import pytest

from app.ai.fake import fake_building
from app.ai.neighborhood import NeighborhoodRequest, building_levels, validate_budget
from tests.test_ai.test_openai_provider import envelope, provider


def building_request(
    direction="east", floors=3, rooms_per_floor=4, main_rooms=2, basement_levels=2
):
    return NeighborhoodRequest(
        brief="The Lantern House with a great room, kitchen, cellar and lower chamber.",
        origin_name="North Street",
        anchor_name="North Street",
        anchor_description="A cobbled street.",
        direction=direction,
        max_rooms=floors * rooms_per_floor + main_rooms + basement_levels,
        max_buildings=1,
        floors=floors,
        rooms_per_floor=rooms_per_floor,
        main_rooms=main_rooms,
        basement_levels=basement_levels,
    )


async def allowed():
    return True


async def test_building_content_does_not_need_ai_connections():
    request = building_request()
    payload = fake_building(request).model_dump()
    # This content would be disconnected without engine-owned routes.
    del payload["connections"]
    calls = []

    def handler(http_request):
        calls.append(json.loads(http_request.content))
        return httpx.Response(200, json=envelope(json.dumps(payload)))

    draft = await provider(handler).generate_neighborhood(request, before_dispatch=allowed)
    validate_budget(draft, request)
    assert sorted(building_levels(draft).values()) == [-2, -1] + [0] * 6 + [1] * 4 + [2] * 4
    assert len(calls) == 1
    wire = calls[0]
    assert "connections" not in wire["text"]["format"]["schema"]["properties"]
    context = json.loads(wire["input"][0]["content"])
    assert len(context["layout"]) == 16
    assert {slot["key"] for slot in context["layout"]} == {room.key for room in draft.rooms}
    assert wire["store"] is False and "tools" not in wire


@pytest.mark.parametrize("direction", ["north", "east", "south", "west"])
@pytest.mark.parametrize("counts", [(1, 1, 0, 0), (3, 4, 2, 2), (5, 4, 1, 3)])
async def test_engine_layout_respects_counts_and_preserves_objects(direction, counts):
    request = building_request(direction, *counts)
    payload = fake_building(request).model_dump()
    del payload["connections"]
    key = payload["rooms"][-1]["key"]
    payload["objects"] = [
        {
            "key": "table",
            "name": "oak table",
            "description": "An oak table stands here.",
            "kind": "fixture",
            "room": key,
            "container": None,
            "interaction_target": None,
        }
    ]
    adapter = provider(lambda _: httpx.Response(200, json=envelope(json.dumps(payload))))
    draft = await adapter.generate_neighborhood(request, before_dispatch=allowed)
    validate_budget(draft, request)
    assert draft.objects[0].room == key
    assert len(draft.rooms) == request.max_rooms
    assert len(draft.connections) == request.max_rooms
    assert (
        next(edge.direction for edge in draft.connections if edge.source == "anchor") == direction
    )


@pytest.mark.parametrize(
    "corruption", ["missing", "duplicate", "unknown_key", "building", "extra", "object_room"]
)
async def test_bad_building_content_is_rejected(corruption):
    from app.ai.provider import AIProviderFailure

    request = building_request()
    payload = fake_building(request).model_dump()
    del payload["connections"]
    if corruption == "missing":
        payload["rooms"].pop()
    elif corruption == "duplicate":
        payload["rooms"][0] = payload["rooms"][1]
    elif corruption == "unknown_key":
        payload["rooms"][0]["key"] = "invented_room"
    elif corruption == "building":
        payload["rooms"][0]["building"] = "invented_building"
    elif corruption == "extra":
        payload["reward"] = 100
    else:
        payload["objects"] = [
            {
                "key": "table",
                "name": "oak table",
                "description": "An oak table stands here.",
                "kind": "fixture",
                "room": "missing_room",
                "container": None,
                "interaction_target": None,
            }
        ]
    adapter = provider(lambda _: httpx.Response(200, json=envelope(json.dumps(payload))))
    with pytest.raises(AIProviderFailure):
        await adapter.generate_neighborhood(request, before_dispatch=allowed)


async def test_engine_layout_preserves_generated_lock_and_key_references():
    from app.ai.neighborhood import materialize_objects

    request = building_request()
    payload = fake_building(request).model_dump()
    del payload["connections"]
    payload["rooms"].reverse()  # Provider ordering cannot change floor assignments.
    payload["objects"] = [
        {
            "key": "chest",
            "name": "oak chest",
            "description": "An oak chest stands here.",
            "kind": "container",
            "room": "room_16",
            "container": None,
            "interaction_target": None,
            "template_id": "container_chest_wooden",
            "locked": True,
            "key_room": "room_3",
            "hiding_place": "rug",
        },
        {
            "key": "rug",
            "name": "wool rug",
            "description": "A wool rug covers the floor.",
            "kind": "fixture",
            "room": "room_3",
            "container": None,
            "interaction_target": None,
            "template_id": "furniture_rug",
        },
    ]
    adapter = provider(lambda _: httpx.Response(200, json=envelope(json.dumps(payload))))
    draft = await adapter.generate_neighborhood(request, before_dispatch=allowed)
    assert draft.objects[0].key_room == "room_3"
    assert draft.objects[0].hiding_place == "rug"
    items = materialize_objects(draft)
    assert len(items) == 3  # Chest, rug, and the engine-provisioned matching key.
