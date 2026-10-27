# Item and object interactions

## Architecture

`domain/catalogue.py` supplies all 159 templates specified in the implementation
brief. `ItemTemplate` validates capability names and physical/configuration bounds.
Templates are seeded idempotently; existing objects retain their IDs, locations,
descriptions, legacy behavior, and current state. Creating a template does not
place an instance into the world.

`commands/items.py` normalizes item grammar. `engine/item_rules.py` resolves visible
objects and executes deterministic capability rules. Legacy objects continue through
`engine/executor.py`; both paths enforce visibility. Aliases resolve only when
unambiguous. Explicit IDs cannot bypass discovery, distance, another player's
inventory, or closed containers.

`domain/item_context.py` composes descriptions from actual placement, hands,
equipment, quantities, and state. Inventory snapshots recursively include only
visible contents, to a bounded depth. They expose contextual text, location,
visible state, and suggested commands, never readable secrets, lock IDs, key links,
provenance, or administrator dependency graphs. Another player's visible equipment
can be examined while in the same lit room.

Migration `0019` adds player condition/posture and room conditions as JSONB with
empty defaults. Instance relationships reuse migration `0018`: containment retains
one physical location, with a placement relationship distinguishing containers,
surfaces, and hiding places. `owner` is separate from physical possession. Hands,
equipment, attachment, occupation, lock/key links, and discovery persist. Quantities
split into new instances; consumption and combination remove instances transactionally.

## Player commands

Use full names or instance IDs when aliases are ambiguous.

```text
take sword
hold sword in right hand
wield sword
release sword
wear backpack
remove backpack
open backpack
put sword in backpack
put letter on table
look on table
take letter from table
search room
look under rug
move rug
pry up floorboard with crowbar
unlock chest with brass key
lock chest with brass key
pick chest lock
read letter
read back of letter
break crate with crowbar
repair backpack with needle thread
light torch
extinguish torch
tie rope to iron ring
untie rope
climb rope
sit chair
lie down on bed
board skiff
tie skiff to iron ring with rope
untie skiff
launch skiff
pilot skiff east
beach skiff
leave
pour blue bottle into red bottle
fill red bottle from blue bottle
split 5 coins
combine <stack-id> with <other-stack-id>
give 3 coins to Mara
spend 3 coins to Mara
use healing potion
```

Required capabilities, free hands/slots, weight, fit, material hardness, durability,
fuel, liquid capacity, matching keys, occupied objects, and existing exits are checked.
`spend` transfers a specified quantity to another present player; it does not invent
a shop, price, or purchase. Lit legacy torches retain their previous behavior.
New torches require a carried ignition source, such as flint and steel or a lit light.
Fuel is measured in successful movement turns, matching the existing game clock.

Hidden objects remain private until discovered. Searching the room reveals clues;
searching, looking beneath, shifting, or prying an appropriate hiding place discovers
its contents. Discovery is per player until the object is physically removed from
concealment. Room `dark` conditions suppress sight unless an accessible light is lit.

## Admin authoring and diagnostics

Authenticated admins can use:

```text
/item catalogue
/item spawn clothing_backpack
/item spawn currency_coin_copper 20
/item spawn container_chest_wooden 1 "Cedar Chest"
/item inspect <instance-id>
/item lock <chest-id> [key-room-id] [hiding-place-id]
/item place <item-id> hidden_under <rug-id>
/item configure <letter-id> '{"readable":{"text":"Meet at the docks.","back":"Bring the key."}}'
/item configure <rope-id> '{"climb_destination":"existing-adjacent-room-id"}'
/item configure <bottle-id> '{"liquid":"water","liquid_litres":1}'
/item environment '{"terrain":"river","shore":true,"dark":false}'
```

Spawn returns the instance ID. Inspection includes the template, physical location,
ownership, equipment, capabilities, condition, state, provenance, lock/key dependency
graph, solvability, and recent accepted/rejected actions and reasons. It is not a
player snapshot. Configure accepts a small allowlist of bounded values rather than
arbitrary capabilities, effects, or code. Authoring requires proximity except
read-only diagnostics.

## Locks, generation, and solvability

`item_dependencies.py` proves access using a fixed point over reachable rooms,
objects, containers, and keys. It rejects orphaned locks, inaccessible required keys,
direct and indirect key cycles, missing parents, and containment cycles. Alternative
lock picking or breaking must be explicit and have a reachable suitable tool.
Gameplay refuses a state change that would strand a required lock/key dependency.
World integrity is checked in the relevant physical regions and accounts for keys
held by other human players without granting the acting player access to them.
Unrelated players and disconnected regions do not block one another's movement.

Lock authoring reuses a safe nearby matching/compatible brass key or creates one.
New placement must be within three room hops. Hidden keys require an interactable
hiding place and receive a clue. Open/closed state does not substitute for key access.

AI neighborhood objects may select a registered `template_id`, request `locked`,
and specify a local `key_room` and `hiding_place`. The engine creates relationships
and matching keys, checks solvability, and counts them against object limits before
publication. Preview and approval revalidate the draft. Invalid template/lock
requests show no authoritative changes. Preview includes generated keys in its
object count and displays their placement, matching targets, and clues alongside
each object's actual portability, template, and locked state. Invalid template/lock
requests cannot be silently flattened or stripped by topology repair. No AI calls
are required for authored objects or gameplay.

## Boundaries

Capabilities support ordinary physical interactions and bounded registered effects.
This increment does not invent absent combat, NPC commerce/persuasion, cooperative
movement sessions, a weather simulation, or a magic system. Climbing requires a
configured existing adjacent exit. Solo vessel travel uses existing exits between
rooms explicitly classified as navigable water, requires a paddle-capable object,
and respects mooring and closed doors. An oak staff can serve as a makeshift paddle.
Travel with multiple occupants fails explicitly pending coordinated group actions.
Generic digging/harvesting changes authored
state and reveals configured hidden objects rather than creating arbitrary loot.
Future systems can extend registered capabilities and effects without per-template
command handlers. Unconfigured actions return an in-world failure.
