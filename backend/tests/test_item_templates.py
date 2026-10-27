import pytest
from pydantic import ValidationError

from app.domain.item import Item
from app.domain.item_template import ItemTemplate, ItemTemplateRegistry


def sword_template() -> ItemTemplate:
    return ItemTemplate.model_validate(
        {
            "template_id": "weapon_sword_short",
            "name": "short sword",
            "aliases": ["sword", "blade", "short blade"],
            "categories": ["weapon", "blade"],
            "description": {
                "short": "a short iron sword",
                "examine": "The blade is practical and unadorned.",
            },
            "material": "iron",
            "physical": {"weight_kg": 1.4, "size": "medium", "portable": True},
            "capabilities": {
                "examinable": {},
                "takeable": {},
                "holdable": {"required_hands": 1},
                "wieldable": {"slots": ["left_hand", "right_hand"]},
                "usable": {"actions": ["cut", "slash", "stab", "pry"]},
                "breakable": {"hardness": 60, "maximum_durability": 100},
            },
            "default_state": {"durability": 100, "wet": False, "broken": False},
            "value": {"amount": 35, "currency": "copper"},
        }
    )


def test_template_creates_isolated_instances() -> None:
    template = sword_template()

    first = Item.from_template("sword_1", template, room_id="town_square")
    second = Item.from_template("sword_2", template, room_id="town_square")

    first.state["wet"] = True
    first.capabilities["usable"]["actions"].append("chop")
    first.provenance["source"] = "procedural"

    assert second.state["wet"] is False
    assert second.capabilities["usable"]["actions"] == ["cut", "slash", "stab", "pry"]
    assert second.provenance == {"source": "authored"}
    assert template.default_state["wet"] is False
    assert template.capabilities["usable"]["actions"] == ["cut", "slash", "stab", "pry"]


def test_template_populates_legacy_and_physical_instance_fields() -> None:
    item = Item.from_template("sword_1", sword_template(), room_id="blacksmith")

    assert item.template_id == "weapon_sword_short"
    assert item.description == "The blade is practical and unadorned."
    assert item.aliases == ("sword", "blade", "short blade")
    assert item.material == "iron"
    assert item.weight_kg == 1.4
    assert item.size == "medium"
    assert item.portable is True
    assert item.can_use is True
    assert item.has_capability("wieldable")
    assert item.durability == 100
    assert item.maximum_durability == 100


def test_template_rejects_unknown_capabilities() -> None:
    data = sword_template().model_dump()
    data["capabilities"]["teleportable"] = {}

    with pytest.raises(ValidationError, match="unsupported capabilities: teleportable"):
        ItemTemplate.model_validate(data)


def test_registry_rejects_duplicate_template_ids() -> None:
    template = sword_template()

    with pytest.raises(ValueError, match="duplicate item template: weapon_sword_short"):
        ItemTemplateRegistry([template, template.model_copy(deep=True)])


@pytest.mark.parametrize(
    ("locations", "message"),
    [
        ({}, "exactly one location"),
        (
            {"room_id": "town_square", "owned_by": "player_1"},
            "exactly one location",
        ),
    ],
)
def test_instance_requires_exactly_one_location(locations: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Item.from_template("sword_1", sword_template(), **locations)
