from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BuildingRecord(Base):
    __tablename__ = "buildings"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class RoomRecord(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    building_id: Mapped[str | None] = mapped_column(ForeignKey("buildings.id", ondelete="RESTRICT"), index=True)


class DoorRecord(Base):
    __tablename__ = "doors"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    destination_room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    is_open: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class ExitRecord(Base):
    __tablename__ = "room_exits"

    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True
    )
    direction: Mapped[str] = mapped_column(String(20), primary_key=True)
    door_id: Mapped[str | None] = mapped_column(ForeignKey("doors.id", ondelete="RESTRICT"))
    destination_room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )


class PlayerRecord(Base):
    __tablename__ = "players"
    __table_args__ = (
        CheckConstraint("facing_direction IN ('north','east','south','west')", name="ck_player_facing"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    facing_direction: Mapped[str] = mapped_column(String(5), nullable=False, default="north", server_default="north")
    current_room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False
    )


class PlayerDiscoveryRecord(Base):
    __tablename__ = "player_discoveries"

    player_id: Mapped[str] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True
    )


class ItemTemplateRecord(Base):
    __tablename__ = "item_templates"
    __table_args__ = (
        CheckConstraint(
            "rarity IN ('common','uncommon','rare','legendary')",
            name="ck_item_templates_rarity",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    short_description: Mapped[str] = mapped_column(String(500), nullable=False)
    examine_description: Mapped[str] = mapped_column(Text, nullable=False)
    material: Mapped[str] = mapped_column(String(100), nullable=False)
    physical: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    capabilities: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    default_state: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    value: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=lambda: {"amount": 0, "currency": "copper"}
    )
    rarity: Mapped[str] = mapped_column(String(20), nullable=False, default="common")
    equipment_slots: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    stackable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attributes: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ItemRecord(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint(
            "(room_id IS NOT NULL AND owner_id IS NULL AND container_id IS NULL) OR "
            "(room_id IS NULL AND owner_id IS NOT NULL AND container_id IS NULL) OR "
            "(room_id IS NULL AND owner_id IS NULL AND container_id IS NOT NULL)",
            name="ck_items_exactly_one_location",
        ),
        CheckConstraint("NOT is_open OR can_open", name="ck_items_open_requires_capability"),
        CheckConstraint(
            "fuel_remaining IS NULL OR fuel_remaining >= 0",
            name="ck_items_fuel_nonnegative",
        ),
        CheckConstraint("quantity > 0", name="ck_items_quantity_positive"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    room_id: Mapped[str | None] = mapped_column(
        ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=True
    )
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("players.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    container_id: Mapped[str | None] = mapped_column(
        ForeignKey("items.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    can_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_use: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    use_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_light_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_lit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fuel_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    portable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    interaction_target_id: Mapped[str | None] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"))
    is_clean: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    interaction_verb: Mapped[str | None] = mapped_column(String(12))
    interaction_state: Mapped[str | None] = mapped_column(String(12))
    template_id: Mapped[str | None] = mapped_column(
        ForeignKey("item_templates.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    state_data: Mapped[dict[str, object]] = mapped_column(
        "state", JSONB, nullable=False, default=dict
    )
    condition: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    relationships: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    discovery: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {"hidden": False, "discovered_by": []},
    )
    provenance: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=lambda: {"source": "authored"}
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
