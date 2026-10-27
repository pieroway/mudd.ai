"""Authored, validated catalogue. Behavior lives in reusable capability rules."""

from copy import deepcopy
from typing import Any

from app.domain.item_template import ItemTemplate, ItemTemplateRegistry

GROUPS = {
    "weapon": "dagger_iron sword_short sword_long axe_hand club_wooden staff_oak bow_hunting arrow crossbow sling",
    "armour": "helmet_leather helmet_iron tunic_leather mail_shirt shield_wooden",
    "clothing": "cloak_wool boots_leather gloves_leather belt_leather backpack pouch",
    "jewellery": "ring_plain amulet",
    "container": "chest_wooden chest_iron crate_wooden barrel sack_burlap basket_wicker bottle_glass flask bucket lockbox",
    "key": "iron_small brass_ornate rusted skeleton",
    "access": "keycard seal",
    "food": "bread_loaf apple dried_meat",
    "drink": "water ale",
    "potion": "healing_minor antidote",
    "herb": "medicinal",
    "poison": "vial",
    "ration": "travel",
    "tool": "lockpick rope_hemp hammer crowbar shovel pickaxe hatchet fishing_rod needle_thread flint_steel waterskin compass spyglass",
    "light": "torch lantern_oil candle brazier",
    "fuel": "lamp_oil firewood",
    "readable": "book scroll letter ledger notice map inscription journal label sign",
    "currency": "coin_copper coin_silver coin_gold",
    "valuable": "gem_uncut gem_cut ring_gold goblet_silver statue_small pearl",
    "material": "wood_log wood_plank iron_ore iron_ingot leather cloth herb bone stone clay",
    "furniture": "table_wooden chair_wooden bed bookshelf cabinet desk rug mirror bench wardrobe weapon_rack painting",
    "fixture": "fireplace door_wooden gate_iron trapdoor floorboard_loose wall_cracked window_glass lever button chain iron_ring ladder stairs well fountain statue altar tree rock bush hole loose_soil",
    "vehicle": "rowboat fishing_skiff cart wagon canoe",
    "mount": "saddle",
    "quest": "token relic package badge fragment evidence body_part sealed_letter",
    "remains": "corpse_humanoid skeleton bones_pile",
    "loot": "coin_purse satchel cache_hidden",
    "magic": "wand scroll ring orb stone portal_key potion weapon",
}

PRIORITY: dict[str, dict[str, Any]] = {
    "weapon_sword_short": dict(
        name="short sword",
        aliases=["sword", "blade", "short blade"],
        material="iron",
        weight=1.4,
        capabilities={
            "wieldable": {"slots": ["left_hand", "right_hand"]},
            "usable": {"actions": ["cut", "slash", "stab", "pry"]},
            "breakable": {"hardness": 60, "maximum_durability": 100},
        },
    ),
    "weapon_dagger_iron": dict(
        name="iron dagger",
        aliases=["dagger", "knife"],
        material="iron",
        weight=0.4,
        capabilities={
            "wieldable": {"slots": ["left_hand", "right_hand"]},
            "usable": {"actions": ["cut", "stab"]},
        },
    ),
    "clothing_backpack": dict(
        name="leather backpack",
        aliases=["backpack", "pack", "leather pack"],
        material="leather",
        weight=1.2,
        capabilities={
            "wearable": {"slots": ["back"]},
            "container": {"capacity_litres": 30, "maximum_weight_kg": 22, "opening_width_cm": 34},
            "openable": {},
            "closeable": {},
            "searchable": {},
            "repairable": {},
        },
    ),
    "clothing_cloak_wool": dict(
        name="wool cloak",
        aliases=["cloak"],
        material="wool",
        weight=1,
        capabilities={"wearable": {"slots": ["shoulders"]}, "foldable": {}},
    ),
    "container_chest_wooden": dict(
        name="wooden chest",
        aliases=["chest", "storage chest"],
        material="oak",
        weight=32,
        size="large",
        portable=False,
        dimensions=dict(length=90, width=48, height=50),
        capabilities={
            "movable": {"strength_required": 14},
            "openable": {},
            "closeable": {},
            "container": {"capacity_litres": 140, "maximum_weight_kg": 100, "opening_width_cm": 80},
            "lockable": {"pickable": True, "difficulty": 10},
            "searchable": {},
            "breakable": {"hardness": 35, "maximum_durability": 120},
        },
    ),
    "container_crate_wooden": dict(
        name="wooden crate",
        aliases=["crate"],
        material="wood",
        weight=12,
        size="large",
        portable=False,
        capabilities={
            "container": {"capacity_litres": 100, "maximum_weight_kg": 80},
            "openable": {},
            "closeable": {},
            "pryable": {},
            "movable": {"strength_required": 10},
        },
    ),
    "container_bottle_glass": dict(
        name="glass bottle",
        aliases=["bottle"],
        material="glass",
        weight=0.3,
        size="small",
        capabilities={
            "container": {"capacity_litres": 1, "maximum_weight_kg": 1, "opening_width_cm": 2},
            "openable": {},
            "closeable": {},
            "fillable": {"capacity_litres": 1},
            "pourable": {},
        },
    ),
    "key_brass_ornate": dict(
        name="ornate brass key",
        aliases=["key", "brass key", "ornate key"],
        material="brass",
        weight=0.05,
        size="tiny",
        capabilities={"usable": {"actions": ["unlock", "lock"]}},
    ),
    "tool_lockpick": dict(
        name="lockpick",
        aliases=["pick", "lock pick"],
        material="iron",
        weight=0.05,
        size="tiny",
        capabilities={"usable": {"actions": ["pick_lock"], "skill_bonus": 5}},
    ),
    "tool_rope_hemp": dict(
        name="coil of hemp rope",
        aliases=["rope", "coil", "hemp rope"],
        material="hemp",
        weight=2.1,
        capabilities={
            "tieable": {
                "compatible_targets": ["ring", "post", "tree", "hook", "anchor", "sturdy_fixture"]
            },
            "attachable": {},
            "detachable": {},
            "climbable": {"requires_secure_attachment": True, "maximum_load_kg": 180},
            "throwable": {"maximum_range_m": 8},
            "usable": {"actions": ["bind", "tow", "lower", "raise"]},
        },
    ),
    "tool_crowbar": dict(
        name="iron crowbar",
        aliases=["crowbar", "pry bar"],
        material="iron",
        weight=2,
        capabilities={"usable": {"actions": ["pry", "break"], "power": 50}},
    ),
    "light_torch": dict(
        name="wooden torch",
        aliases=["torch", "unlit torch", "burning torch"],
        material="wood",
        weight=0.7,
        capabilities={
            "lightable": {"requires_ignition_source": True},
            "extinguishable": {},
            "usable": {"actions": ["illuminate", "ignite"]},
            "breakable": {"maximum_durability": 30},
        },
        state={"lit": False, "fuel_remaining": 30},
    ),
    "potion_healing_minor": dict(
        name="minor healing potion",
        aliases=["potion", "healing potion"],
        material="glass",
        weight=0.2,
        size="small",
        capabilities={"consumable": {"effect": "heal", "amount": 20}},
    ),
    "readable_letter": dict(
        name="folded letter",
        aliases=["letter", "note", "paper"],
        material="paper",
        weight=0.01,
        size="tiny",
        capabilities={
            "readable": {"content_source": "instance", "requires_language": "common"},
            "openable": {},
            "breakable": {"maximum_durability": 5, "hardness": 0},
            "searchable": {"searchable_parts": ["front", "back", "folds", "seal"]},
        },
    ),
    "currency_coin_copper": dict(
        name="copper coin",
        aliases=["coin", "coins", "copper"],
        material="copper",
        weight=0.01,
        size="tiny",
        capabilities={"stackable": {"maximum_quantity": 1000000}},
    ),
    "furniture_table_wooden": dict(
        name="wooden table",
        aliases=["table"],
        material="wood",
        weight=20,
        size="large",
        portable=False,
        capabilities={"surface": {"maximum_weight_kg": 80}, "movable": {"strength_required": 10}},
    ),
    "furniture_rug": dict(
        name="woven rug",
        aliases=["rug", "carpet"],
        material="wool",
        weight=3,
        portable=False,
        capabilities={"movable": {"strength_required": 1}, "searchable": {}, "foldable": {}},
    ),
    "fixture_floorboard_loose": dict(
        name="loose floorboard",
        aliases=["floorboard", "board", "floorboards"],
        material="wood",
        weight=2,
        portable=False,
        capabilities={"searchable": {}, "pryable": {}, "movable": {"strength_required": 5}},
    ),
    "fixture_iron_ring": dict(
        name="iron ring",
        aliases=["ring", "dock ring"],
        material="iron",
        weight=2,
        portable=False,
        capabilities={"attachable": {"secure": True, "maximum_load_kg": 300}, "tieable": {}},
    ),
    "vehicle_fishing_skiff": dict(
        name="fishing skiff",
        aliases=["skiff", "boat", "fishing boat"],
        material="wood",
        weight=145,
        size="huge",
        portable=False,
        capabilities={
            "enterable": {"maximum_occupants": 4},
            "pilotable": {
                "environments": ["river", "lake", "sheltered_water"],
                "required_equipment": ["oar"],
            },
            "container": {"capacity_litres": 900, "maximum_weight_kg": 500},
            "movable": {"strength_required": 20},
            "tieable": {},
            "attachable": {},
            "repairable": {"compatible_materials": ["wood_plank", "rope", "pitch"]},
            "breakable": {"hardness": 25, "maximum_durability": 200},
        },
        state={"afloat": False, "tied": False, "leaking": False},
    ),
}


def build_catalogue() -> ItemTemplateRegistry:
    templates: list[ItemTemplate] = []
    for group, names in GROUPS.items():
        for suffix in names.split():
            template_id = f"{group}_{suffix}"
            override = deepcopy(PRIORITY.get(template_id, {}))
            name = override.get("name", suffix.replace("_", " "))
            portable = override.get(
                "portable", group not in {"fixture", "furniture", "vehicle", "remains"}
            )
            caps: dict[str, dict[str, Any]] = {
                "examinable": {},
                "searchable": {},
                "breakable": {"maximum_durability": 50, "hardness": 10},
            }
            if portable:
                caps.update({"takeable": {}, "holdable": {"required_hands": 1}})
            if group == "weapon":
                caps.update(
                    {
                        "wieldable": {"slots": ["left_hand", "right_hand"]},
                        "usable": {"actions": ["cut", "break"], "power": 40},
                    }
                )
            if template_id == "weapon_staff_oak":
                caps["usable"]["actions"].append("paddle")
            if group in {"clothing", "armour", "jewellery", "mount"}:
                caps["wearable"] = {"slots": ["body" if group == "armour" else suffix]}
            if group in {"container", "loot"}:
                caps.update(
                    {
                        "container": {"capacity_litres": 20, "maximum_weight_kg": 15},
                        "openable": {},
                        "closeable": {},
                    }
                )
            if group in {"readable"}:
                caps["readable"] = {"content_source": "instance"}
            if group in {"currency", "material", "fuel"}:
                caps["stackable"] = {"maximum_quantity": 1000000}
            if group in {"food", "drink", "ration", "herb"}:
                caps["consumable"] = {"effect": "nourish", "amount": 5}
            if group == "light" or template_id == "fixture_fireplace":
                caps.update({"lightable": {}, "extinguishable": {}})
            if group == "furniture":
                caps["movable"] = {"strength_required": 10}
                if suffix in {"chair_wooden", "bench", "bed"}:
                    caps["sittable"] = {}
                if suffix == "bed":
                    caps["lieable"] = {}
                if suffix in {"table_wooden", "desk", "bookshelf", "weapon_rack"}:
                    caps["surface"] = {"maximum_weight_kg": 60}
            if group == "vehicle":
                caps.update(
                    {"enterable": {"maximum_occupants": 2}, "movable": {"strength_required": 20}}
                )
            if group == "key":
                caps["usable"] = {"actions": ["unlock", "lock"]}
            if group == "tool" and suffix in {"hammer", "needle_thread"}:
                caps["usable"] = {"actions": ["repair"], "power": 20}
            if template_id == "tool_flint_steel":
                caps["usable"] = {"actions": ["ignite"]}
            if group == "tool" and suffix in {"shovel", "pickaxe", "hatchet"}:
                caps["usable"] = {"actions": ["dig", "harvest", "break"], "power": 40}
            if group == "fixture" and suffix in {"hole", "loose_soil"}:
                caps["diggable"] = {}
            if group == "fixture" and suffix in {"tree", "bush"}:
                caps["harvestable"] = {}
            if group == "fixture" and suffix in {"lever", "button"}:
                caps["switchable"] = {}
            if group == "fixture" and suffix in {"ladder", "stairs"}:
                caps["climbable"] = {"maximum_load_kg": 300}
            caps.update(override.get("capabilities", {}))
            # Every capability offered here has a deterministic handler or explicit failure.
            state: dict[str, Any] = {
                "durability": caps["breakable"]["maximum_durability"],
                "broken": False,
                "wet": False,
            }
            if "openable" in caps:
                state["open"] = False
            if "lightable" in caps:
                state.update({"lit": False, "fuel_remaining": 30})
            if "lockable" in caps:
                state["locked"] = False
            state.update(override.get("state", {}))
            templates.append(
                ItemTemplate.model_validate(
                    {
                        "template_id": template_id,
                        "name": name,
                        "aliases": override.get("aliases", [suffix.replace("_", " ")]),
                        "categories": [group],
                        "description": {
                            "short": f"a {name}",
                            "examine": f"The {name} bears the marks of careful craftsmanship.",
                        },
                        "material": override.get(
                            "material", "wood" if not portable else "mixed materials"
                        ),
                        "physical": {
                            "weight_kg": override.get("weight", 1 if portable else 20),
                            "size": override.get("size", "medium"),
                            "portable": portable,
                            "dimensions_cm": override.get("dimensions", {}),
                        },
                        "capabilities": caps,
                        "default_state": state,
                        "stackable": "stackable" in caps,
                        "equipment_slots": caps.get("wearable", caps.get("wieldable", {})).get(
                            "slots", []
                        ),
                    }
                )
            )
    return ItemTemplateRegistry(templates)


CATALOGUE = build_catalogue()
