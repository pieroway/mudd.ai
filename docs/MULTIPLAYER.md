# Multiplayer

The world is shared.

Server-authoritative state includes player presence, room membership, shared items, ownership, transfers, currency, environmental state, combat state, and NPC state.

Players in the same room may speak naturally. Do not normally rewrite human-to-human speech.

If player A drops an item, it becomes room state. Player B may later find and take it. Only one player may win a simultaneous pickup.

Player-to-player item and currency exchanges must be validated and atomic.

Design explicitly for simultaneous pickup, last-stock purchase, shared doors/containers, disconnect during transfer, and duplicate requests.

Free-form text cannot force another human player's actions, dialogue, feelings, movement, inventory transfer, or consent.
