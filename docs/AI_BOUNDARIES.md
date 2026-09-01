# AI Boundaries

AI may interpret natural-language commands, narrate deterministic outcomes, roleplay NPCs within bounded context, propose world content, propose quests/artifacts, and summarize memories.

AI may not directly mutate authoritative game state.

Natural language becomes strict structured actions that are validated before execution.

## RAG

Retrieve only relevant context such as current room, visible items, nearby NPCs, inventory, local lore, approved NPC knowledge, recent conversation, and relevant memories.

Start with relational retrieval. Consider pgvector later if semantic retrieval becomes valuable.

NPCs receive only information they are allowed to know.

Generated content is non-canonical until schema, consistency, rarity, and balance validation pass.
