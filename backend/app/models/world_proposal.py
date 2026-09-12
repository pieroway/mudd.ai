"""Private immutable room drafts and their terminal decisions."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from typing import Any

from app.models.base import Base


class WorldProposalRecord(Base):
    __tablename__ = "world_proposals"
    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','rejected','stale')", name="ck_world_status"),
        CheckConstraint("direction IN ('north','south','east','west','up','down')", name="ck_world_direction"),
        CheckConstraint("(status = 'approved') = (result_room_id IS NOT NULL)", name="ck_world_result"),
        CheckConstraint("(status = 'pending') = (decided_at IS NULL)", name="ck_world_decision"),
        CheckConstraint("schema_version IN (1,2)", name="ck_world_schema"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    creator_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), index=True)
    source_room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="RESTRICT"))
    source_fingerprint: Mapped[str] = mapped_column(String(64))
    direction: Mapped[str] = mapped_column(String(5))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(8), default="pending", server_default="pending")
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_room_id: Mapped[str | None] = mapped_column(ForeignKey("rooms.id", ondelete="RESTRICT"))
