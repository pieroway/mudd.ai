"""Bounded presentation-only contracts; no mutable world objects or commands."""

from typing import Annotated, Literal, get_args

from pydantic import ConfigDict, StringConstraints

from app.ai.models import StrictModel

NarratedAction = Literal[
    "look", "move", "take", "drop", "examine", "open", "close", "use",
    "extinguish", "look_in", "take_from", "put",
]
NARRATED_ACTIONS = frozenset(get_args(NarratedAction))


class NarrationRequest(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    action: NarratedAction
    success: bool
    authoritative_text: Annotated[str, StringConstraints(min_length=1, max_length=4096)]


class NarrationResponse(StrictModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
