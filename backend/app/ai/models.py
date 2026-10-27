"""Strict, provider-independent models for AI command interpretation."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Direction = Literal["north", "south", "east", "west", "up", "down"]


class StrictModel(BaseModel):
    """Reject coercion and fields outside the declared provider contract."""

    model_config = ConfigDict(extra="forbid", strict=True)


class InterpretCommandRequest(StrictModel):
    """Player input supplied to a command-interpreting provider."""

    raw_input: NonEmptyText


class NoArgumentCommand(StrictModel):
    action: Literal["look", "inventory", "help", "leave"]


class MoveCommand(StrictModel):
    action: Literal["move"]
    direction: Direction


class TargetCommand(StrictModel):
    action: Literal["take", "drop", "examine", "open", "close", "use", "extinguish"]
    target: NonEmptyText


class ContainerCommand(StrictModel):
    action: Literal["look_in", "look_on"]
    container: NonEmptyText


class ItemContainerCommand(StrictModel):
    action: Literal["take_from", "put"]
    target: NonEmptyText
    container: NonEmptyText
    placement: Literal['contained_in', 'resting_on'] | None = None


class ItemCapabilityCommand(StrictModel):
    action: Literal['hold', 'release', 'wear', 'wield', 'remove', 'search', 'look_under',
                    'lock', 'unlock', 'pick_lock', 'read', 'push', 'pull', 'move_object',
                    'break', 'repair', 'light', 'attach', 'detach', 'tie', 'untie', 'climb',
                    'sit', 'lie', 'board', 'pour', 'fill', 'fold', 'unfold', 'switch',
                    'split', 'combine', 'spend', 'consume', 'pry', 'dig', 'harvest', 'throw', 'cut', 'slash', 'stab',
                    'pilot', 'launch', 'beach']
    target: NonEmptyText
    tool: NonEmptyText | None = None
    destination: NonEmptyText | None = None
    target_player: NonEmptyText | None = None
    slot: Literal['left_hand', 'right_hand'] | None = None
    part: Literal['text', 'front', 'back', 'folds', 'seal', 'cover', 'pages', 'margins'] | None = None
    quantity: int | None = Field(default=None, ge=1, le=1000000)
    direction: Direction | None = None


class GiveCommand(StrictModel):
    action: Literal["give"]
    target: NonEmptyText
    target_player: NonEmptyText


class SayCommand(StrictModel):
    action: Literal["say"]
    message: NonEmptyText


class TellCommand(StrictModel):
    action: Literal["tell"]
    target_player: NonEmptyText
    message: NonEmptyText


class WhoCommand(StrictModel):
    action: Literal["who"]
    page: int | None = Field(default=None, ge=1)


ProposedCommand = Annotated[
    NoArgumentCommand
    | MoveCommand
    | TargetCommand
    | ContainerCommand
    | ItemContainerCommand
    | ItemCapabilityCommand
    | GiveCommand
    | SayCommand
    | TellCommand
    | WhoCommand,
    Field(discriminator="action"),
]


class InterpretCommandResponse(StrictModel):
    """A validated command proposal; it is never an authoritative outcome."""

    command: ProposedCommand
