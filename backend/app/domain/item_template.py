from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ItemSize = Literal["tiny", "small", "medium", "large", "huge"]
ItemRarity = Literal["common", "uncommon", "rare", "legendary"]

CAPABILITY_NAMES = frozenset(
    {
        "attachable",
        "breakable",
        "climbable",
        "closeable",
        "consumable",
        "container",
        "detachable",
        "diggable",
        "enterable",
        "examinable",
        "extinguishable",
        "fillable",
        "foldable",
        "harvestable",
        "holdable",
        "lieable",
        "lightable",
        "loadable",
        "lockable",
        "movable",
        "openable",
        "pickable",
        "pilotable",
        "pourable",
        "pryable",
        "pullable",
        "pushable",
        "readable",
        "repairable",
        "searchable",
        "sittable",
        "stackable",
        "surface",
        "switchable",
        "takeable",
        "throwable",
        "tieable",
        "traversable",
        "usable",
        "wearable",
        "wieldable",
    }
)


class TemplateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ItemDescription(TemplateModel):
    short: str = Field(min_length=1, max_length=500)
    examine: str = Field(min_length=1, max_length=4000)


class ItemDimensions(TemplateModel):
    length: float | None = Field(default=None, gt=0)
    width: float | None = Field(default=None, gt=0)
    height: float | None = Field(default=None, gt=0)


class ItemPhysicalProperties(TemplateModel):
    weight_kg: float = Field(ge=0)
    size: ItemSize
    dimensions_cm: ItemDimensions = Field(default_factory=ItemDimensions)
    portable: bool


class ItemValue(TemplateModel):
    amount: int = Field(ge=0)
    currency: str = Field(default="copper", min_length=1, max_length=30)


class ItemTemplate(TemplateModel):
    template_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")
    name: str = Field(min_length=1, max_length=100)
    aliases: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    description: ItemDescription
    material: str = Field(min_length=1, max_length=100)
    physical: ItemPhysicalProperties
    capabilities: dict[str, dict[str, Any]] = Field(default_factory=dict)
    default_state: dict[str, Any] = Field(default_factory=dict)
    value: ItemValue = Field(default_factory=lambda: ItemValue(amount=0))
    rarity: ItemRarity = "common"
    equipment_slots: tuple[str, ...] = ()
    stackable: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("aliases", "categories", "equipment_slots")
    @classmethod
    def validate_unique_names(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = [value.strip().casefold() for value in values]
        if any(not value for value in normalized):
            raise ValueError("names must not be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("names must be unique")
        return values

    @model_validator(mode="after")
    def validate_capabilities(self) -> ItemTemplate:
        unknown = sorted(set(self.capabilities) - CAPABILITY_NAMES)
        if unknown:
            raise ValueError(f"unsupported capabilities: {', '.join(unknown)}")
        if self.stackable and "stackable" not in self.capabilities:
            raise ValueError("stackable templates must declare the stackable capability")
        return self


class ItemTemplateRegistry(Mapping[str, ItemTemplate]):
    """Immutable lookup for validated, uniquely identified item templates."""

    def __init__(self, templates: Iterable[ItemTemplate]) -> None:
        indexed: dict[str, ItemTemplate] = {}
        for template in templates:
            if template.template_id in indexed:
                raise ValueError(f"duplicate item template: {template.template_id}")
            indexed[template.template_id] = template
        self._templates = indexed

    def __getitem__(self, template_id: str) -> ItemTemplate:
        return self._templates[template_id]

    def __iter__(self) -> Iterator[str]:
        return iter(self._templates)

    def __len__(self) -> int:
        return len(self._templates)
