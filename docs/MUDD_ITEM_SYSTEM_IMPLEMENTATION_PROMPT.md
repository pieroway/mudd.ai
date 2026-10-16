# MUDD Item and Object Interaction System — Codex Implementation Prompt

Inspect my existing MUDD project and improve its item and object-interaction system. Do not assume its architecture, language, database schema, or naming conventions. First examine the repository and identify how rooms, exits, players, hands, equipment, inventories, commands, objects, persistence, APIs, frontend displays, procedural generation, and AI-generated content currently work.

Preserve existing working behaviour unless these requirements intentionally change it. Reuse existing models, services, migrations, validators, APIs, command handlers, and test conventions where practical. Do not stop after planning unless there is a genuine blocker: inspect, report what you found, plan briefly, implement, test, and report exact results.

## Primary goal

Make nearly everything in the world meaningfully interactable. Items and environmental objects must be stateful entities whose interactions and descriptions depend on identity, capabilities, physical state, location, containment/support relationships, owner, holder, equipment slot, current use, room conditions, and the observing player's knowledge.

The deterministic engine and database remain authoritative. AI may propose flavour and structured content, but may not contradict stored state, determine action success, execute arbitrary code, bypass permissions, or introduce unsupported capabilities.

## 1. Templates and instances

Separate reusable templates from individual instances. A template such as `weapon_sword_short` defines a kind of object. An instance such as `item_84721` stores one sword's location, owner, state, condition, relationships, and provenance. Changing one instance must not change all items from that template.

Templates should support stable IDs, names, aliases, categories, base descriptions, material, dimensions, weight, portability, value, rarity, default capabilities/state/durability, equipment slots, stackability, and gameplay attributes.

Instances should support unique IDs, template references, authoritative location, ownership, state, condition, quantity, contents, custom overrides, discovery, relationships, lock/key associations, provenance, and timestamps.

## 2. Proposed logical data contract

The YAML below is a design contract, not a mandate to store YAML. Translate it into the project's existing Python models, database schema, JSON, seed files, or other conventions.

```yaml
# Reusable template
template_id: string
name: string
aliases: []
categories: []
description:
  short: string
  examine: string
material: string
physical:
  weight_kg: number
  size: tiny | small | medium | large | huge
  dimensions_cm: {length: null, width: null, height: null}
  portable: boolean
capabilities: {}
default_state: {}
value: {amount: number, currency: copper}
rarity: common | uncommon | rare | legendary

---
# Individual instance
instance_id: string
template_id: string
custom: {name: null, description: null}
location:
  relationship: in_room | contained_in | resting_on | held_by | worn_by | attached_to | hidden_under
  target_id: string
  slot: null
ownership: {owner_id: null}
state: {}
condition: {durability: number, maximum_durability: number, broken: false}
quantity: 1
relationships: {}
discovery: {hidden: false, discovered_by: []}
provenance: {source: authored | procedural | ai_generated, generation_reason: null}
created_at: timestamp
updated_at: timestamp
```

## 3. Capability-based interaction system

Objects declare reusable capabilities rather than receiving bespoke command code. Support extensibility for capabilities such as:

- examinable, takeable, droppable, movable, holdable, wearable, wieldable, usable, readable;
- openable, closeable, lockable, pickable, searchable, container, surface;
- sittable, lieable, enterable, pilotable, traversable;
- breakable, repairable, consumable, stackable;
- lightable, extinguishable, climbable, attachable, detachable, tieable;
- throwable, pushable, pullable, switchable, fillable, pourable;
- diggable, harvestable, loadable, foldable, and pryable.

Capabilities may configure required hands, valid slots, capacity, maximum weight, opening size, permitted contents, strength, hardness, durability, fuel, charges, range, compatible attachments, supported load, lock difficulty, effects, and valid targets.

Commands query capabilities, state, relationships, permissions, and physical constraints. Examples:

- `open chest` checks that it is openable, closed, accessible, and unlocked.
- `unlock chest with brass key` checks lock/key compatibility.
- `pick chest lock` checks tool, skill, and difficulty.
- `break chest with axe` checks hardness, durability, and tool effectiveness.
- `put sword in chest` checks open state, capacity, opening dimensions, and permissions.
- `push cabinet` checks movability and strength.
- `tie rope to ring` checks compatible attachment capabilities.
- `climb rope` checks that it is securely attached and supports the load.
- `take skiff` must not put a boat in normal inventory.

Return useful in-world failures such as “The chest is locked,” “The skiff will not fit inside your backpack,” “Secure the rope before climbing it,” or “Your hands are full,” instead of generic invalid-command errors.

Preserve existing natural-language parsing but route resolved actions through deterministic rules.

## 4. Explicit relationships

Model relationships as data rather than prose, including:

- in a room, on a surface, in a container, covered by, hidden beneath;
- owned by, carried by, held in a specific hand, worn/equipped in a slot;
- attached to, tied to, opens/unlocks, used on;
- boarded/occupied by, or concealing another object.

Ownership, inventory, containment, holding, equipping, and active use are distinct. A player can own a torch stored in a backpack, hold it without lighting it, then light it to illuminate the room.

## 5. Context-aware descriptions

Fix the existing problem where an item has the same description everywhere. Store facts, then compose text for the current context. Support descriptions for room listings, named surfaces, open containers, inventory, backpacks, the viewer's hands, another character's hands, equipment, active use, placement, close examination, and physical states such as damaged, wet, burning, empty, open, or locked.

Example for one sword:

- Room: “A notched iron sword lies in the mud beside the road.”
- Surface: “A notched iron sword rests across the oak table.”
- Player holding: “You hold a notched iron sword in your right hand.”
- Another character: “Mara carries a notched iron sword loosely at her side.”
- Inventory: “A notched iron sword is secured to your pack.”
- Equipped: “You wield a notched iron sword in your right hand.”
- Active use: “You drive the notched iron sword into the rotten boards.”
- Examination: “The blade is badly notched, but its leather grip remains firm.”

Conceptually:

```text
identity + state + spatial relationship + current action
+ surroundings + viewer knowledge = contextual presentation
```

Descriptions must never contradict authoritative state. Prefer deterministic rendering. If an LLM improves prose, give it only permitted structured facts, constrain/validate its result, and retain a non-AI fallback.

## 6. Viewer-relative descriptions and discovery

Account for first-person wording, other characters, hidden details, search/examination discoveries, darkness, light, weather, visibility, perception/skills already present, identification state, container visibility, and administrator visibility.

Do not reveal hidden compartments, keys, inscriptions, container contents, or unidentified magical properties until discovered. Persist discovery state where appropriate.

## 7. Generated locks, keys, and clues

When generating a locked object:

1. Create the object and lock.
2. Safely reuse a suitable existing key if one exists; otherwise generate a matching key from a reusable template.
3. Store a stable key-to-lock relationship.
4. Place the key in the current room or normally within one to three reachable rooms.
5. It may be visible, hidden, in an accessible container, held by an accessible NPC, or obtainable through a small interaction.
6. If hidden, generate discoverable clues and hiding-place interactions.
7. Validate solvability and persist relationship/provenance.

Placement must fit the setting. For example, an old dockside chest might have a tarnished brass key beneath a loose floorboard in a nearby fisherman's hut.

Never put a required key inside its own locked container. Detect indirect cycles such as Chest A requiring Key A in Chest B while Chest B requires Key B in Chest A. Model access dependencies as a graph or equivalent and validate reachability from player-accessible state.

Also prevent inaccessible NPC holders, orphaned locks, removal of the only critical key, and regeneration that breaks dependencies. Model explicit alternative solutions such as lock picking, breaking, magic, or persuasion rather than assuming them.

A hidden object must be discoverable without guessing one exact phrase. Support interactions such as `search room`, `look under rug`, `move rug`, `examine floorboards`, `lift floorboard`, and `pry up board with crowbar`.

## 8. Physical constraints and state transitions

Where appropriate, consider dimensions, weight, container capacity/opening, hands, carrying capacity, strength, material, hardness, durability, fixed placement, equipment, attachments, and liquid vessels. Keep this practical rather than simulating full physics.

Support validated states such as open/closed, locked/unlocked, lit/unlit, wet/dry, intact/damaged/broken, full/partial/empty, hidden/discovered, attached/detached, tied/untied, folded/unfolded, active/inactive, charges, fuel, quantity, and durability.

Integrate with an existing event system or add only a small clean mechanism for exceptional `on_pickup`, `on_drop`, `on_examine`, `on_search`, `on_open`, `on_unlock`, `on_use`, `on_break`, `on_repair`, containment, and state-change events. Ordinary behaviour belongs in capabilities and rules.

## 9. Representative template definitions

Implement these concepts using current project conventions.

```yaml
template_id: weapon_sword_short
name: short sword
aliases: [sword, blade, short blade]
categories: [weapon, blade]
description:
  short: a short iron sword
  examine: The blade is practical and unadorned, with a leather-wrapped grip.
material: iron
physical: {weight_kg: 1.4, size: medium, portable: true}
capabilities:
  examinable: {}
  takeable: {}
  holdable: {required_hands: 1}
  wieldable: {slots: [left_hand, right_hand]}
  usable: {actions: [cut, slash, stab, pry]}
  breakable: {hardness: 60, maximum_durability: 100}
default_state: {durability: 100, wet: false, broken: false}
value: {amount: 35, currency: copper}
rarity: common
```

```yaml
template_id: clothing_backpack
name: leather backpack
aliases: [backpack, pack, leather pack]
categories: [clothing, container]
description:
  short: a weathered leather backpack
  examine: Its thick leather flap is secured by two brass buckles.
material: leather
physical: {weight_kg: 1.2, size: medium, portable: true}
capabilities:
  examinable: {}
  takeable: {}
  wearable: {slots: [back]}
  openable: {}
  closeable: {}
  container: {capacity_litres: 30, maximum_weight_kg: 22, opening_width_cm: 34}
  searchable: {}
  repairable: {}
default_state: {open: false, condition: 85}
value: {amount: 18, currency: copper}
rarity: common
```

```yaml
template_id: container_chest_wooden
name: wooden chest
aliases: [chest, wooden chest, storage chest]
categories: [container, furniture]
description:
  short: a heavy wooden chest
  examine: Iron bands reinforce the chest, and a keyhole is set beneath its lid.
material: oak
physical:
  weight_kg: 32
  size: large
  dimensions_cm: {length: 90, width: 48, height: 50}
  portable: false
capabilities:
  examinable: {}
  movable: {strength_required: 14}
  openable: {}
  closeable: {}
  container: {capacity_litres: 140, maximum_weight_kg: 100, opening_width_cm: 80}
  lockable: {supports_generated_lock: true, pickable: true}
  searchable: {supports_hidden_compartments: true}
  breakable: {hardness: 35, maximum_durability: 120}
default_state: {open: false, locked: false, durability: 120, hidden_compartments_discovered: false}
value: {amount: 25, currency: copper}
rarity: common
```

```yaml
template_id: key_brass_ornate
name: ornate brass key
aliases: [key, brass key, ornate key]
categories: [key, access_item]
description:
  short: a small ornate brass key
  examine: Fine curling patterns surround the key's unusually shaped teeth.
material: brass
physical: {weight_kg: 0.05, size: tiny, portable: true}
capabilities:
  examinable: {}
  takeable: {}
  holdable: {required_hands: 1}
  usable: {actions: [unlock, lock]}
  breakable: {hardness: 25, maximum_durability: 25}
default_state: {durability: 25, broken: false}
value: {amount: 2, currency: copper}
rarity: uncommon
```

```yaml
instance_id: key_1042
template_id: key_brass_ornate
location: {relationship: hidden_under, target_id: floorboard_203, slot: null}
relationships: {opens: [lock_1042]}
discovery: {hidden: true, difficulty: 12, discovered_by: []}
provenance: {source: procedural, generation_reason: required_key_for_lock_1042}
```

```yaml
template_id: tool_rope_hemp
name: coil of hemp rope
aliases: [rope, coil, hemp rope]
categories: [tool]
description:
  short: a coil of weathered hemp rope
  examine: The rope is about fifteen metres long and smells faintly of river water.
material: hemp
physical: {weight_kg: 2.1, size: medium, portable: true}
capabilities:
  examinable: {}
  takeable: {}
  holdable: {required_hands: 1}
  tieable: {compatible_targets: [ring, post, tree, hook, anchor, sturdy_fixture]}
  attachable: {}
  climbable: {requires_secure_attachment: true, maximum_load_kg: 180}
  throwable: {maximum_range_m: 8}
  usable: {actions: [bind, tow, lower, raise]}
  breakable: {hardness: 12, maximum_durability: 60}
default_state: {tied: false, attached_to: null, wet: false, durability: 60}
value: {amount: 12, currency: copper}
rarity: common
```

```yaml
template_id: light_torch
name: wooden torch
aliases: [torch, unlit torch, burning torch]
categories: [tool, light_source]
description:
  short: a pitch-wrapped wooden torch
  examine: Cloth and pitch are wrapped tightly around one end of a wooden shaft.
material: wood
physical: {weight_kg: 0.7, size: medium, portable: true}
capabilities:
  examinable: {}
  takeable: {}
  holdable: {required_hands: 1}
  lightable: {requires_ignition_source: true}
  extinguishable: {}
  usable: {actions: [illuminate, ignite]}
  breakable: {maximum_durability: 30}
default_state: {lit: false, fuel_seconds: 1800, durability: 30}
effects: {when_lit: {light_radius: 2, heat: 5}}
```

```yaml
template_id: readable_letter
name: folded letter
aliases: [letter, note, paper]
categories: [readable, document]
description:
  short: a folded sheet of paper
  examine: The paper is creased, stained, and covered with hurried handwriting.
material: paper
physical: {weight_kg: 0.01, size: tiny, portable: true}
capabilities:
  examinable: {}
  takeable: {}
  readable: {content_source: instance, requires_language: common}
  openable: {}
  searchable: {searchable_parts: [front, back, folds, seal]}
  breakable: {maximum_durability: 5}
default_state: {open: false, wet: false, torn: false, durability: 5}
```

```yaml
template_id: vehicle_fishing_skiff
name: fishing skiff
aliases: [skiff, boat, fishing boat]
categories: [vehicle, watercraft]
description:
  short: a weathered fishing skiff
  examine: The shallow wooden boat bears years of scratches, patched seams, and river stains.
material: wood
physical: {weight_kg: 145, size: huge, portable: false}
capabilities:
  examinable: {}
  enterable: {maximum_occupants: 4}
  pilotable: {environments: [river, lake, sheltered_water], required_equipment: [oar]}
  container: {capacity_litres: 900, maximum_weight_kg: 500}
  movable: {strength_required: 20, cooperative_movement: true}
  tieable: {compatible_targets: [dock_ring, post, anchor, tree]}
  attachable: {}
  repairable: {compatible_materials: [wood_plank, rope, pitch]}
  breakable: {hardness: 25, maximum_durability: 200}
default_state: {afloat: false, tied: false, boarded_by: [], durability: 150, leaking: false}
```

## 10. Standard template catalogue

Create data-driven catalogue entries for all templates below. Each needs a stable ID, aliases, categories, physical defaults, base descriptions, and applicable capability configuration. Do not create separate command logic per template.

### Weapons
`weapon_dagger_iron`, `weapon_sword_short`, `weapon_sword_long`, `weapon_axe_hand`, `weapon_club_wooden`, `weapon_staff_oak`, `weapon_bow_hunting`, `weapon_arrow`, `weapon_crossbow`, `weapon_sling`.

### Armour, clothing, and jewellery
`armour_helmet_leather`, `armour_helmet_iron`, `armour_tunic_leather`, `armour_mail_shirt`, `armour_shield_wooden`, `clothing_cloak_wool`, `clothing_boots_leather`, `clothing_gloves_leather`, `clothing_belt_leather`, `clothing_backpack`, `clothing_pouch`, `jewellery_ring_plain`, `jewellery_amulet`.

### Containers
`container_chest_wooden`, `container_chest_iron`, `container_crate_wooden`, `container_barrel`, `container_sack_burlap`, `container_basket_wicker`, `container_bottle_glass`, `container_flask`, `container_bucket`, `container_lockbox`.

### Keys and access
`key_iron_small`, `key_brass_ornate`, `key_rusted`, `key_skeleton`, `access_keycard`, `access_seal`, `tool_lockpick`. Store lock compatibility on instances/relationships rather than creating a template per lock.

### Food, drink, and consumables
`food_bread_loaf`, `food_apple`, `food_dried_meat`, `drink_water`, `drink_ale`, `potion_healing_minor`, `potion_antidote`, `herb_medicinal`, `poison_vial`, `ration_travel`. Where practical, separate a reusable vessel from its contents.

### Tools
`tool_rope_hemp`, `tool_hammer`, `tool_crowbar`, `tool_shovel`, `tool_pickaxe`, `tool_hatchet`, `tool_fishing_rod`, `tool_needle_thread`, `tool_flint_steel`, `tool_waterskin`, `tool_compass`, `tool_spyglass`.

### Light and fire
`light_torch`, `light_lantern_oil`, `light_candle`, `light_brazier`, `fuel_lamp_oil`, `fuel_firewood`, `fixture_fireplace`.

### Readable objects
`readable_book`, `readable_scroll`, `readable_letter`, `readable_ledger`, `readable_notice`, `readable_map`, `readable_inscription`, `readable_journal`, `readable_label`, `readable_sign`. Store unique text on instances or content records. Support addressable parts such as cover, front, back, pages, folds, margins, and seals.

### Currency and valuables
`currency_coin_copper`, `currency_coin_silver`, `currency_coin_gold`, `valuable_gem_uncut`, `valuable_gem_cut`, `valuable_ring_gold`, `valuable_goblet_silver`, `valuable_statue_small`, `valuable_pearl`. Use quantities for interchangeable stacks rather than one row per coin; support split, combine, transfer, and spend.

### Crafting materials
`material_wood_log`, `material_wood_plank`, `material_iron_ore`, `material_iron_ingot`, `material_leather`, `material_cloth`, `material_herb`, `material_bone`, `material_stone`, `material_clay`.

### Furniture and room objects
`furniture_table_wooden`, `furniture_chair_wooden`, `furniture_bed`, `furniture_bookshelf`, `furniture_cabinet`, `furniture_desk`, `furniture_rug`, `furniture_mirror`, `furniture_bench`, `furniture_wardrobe`, `furniture_weapon_rack`, `furniture_painting`.

Furniture remains interactable even when too large for inventory. Support applicable sitting, lying, surfaces, containment, opening, moving, searching, looking behind/under, breaking, repair, and concealment. A rug can conceal a hatch, floorboard, key, or other object.

### Fixtures and environmental objects
`fixture_door_wooden`, `fixture_gate_iron`, `fixture_trapdoor`, `fixture_floorboard_loose`, `fixture_wall_cracked`, `fixture_window_glass`, `fixture_lever`, `fixture_button`, `fixture_chain`, `fixture_iron_ring`, `fixture_ladder`, `fixture_stairs`, `fixture_well`, `fixture_fountain`, `fixture_statue`, `fixture_altar`, `fixture_tree`, `fixture_rock`, `fixture_bush`, `fixture_hole`, `fixture_loose_soil`.

Fixed objects still allow appropriate interaction. A loose floorboard can be examined, searched, lifted, pried, replaced, and reveal objects beneath it.

### Transportation
`vehicle_rowboat`, `vehicle_fishing_skiff`, `vehicle_cart`, `vehicle_wagon`, `mount_saddle`, `vehicle_canoe`. Vehicles support applicable boarding, leaving, launching, beaching, piloting, pushing, pulling, tying, cargo, damage, and repair, not ordinary pocket inventory.

### Quest and special objects
`quest_token`, `quest_relic`, `quest_package`, `quest_badge`, `quest_fragment`, `quest_evidence`, `quest_body_part`, `quest_sealed_letter`. Quest importance and restrictions should normally be instance relationships rather than duplicated physical templates.

### Remains and loot sources
`remains_corpse_humanoid`, `remains_skeleton`, `remains_bones_pile`, `loot_coin_purse`, `loot_satchel`, `loot_cache_hidden`.

### Magical objects
`magic_wand`, `magic_scroll`, `magic_ring`, `magic_orb`, `magic_stone`, `magic_portal_key`, `magic_potion`, `magic_weapon`. Use allowlisted effects, charges, activation requirements, cooldowns, targets, identification state, and validated passive/active effects; never arbitrary generated code.

## 11. Priority acceptance set

Create structurally valid catalogue entries for all listed templates, but fully implement and test these first:

1. `weapon_sword_short`
2. `weapon_dagger_iron`
3. `clothing_backpack`
4. `clothing_cloak_wool`
5. `container_chest_wooden`
6. `container_crate_wooden`
7. `container_bottle_glass`
8. `key_brass_ornate`
9. `tool_lockpick`
10. `tool_rope_hemp`
11. `tool_crowbar`
12. `light_torch`
13. `potion_healing_minor`
14. `readable_letter`
15. `currency_coin_copper`
16. `furniture_table_wooden`
17. `furniture_rug`
18. `fixture_floorboard_loose`
19. `fixture_iron_ring`
20. `vehicle_fishing_skiff`

These exercise weapons, hands, equipment, inventory, capacity, fit, locks, keys, lock picking, hidden objects, clues, discovery, surfaces, readable content, consumables, stacks, lighting, attachments, climbing, descriptions, and large objects.

## 12. AI-generated objects

AI-assisted world generation may propose template selection, names, aliases, descriptive facts, materials, condition, registered capabilities, placement, clues, locks, and keys. Validate all proposals before persistence with structured schemas, allowlists, bounds, reachability, and permissions. The game must work without AI.

## 13. Persistence and backward compatibility

Persist state, discovery, and relationships across restarts, disconnections, room unloading, configured Docker recreation, movement, transfers, equipment changes, containment, and lock/key generation. Add safe migrations/defaults for existing records. Do not silently destroy world data.

## 14. Commands, API, and frontend

Integrate at least the architecture needed for: `look`, `look at`, `examine`, `search`, `take/get/pick up`, `drop`, `hold`, `release`, `put`, `remove`, `give`, `wear`, `wield`, `use`, `open`, `close`, `lock`, `unlock`, `pick lock`, `read`, `push`, `pull`, `move`, `break`, `repair`, `light`, `extinguish`, `attach`, `detach`, `tie`, `untie`, `climb`, `sit`, `lie down`, `enter/board`, `leave`, `pour`, `fill`, and `inventory`.

Normalize reasonable equivalent language. Update APIs and frontend to expose contextual text, visible state, safe IDs, available/suggested actions, visible container contents, held/equipped location, and discovered details. Never expose hidden objects, secret lock data, inaccessible contents, or admin-only dependency information. Preserve the command-driven interface and optional panels.

## 15. Administrator diagnostics

Provide an admin/debug view of template/instance IDs, authoritative location, ownership, containment/surfaces, hand/equipment relationships, capabilities, state, lock/key links, generation provenance, dependency chain, solvability, and reasons an action was accepted or rejected. Do not show this in ordinary player output.

## 16. Automated tests

Follow existing test tools and conventions. Add unit and appropriate integration/API tests for:

- template versus instance isolation;
- take/drop, hold/release, wear/remove, wield, containment, transfers, surfaces, and room movement;
- contextual first-/third-person descriptions and physical states;
- hidden information, visibility, light, discovery, and permissions;
- open/close/lock/unlock and explicit state transitions;
- generating or safely reusing a matching key;
- current-room and reachable-nearby-room key placement;
- hidden keys, clues, and reasonable discovery commands;
- preventing direct and indirect lock/key cycles;
- rejecting unreachable placement and preserving dependencies through restart;
- explicit duplicate keys and alternate access paths;
- capacity, opening size, weight, hands, equipment slots, durability, and large objects;
- stacks: combine, split, transfer, spend;
- meaningful failure messages;
- AI schema/allowlist validation and non-AI fallback;
- admin-only diagnostics and backward compatibility.

Add Playwright tests only for meaningful browser flows already supported by the repository. Do not duplicate every unit test in Playwright. Run relevant existing suites and new tests. Never claim a test passed unless it ran; state exactly why anything could not run.

## 17. Required implementation workflow

1. Inspect repository and documentation.
2. Explain current room, item, inventory/equipment, command, persistence, API/frontend, and AI-generation architecture, naming the important files.
3. Identify compatibility risks and provide a concise plan.
4. Make conservative choices for small ambiguities; ask only when a choice materially affects scope, compatibility, or stored data.
5. Implement the smallest coherent foundation.
6. Add migrations and backward compatibility.
7. Implement priority templates, then structurally valid remaining catalogue entries.
8. Add automated tests.
9. Run formatting, linting, static analysis, unit, integration, and relevant Playwright tests.
10. Fix regressions caused by this work.

At completion, report architecture, changed files, database changes, templates and capabilities added, commands supported, validation/solvability rules, contextual-description behaviour, exact tests/results, limitations, and the recommended next increment.

Before editing, inspect the repository and report what you found. Then proceed unless genuinely blocked.
