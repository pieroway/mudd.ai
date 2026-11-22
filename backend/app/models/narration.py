"""Shared presentation variants keyed by a digest of an authoritative outcome."""

from sqlalchemy import CheckConstraint, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NarrationLibraryRecord(Base):
    __tablename__ = "narration_library"
    __table_args__ = (
        CheckConstraint("jsonb_array_length(flourishes) BETWEEN 1 AND 5",
                        name="ck_narration_library_size"),
    )

    outcome_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    flourishes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
