from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Any

from app.domain.item_template import ItemTemplate


@dataclass
class Item:
    id: str
    name: str
    description: str
    room_id: str | None = None
    owned_by: str | None = None
    container_id: str | None = None
    can_open: bool = False
    is_open: bool = False
    can_use: bool = False
    use_message: str | None = None
    is_light_source: bool = False
    is_lit: bool = False
    fuel_remaining: int | None = None
    portable: bool = True
    interaction_target_id: str | None = None
    is_clean: bool = False
    interaction_verb: str | None = None
    interaction_state: str | None = None
    template_id: str | None = None
    aliases: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    material: str | None = None
    weight_kg: float | None = None
    size: str | None = None
    dimensions_cm: dict[str, float | None] = field(default_factory=dict)
    capabilities: dict[str, dict[str, Any]] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    quantity: int = 1
    durability: int | None = None
    maximum_durability: int | None = None
    condition: dict[str, Any] = field(default_factory=dict)
    relationships: dict[str, Any] = field(default_factory=dict)
    discovery: dict[str, Any] = field(
        default_factory=lambda: {"hidden": False, "discovered_by": []}
    )
    provenance: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_template(
        cls,
        instance_id: str,
        template: ItemTemplate,
        *,
        room_id: str | None = None,
        owned_by: str | None = None,
        container_id: str | None = None,
        quantity: int = 1,
        provenance: dict[str, Any] | None = None,
    ) -> Item:
        if quantity < 1:
            raise ValueError("item quantity must be at least one")
        locations = (room_id, owned_by, container_id)
        if sum(location is not None for location in locations) != 1:
            raise ValueError("an item instance must have exactly one location")

        capabilities = deepcopy(template.capabilities)
        state = deepcopy(template.default_state)
        breakable = capabilities.get("breakable", {})
        maximum_durability = breakable.get("maximum_durability")
        durability = state.get("durability", maximum_durability)
        condition = {
            "durability": durability,
            "maximum_durability": maximum_durability,
            "broken": bool(state.get("broken", False)),
        }
        dimensions = template.physical.dimensions_cm.model_dump()

        return cls(
            id=instance_id,
            name=template.name,
            description=template.description.examine,
            room_id=room_id,
            owned_by=owned_by,
            container_id=container_id,
            can_open="openable" in capabilities,
            is_open=bool(state.get("open", False)),
            can_use="usable" in capabilities,
            is_light_source="lightable" in capabilities,
            is_lit=bool(state.get("lit", False)),
            fuel_remaining=state.get("fuel_remaining"),
            portable=template.physical.portable,
            template_id=template.template_id,
            aliases=tuple(template.aliases),
            categories=tuple(template.categories),
            material=template.material,
            weight_kg=template.physical.weight_kg,
            size=template.physical.size,
            dimensions_cm=dimensions,
            capabilities=capabilities,
            state=state,
            quantity=quantity,
            durability=durability,
            maximum_durability=maximum_durability,
            condition=condition,
            provenance=deepcopy(provenance or {"source": "authored"}),
        )

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities

    def is_in_room(self, room_id: str) -> bool:
        return self.room_id == room_id and self.owned_by is None

    def take_by(self, player_id: str) -> None:
        self.room_id = None
        self.container_id = None
        self.owned_by = player_id

    def drop_in(self, room_id: str) -> None:
        self.owned_by = None
        self.container_id = None
        self.room_id = room_id

    def put_in(self, container_id: str) -> None:
        self.room_id = None
        self.owned_by = None
        self.container_id = container_id
