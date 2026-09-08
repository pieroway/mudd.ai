"""Persistent NPC location and private, bounded per-character memory."""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NPCRecord(Base):
    __tablename__ = "npcs"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    secret: Mapped[str] = mapped_column(Text, nullable=False)


class NPCMemoryRecord(Base):
    __tablename__ = "npc_memories"
    __table_args__ = (
        CheckConstraint("interactions >= 0", name="ck_npc_memory_interactions"),
        CheckConstraint("char_length(player_text) <= 400", name="ck_npc_memory_player_text"),
        CheckConstraint("char_length(npc_text) <= 600", name="ck_npc_memory_npc_text"),
    )
    npc_id: Mapped[str] = mapped_column(ForeignKey("npcs.id", ondelete="CASCADE"), primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    interactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    player_text: Mapped[str] = mapped_column(String(400), nullable=False)
    npc_text: Mapped[str] = mapped_column(String(600), nullable=False)
