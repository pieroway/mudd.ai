from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RoomRecord(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class ExitRecord(Base):
    __tablename__ = "room_exits"

    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True
    )
    direction: Mapped[str] = mapped_column(String(20), primary_key=True)
    destination_room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )


class PlayerRecord(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    current_room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False
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
