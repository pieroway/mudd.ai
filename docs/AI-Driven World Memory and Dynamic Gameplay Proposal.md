# AI-Driven World Memory and Dynamic Gameplay Proposal

## Purpose

Consider adding an AI-assisted world-memory layer to the MUD so the game can react to player activity, remember meaningful events, create more believable NPC behavior, generate rumours, support dynamic quests, and make the world feel as though it continues to evolve even when individual players are not present.

The AI should not become the authoritative game engine. Core game state must remain deterministic and controlled by normal application logic.

The central design principle is:

**Store facts, relationships, and significant events rather than complete conversations or command histories.**

---

## Design Goals

The system should eventually make possible features such as:

- NPCs remembering meaningful interactions with individual players.
- NPC opinions changing based on player behavior.
- NPCs remembering debts, attacks, assistance, insults, trades, alliances, and other relevant events.
- NPC-to-NPC relationships developing over time.
- Dynamic rumours based on actual events in the world.
- Important player actions becoming part of world history.
- AI-generated quests derived from existing world conditions.
- Environmental consequences from repeated player activity.
- Region-specific stories, politics, cultures, legends, and conflicts.
- Rare items influencing how players perceive or interact with the world.
- An AI "world director" capable of identifying interesting emerging situations.
- Natural-language NPC interaction while retaining traditional MUD commands.
- Player actions gradually becoming legends, stories, monuments, books, rumours, or named objects.

This should be designed so that it can be added incrementally rather than requiring a complete AI implementation from the beginning.

---

# Core Architectural Rule

## AI Does Not Own Game Truth

The traditional game engine remains authoritative for:

- Player statistics
- Inventory
- Item ownership
- Currency
- Combat
- Damage
- Death
- Movement
- Geography
- Permissions
- Quest state
- Faction membership
- NPC location
- Object location
- Economy
- Environmental state
- Item powers
- Cooldowns
- Resource availability

AI may:

- Interpret
- Describe
- Converse
- Summarize
- Suggest
- Generate flavour
- Generate dialogue
- Identify interesting situations
- Propose game actions

AI must not directly modify authoritative game state.

For example, an AI-controlled NPC should not simply decide:

`Give player 50,000 gold.`

Instead, it should request something equivalent to:

`transfer_gold(npcId, playerId, 50000)`

The game engine validates the request and either executes or rejects it.

This prevents hallucinations or AI reasoning errors from corrupting the game world.

---

# Event-Based World History

Add a structured event system capable of recording significant player, NPC, economic, environmental, and world actions.

A basic event could include:

- Event ID
- Timestamp
- Event type
- Actor ID
- Target ID
- Location ID
- Result
- Importance score
- Optional metadata

Example:

```text
event_type = PURCHASE
actor = player_alan
target = npc_hugh
location = red_dragon_tavern
item = ale
quantity = 2
importance = 1
```

Another:

```text
event_type = NPC_SAVED
actor = player_alan
target = npc_hugh
location = red_dragon_tavern
importance = 7
```

Another:

```text
event_type = ARTIFACT_DISCOVERED
actor = player_morgan
item = whispering_coin
location = forgotten_observatory
importance = 9
```

The purpose is not to permanently store every player command.

The purpose is to create a compact structured record of events that may later have consequences.

---

# Event Importance

Events should have an importance value.

For example:

```text
1 = trivial
2 = minor
3 = noteworthy
4 = locally memorable
5 = significant
6 = important
7 = major
8 = regional
9 = historic
10 = world-changing
```

Possible retention policy:

```text
Importance 1
Delete after 24 hours.

Importance 2
Delete after several days.

Importance 3
Retain for approximately one month.

Importance 4-5
Retain for longer-term local memory.

Importance 6-8
Retain indefinitely unless summarized.

Importance 9-10
Permanent world history.
```

Retention times should eventually be configurable.

---

# Layered Memory Model

The system could use several different forms of memory.

## 1. Current World State

This is the existing authoritative database.

Examples:

- Player location
- Player inventory
- NPC state
- Item state
- Currency
- Room state
- Faction state
- Weather
- Economy
- Environmental conditions

This should never depend on AI memory.

---

## 2. Recent Event History

Keep detailed structured events for a limited period.

This allows questions such as:

- Who attacked this merchant yesterday?
- Who recently entered this dungeon?
- Who was carrying a certain artifact?
- What happened in this town this week?
- Which player recently helped this NPC?

Recent history can eventually be pruned.

---

## 3. Significant Historical Events

Important events should be retained long term.

Examples:

- Major boss killed
- Town conquered
- Important NPC killed
- Rare artifact discovered
- Large PvP battle
- Political change
- Guild betrayal
- Major economic disruption
- New region discovered
- Important player-created event

These events can become part of the world's permanent history.

---

## 4. NPC Memory

NPCs should not need full transcripts of conversations.

Instead, store concise memories.

Example:

```text
NPC: Hugh the Bartender

Relationship toward player Alan:

trust = 72
respect = 61
fear = 5

Memories:

- Alan protected the tavern during a goblin raid.
- Alan frequently asks about northern caravans.
- Alan owes Hugh 12 silver.
```

Relationships could include values such as:

- Trust
- Respect
- Fear
- Affection
- Suspicion
- Anger
- Loyalty

Not every NPC requires all values.

NPC memory should be selective and based on event importance.

---

## 5. World Summaries

Periodically summarize many lower-level events into a smaller number of meaningful facts.

For example, thousands of individual events might eventually become:

```text
Town Summary:

- Goblin attacks increased on the western road.
- Three merchants were killed.
- Caravan traffic nearly stopped.
- Alan helped restore the trade route.
- The Merchant Guild now holds Alan in high regard.
- Rumours are circulating about a blue crystal found near the ruins.
```

Once summarized, some lower-priority raw events could be deleted or archived.

---

# World Historian Process

Consider eventually adding a background or scheduled process called something similar to:

`WorldHistorian`

Its purpose would be to examine accumulated events and determine:

- What is worth remembering?
- What can be discarded?
- What should become a historical summary?
- Which player actions became important?
- Which NPCs should remember specific events?
- Which rumours might naturally arise?
- Which events should become permanent world lore?

For example:

```text
4,231 low-level events
```

could potentially be reduced to:

```text
27 meaningful historical facts
```

The historian should produce structured output rather than uncontrolled prose wherever possible.

---

# Relevant Memory Retrieval

AI should never receive the entire world history for every interaction.

Instead, retrieve only relevant context.

For example, if a player asks:

`ask Hugh what he thinks of Morgan`

the system might retrieve:

```text
NPC:
Hugh

Relationship with requesting player:
Friendly

Known facts about Morgan:

- Morgan owes Hugh 40 silver.
- Morgan started a fight in Hugh's tavern three days ago.
- Morgan belongs to the Blackwood Guild.

Recent relevant world event:

- Blackwood Guild members damaged the tavern.

NPC personality:

- Hugh dislikes violence.
- Hugh strongly dislikes unpaid debts.
```

The AI can then generate an appropriate response based on those facts.

This is a good candidate for a RAG-style retrieval system.

A conceptual query might be:

```text
Retrieve relevant memories involving:

NPC = Hugh
Subject = Morgan
Location = Red Dragon Tavern
Age <= 90 days
Importance >= 4
```

Only the results should be placed into the AI context.

---

# Dynamic NPC Dialogue

NPC dialogue could eventually use:

- Personality
- Current mood
- NPC knowledge
- NPC memories
- Relationship values
- Local events
- Faction relationships
- Current world state

Example:

Instead of a static response:

`Morgan is a member of the Blackwood Guild.`

Hugh might say:

`Hugh wipes the counter harder than necessary. "Morgan? If you see him, tell him I've still got a ledger with his name on it."`

The underlying fact remains deterministic.

The AI merely expresses it naturally.

---

# Dynamic Rumours

Actual game events could create rumours.

Example event:

```text
Player Morgan discovered a rare artifact near the northern ruins.
```

Possible later rumour:

```text
"Someone carrying a silver staff was seen near the northern ruins."
```

Rumours do not need to be perfectly accurate.

The system could intentionally allow:

- Accurate rumours
- Exaggerated rumours
- Partially incorrect rumours
- Old rumours
- Conflicting rumours

However, rumours should always originate from actual known or plausible world events rather than arbitrary AI invention.

---

# Dynamic Quests

AI could eventually help identify quest opportunities from world state.

Instead of only predefined quests such as:

`Kill 10 wolves`

the system might recognize:

- Caravan traffic has stopped.
- Multiple merchants were attacked.
- Wolves have become unusually aggressive.
- A nearby hunter NPC has relevant knowledge.
- The road has seen little player activity recently.

The system could propose a quest around the real situation.

The game engine must still determine:

- Objectives
- Rewards
- Completion conditions
- Valid targets
- Required items
- Game-state changes

AI could provide the narrative wrapper.

---

# Environmental Consequences

Repeated player behavior could influence the world.

Example:

Players kill too many wolves.

Possible chain:

```text
Wolf population decreases
↓
Deer population increases
↓
Crop damage increases
↓
Food prices rise
↓
Farmers complain
↓
Hunters relocate
↓
NPC rumours emerge
↓
Players discover an ecological problem
```

This kind of simulation could make the world feel alive without needing AI to control the underlying mechanics.

The simulation itself should preferably remain deterministic.

AI explains and interprets the consequences.

---

# AI World Director

A future system could periodically inspect structured world information and identify interesting opportunities.

Possible inputs:

- Player population by region
- Recent deaths
- Recent discoveries
- Economy
- Dormant locations
- NPC conflicts
- Player conflicts
- Rare artifacts
- Faction tensions
- Unresolved events
- Underused areas
- Recent unusual events

Example analysis:

```text
Northern region has received very little player activity.

Ancient Observatory has not been entered in 19 days.

Player Morgan currently owns an artifact historically connected to the Observatory.

Two scholar NPCs know fragments of Observatory lore.
```

The World Director might then propose subtle world changes:

- A scholar begins asking questions.
- Strange lights appear over the mountains.
- Merchants hear rumours.
- An NPC begins researching the artifact.
- Animals behave strangely near the region.

The goal is not to generate a conventional quest marker.

The goal is to create situations players notice naturally.

---

# Player-Specific Perception

AI could help produce different descriptions depending on what a player knows or possesses.

Example normal player:

```text
An old wooden door stands before you.
```

Player with magical perception:

```text
A faint violet distortion surrounds the door.
```

Player carrying a specific artifact:

```text
The stone in your ring grows warm as you approach the door.
```

The engine decides whether the player qualifies for additional information.

AI may generate the wording.

---

# Rare and God-Empowered Items

The existing concept of rare empowered items could integrate well with this system.

These items should remain constrained by normal game rules but could grant unusual access to world information.

Example:

## The Whispering Coin

Possible power:

Once per day, the owner may ask:

`Who in this city knows something about the missing caravan?`

The system queries actual NPC memories and knowledge.

The AI then returns a cryptic interpretation.

The AI must not invent NPC knowledge that does not exist.

Other possible artifact abilities:

- Examine hidden player statistics.
- Reveal unusual NPC relationships.
- Detect important events that occurred in a room.
- Reveal fragments of object history.
- Detect nearby lies.
- Reveal faction influence.
- Sense unusual world-state changes.
- Hear distant rumours.
- Temporarily perceive hidden attributes.

These powers could make the AI memory system part of gameplay rather than merely background infrastructure.

---

# Player Actions Becoming History

The system could identify unusually interesting player achievements.

Example:

A player kills a powerful creature using an ordinary cooking knife.

Initially this is simply an event.

Later:

- NPCs mention it.
- Bards exaggerate it.
- Other players hear the story.
- A book records it.
- A monument references it.
- The weapon gains historical significance.

Eventually the game might create:

`Pieroway's Knife`

Not because a developer predefined it, but because the world historian determined that the event became culturally significant.

The game engine should still determine whether such an object is created and what powers, if any, it receives.

---

# Natural-Language Commands

Traditional commands should remain available and reliable:

```text
north
get sword
sell gem
attack goblin
inventory
```

AI could optionally allow more natural interactions:

```text
Ask the bartender whether anyone strange came through town last night.
```

The AI should interpret the request into structured game actions.

For example:

```text
action = ASK_NPC
npc = bartender
topic = strange_visitors
time_reference = last_night
```

The normal game system then determines what information the bartender knows.

This keeps natural-language input from bypassing game rules.

---

# Suggested Initial Implementation

Do not attempt the complete AI system initially.

The most useful preparation may simply be to add a generic event model.

A minimal event structure could contain:

```text
timestamp
actor
action
target
location
result
importance
metadata
```

For example:

```text
WorldEvent
{
    Id
    Timestamp
    EventType
    ActorId
    TargetId
    LocationId
    Importance
    Result
    Metadata
}
```

This would provide the historical foundation for later:

- NPC memory
- AI dialogue
- Dynamic rumours
- World summaries
- Historical records
- Dynamic quests
- AI world direction
- Player legends
- Artifact powers

Adding structured event history early could avoid having to retrofit event collection after much of the game is already implemented.

---

# Possible Supporting Components

Future architecture could include components such as:

```text
WorldEventService
WorldEventRepository
EventImportanceEvaluator
NpcMemoryService
RelationshipService
MemoryRetrievalService
RumourService
WorldHistorian
WorldDirector
AiDialogueService
AiActionValidator
WorldSummaryService
ArtifactInsightService
```

These names are conceptual only.

They should not be introduced until the existing architecture makes their responsibilities clear.

---

# Conceptual Flow

```text
PLAYER ACTION
      |
      v
GAME ENGINE
      |
      v
ACTION VALIDATED
      |
      v
WORLD STATE UPDATED
      |
      v
STRUCTURED EVENT GENERATED
      |
      v
EVENT DATABASE
      |
      +----------------------+
      |                      |
      v                      v
NPC MEMORY              WORLD HISTORY
      |                      |
      +-----------+----------+
                  |
                  v
         RELEVANT MEMORY RETRIEVAL
                  |
                  v
                  AI
                  |
                  v
      DIALOGUE / DESCRIPTION /
       RUMOUR / STORY PROPOSAL
```

AI output that attempts to modify game state must return through the normal game engine for validation.

---

# Storage Considerations

This approach should not require excessive storage.

Structured event records containing mostly:

- IDs
- timestamps
- enums
- numeric values
- small metadata objects

are relatively compact.

Millions of structured events are manageable with conventional database technology.

The larger concern is not database storage.

The larger concern is AI context size.

Therefore:

**Do not send large event histories to the AI.**

Retrieve only the events relevant to the current situation.

Over time:

- Delete trivial events.
- Summarize medium-value events.
- Preserve historically significant events.
- Maintain compact NPC memories.
- Maintain structured relationships separately from prose.

---

# Key Design Principles

1. The deterministic game engine owns truth.

2. AI never modifies authoritative world state directly.

3. Store structured events rather than complete transcripts.

4. Record meaningful actions at the time they occur.

5. Give events importance values.

6. Retain important events and discard trivial ones.

7. Summarize history periodically.

8. NPC memory should contain facts and relationships rather than entire conversations.

9. Retrieve only relevant memories for AI context.

10. AI should primarily provide interpretation, dialogue, narration, summarization, and proposals.

11. All AI-proposed actions must be validated by the normal game engine.

12. AI features should be optional and incrementally adoptable.

13. The game must remain functional if AI services are unavailable.

14. Avoid designing core gameplay that depends on unpredictable AI output.

15. Prefer deterministic simulation with AI explaining the consequences.

---

# Recommendation for Current Development

Do not build the full AI system yet.

However, while designing the normal game engine, consider introducing a lightweight structured `WorldEvent` system early.

Capturing events from the beginning would create the raw material needed for advanced AI features later without forcing a major architectural rewrite.

At minimum, consider recording:

```text
Timestamp
Actor
Action/EventType
Target
Location
Result
Importance
Metadata
```

Everything else described in this proposal can remain deferred until the core multiplayer MUD is stable.

The main goal at this stage is therefore not:

**"Add AI now."**

It is:

**"Avoid designing the game in a way that prevents meaningful AI-driven world memory later."**