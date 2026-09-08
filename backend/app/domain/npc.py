"""Authored NPC facts and deterministic relationship rules."""

EDRIC_ID = "edric"
EDRIC_ROOM = "inn"
EDRIC_PERSONALITY = "A patient, warm innkeeper with dry humor; plain-spoken and discreet."
EDRIC_GOALS = ["Welcome travelers.", "Keep the Inn peaceful."]
EDRIC_KNOWLEDGE = [
    "Edric tends the Inn and welcomes travelers.",
    "The Inn has lanterns and a wood fire.",
    "The Town Square is west of the Inn.",
]


def relationship_for(interactions: int) -> str:
    """Familiarity reflects completed conversations, never provider-assigned trust."""
    if interactions == 0:
        return "stranger"
    return "familiar visitor" if interactions >= 3 else "returning visitor"
