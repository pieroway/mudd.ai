Review the current MUD codebase and propose a scalable command architecture for the game.

The goal is NOT to create hundreds of unrelated command implementations.

Instead, design the system around approximately 120–180 canonical player actions, with aliases and alternate phrasing resolving to the same underlying action.

For example:

```text
get sword
take sword
grab sword
pick up sword
pick up the sword
```

should all ultimately resolve to something conceptually equivalent to:

```text
Action: TAKE
Target: sword
Source: current room
```

Similarly:

```text
n
north
go north
walk north
```

should resolve to the same movement action.

## Goals

Design a command system that:

- Feels familiar to experienced MUD players.
- Is easy for new players to discover.
- Supports traditional short commands.
- Supports aliases.
- Can later support more natural-language input.
- Avoids duplicating game logic for synonymous commands.
- Is easy to extend.
- Is easy to unit test.
- Keeps parsing separate from game rules.
- Keeps command execution deterministic.
- Can eventually allow AI-assisted natural-language interpretation without making AI responsible for game mechanics.

## Command Categories

Consider a comprehensive command set covering at least:

1. Movement and navigation
2. Looking, examining, and perception
3. Inventory and item handling
4. Equipment
5. Combat
6. Skills and abilities
7. Magic/spells if supported by the current design
8. Communication
9. Social actions and emotes
10. Groups/parties
11. Guilds/clans/factions
12. Shops and economy
13. Player-to-player trading
14. Player stalls/marketplaces
15. Banking/currency
16. Containers, doors, locks, and keys
17. Food/drink/rest/sleep
18. Character information
19. World information
20. Quests/tasks
21. Crafting/gathering if appropriate
22. Housing/property if appropriate
23. Rare or empowered-item interactions
24. Help and command discovery
25. Account/session commands
26. Preferences/settings
27. Administrative or moderation commands, separated from normal player commands

## Canonical Commands vs Aliases

Identify one canonical command/action for each gameplay operation.

For example:

```text
Canonical action:
TAKE

Possible aliases:
get
grab
pickup
pick up
```

Do not create separate business logic for each alias.

Aliases should resolve to the canonical command before execution.

Where appropriate, allow commands to have short aliases:

```text
north -> n
south -> s
inventory -> i
equipment -> eq
look -> l
```

Avoid ambiguous aliases.

## Parsing

Keep parsing separate from execution.

Conceptually, input such as:

```text
put the silver coin into the wooden chest
```

might become:

```text
CommandIntent
{
    Action = PUT
    DirectObject = silver coin
    IndirectObject = wooden chest
}
```

The command executor then validates:

- Does the player possess the coin?
- Is the chest present?
- Is the chest accessible?
- Is it open?
- Can the chest contain the object?
- Does the player have permission?

The parser should not make those gameplay decisions.

## Natural-Language Expansion

Design the architecture so more flexible phrasing could eventually be added.

For example:

```text
ask the bartender about the missing caravan

give Hugh three silver coins

take everything except the rusty sword

put all my gems into the chest

look behind the statue
```

Do NOT require AI for the initial implementation.

Traditional deterministic parsing should remain the primary mechanism.

However, design a clean boundary where an AI parser could someday translate unusual player wording into the same structured `CommandIntent` representation.

AI should never directly execute game actions.

Conceptually:

```text
Player text
    |
    v
Traditional Parser
    |
    +---- unable to confidently parse ----+
                                         |
                                         v
                                  Optional AI Parser
                                         |
                                         v
                                  CommandIntent
                                         |
                                         v
                                  Validation Layer
                                         |
                                         v
                                    Game Engine
```

The game engine remains authoritative.

## Command Discovery

Consider how players discover available commands.

Possible features:

```text
commands
commands combat
commands movement
commands economy

help
help combat
help take
help trade
```

Commands should carry metadata where practical, such as:

```text
Name
Aliases
Category
Syntax
ShortDescription
DetailedHelp
MinimumAccessLevel
CanUseWhileFighting
CanUseWhileDead
CanUseWhileSleeping
Cooldown
```

Do not force this exact model if it does not fit the existing architecture.

## Command Registry

Consider using a command registry rather than a large central switch statement.

Conceptually:

```text
CommandRegistry
    TAKE -> TakeCommand
    DROP -> DropCommand
    LOOK -> LookCommand
    ATTACK -> AttackCommand
```

Aliases could resolve through the same registry:

```text
get -> TAKE
grab -> TAKE
pickup -> TAKE

kill -> ATTACK
fight -> ATTACK
```

Prefer the architecture that fits the current codebase rather than blindly implementing this example.

## Target Size

Develop a proposed command catalogue containing approximately:

- 120–180 canonical player commands/actions

Do not artificially inflate the count.

If several commands are really aliases or parameterized versions of another action, consolidate them.

For example, do not create:

```text
open-door
open-chest
open-box
```

when:

```text
open <target>
```

can support all three through game-object capabilities.

Likewise, prefer:

```text
use <item> [target]
```

where appropriate instead of dozens of object-specific commands.

## Extensibility

The command system should make it possible for future game systems to register commands without tightly coupling everything together.

Potential future systems include:

- Crafting
- Magic
- Guild abilities
- Player housing
- Vehicles/mounts
- Sailing
- Politics
- Player businesses
- Rare empowered objects
- AI-supported NPC interaction
- World events

Consider whether commands should expose capability or permission checks instead of embedding those checks into parsing.

## Testing

Design the system to be highly testable.

At minimum, consider tests for:

- Alias resolution
- Case insensitivity
- Extra whitespace
- Abbreviations
- Missing arguments
- Invalid targets
- Ambiguous targets
- Multiple matching objects
- Commands unavailable because of player state
- Permissions
- Combat restrictions
- Container interactions
- Multi-word object names
- Quoted strings where applicable
- Prepositions such as `in`, `into`, `from`, `at`, `to`, `with`, and `on`

Examples:

```text
get sword

GET SWORD

get   sword

get rusty sword

get the rusty sword

get sword from chest

put sword in chest

give 10 gold to hugh

attack second goblin
```

## Important Constraint

Before modifying code:

1. Inspect the existing command/parser architecture.
2. Identify what already exists.
3. Reuse existing abstractions where sensible.
4. Avoid large rewrites unless there is a strong architectural reason.
5. Do not implement all 120–180 commands immediately unless the project is already at the stage where that makes sense.

The first goal is to establish the architecture and command catalogue.

## Deliverables

Please provide:

1. An assessment of the existing command architecture.
2. Recommended architectural changes, if any.
3. A proposed grouped catalogue of approximately 120–180 canonical player commands.
4. Aliases for each command where appropriate.
5. Identification of commands that should NOT be separate because they can share a more general action.
6. A proposed structured `CommandIntent` model or equivalent appropriate to this codebase.
7. A proposed command registry/handler architecture.
8. A strategy for command help/discovery.
9. A testing strategy.
10. A phased implementation plan.

For the implementation plan, separate:

```text
Phase 1 - foundational architecture
Phase 2 - standard MUD commands
Phase 3 - richer object interaction
Phase 4 - advanced gameplay systems
Phase 5 - optional natural-language / AI-assisted interpretation
```

Do not add AI dependencies at this time.

The architecture should merely leave a clean integration point for them later.

Most importantly, preserve one rule throughout the design:

**Player wording may be flexible, but actual game actions must remain structured, deterministic, validated, and controlled by the game engine.**